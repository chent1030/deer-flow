import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.admin.config import AdminConfig
from app.admin.minio import MinioClient
from app.admin.routers import audit_threads as admin_audit_threads
from app.admin.routers import agent_share_records as admin_agent_share_records
from app.admin.routers import auth as admin_auth
from app.admin.routers import departments as admin_depts
from app.admin.routers import skills as admin_skills
from app.admin.routers import users as admin_users
from app.gateway.auth_middleware import AuthMiddleware
from app.gateway.config import get_gateway_config
from app.gateway.csrf_middleware import CSRFMiddleware, get_configured_cors_origins
from app.gateway.deps import langgraph_runtime
from app.gateway.error_localization import localize_error_detail
from app.gateway.routers import (
    agents,
    artifacts,
    assistants_compat,
    auth,
    channels,
    feedback,
    mcp,
    memory,
    models,
    runs,
    scheduler,
    skills,
    suggestions,
    thread_runs,
    threads,
    uploads,
    users,
)
from deerflow.config import app_config as deerflow_app_config
from deerflow.config.app_config import apply_logging_level

AppConfig = deerflow_app_config.AppConfig
get_app_config = deerflow_app_config.get_app_config

# Default logging; lifespan overrides from config.yaml log_level.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# Upper bound (seconds) each lifespan shutdown hook is allowed to run.
# Bounds worker exit time so uvicorn's reload supervisor does not keep
# firing signals into a worker that is stuck waiting for shutdown cleanup.
_SHUTDOWN_HOOK_TIMEOUT_SECONDS = 5.0


async def _ensure_admin_user(app: FastAPI) -> None:
    """Startup hook: check admin bootstrap and migrate orphan threads.

    Uses the clerk admin user table (app.admin.models.user.User) which
    manages users via the admin panel. The deer-flow built-in auth user
    table (deerflow.persistence.user.model.UserRow) is not used when
    the admin module is active.
    """
    from sqlalchemy import select

    from app.admin.models.user import User, UserRole
    from deerflow.persistence.engine import get_session_factory

    sf = get_session_factory()
    if sf is None:
        return

    try:
        async with sf() as session:
            stmt = select(User).where(User.role == UserRole.SUPER_ADMIN).limit(1)
            row = (await session.execute(stmt)).scalar_one_or_none()
    except Exception:
        logger.warning("Admin user check failed (table may not exist yet); run `make db-migrate` to initialize", exc_info=True)
        return

    if row is None:
        logger.info("=" * 60)
        logger.info("  First boot detected — no admin account exists.")
        logger.info("  Run `make db-seed` to create the initial admin account.")
        logger.info("=" * 60)
        return

    admin_id = str(row.id)

    # LangGraph store orphan migration — non-fatal.
    store = getattr(app.state, "store", None)
    if store is not None:
        try:
            migrated = await _migrate_orphaned_threads(store, admin_id)
            if migrated:
                logger.info("Migrated %d orphan LangGraph thread(s) to admin", migrated)
        except Exception:
            logger.exception("LangGraph thread migration failed (non-fatal)")


async def _iter_store_items(store, namespace, *, page_size: int = 500):
    """Paginated async iterator over a LangGraph store namespace.

    Replaces the old hardcoded ``limit=1000`` call with a cursor-style
    loop so that environments with more than one page of orphans do
    not silently lose data. Terminates when a page is empty OR when a
    short page arrives (indicating the last page).
    """
    offset = 0
    while True:
        batch = await store.asearch(namespace, limit=page_size, offset=offset)
        if not batch:
            return
        for item in batch:
            yield item
        if len(batch) < page_size:
            return
        offset += page_size


async def _migrate_orphaned_threads(store, admin_user_id: str) -> int:
    """Migrate LangGraph store threads with no user_id to the given admin.

    Uses cursor pagination so all orphans are migrated regardless of
    count. Returns the number of rows migrated.
    """
    migrated = 0
    async for item in _iter_store_items(store, ("threads",)):
        metadata = item.value.get("metadata", {})
        if not metadata.get("user_id"):
            metadata["user_id"] = admin_user_id
            item.value["metadata"] = metadata
            await store.aput(("threads",), item.key, item.value)
            migrated += 1
    return migrated


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""

    # Load config and check necessary environment variables at startup.
    # `startup_config` is a local snapshot used only for one-shot bootstrap
    # work (logging level, langgraph_runtime engines, channels). Request-time
    # config resolution always routes through `get_app_config()` in
    # `app/gateway/deps.py::get_config()` so `config.yaml` edits become
    # visible without a process restart. We deliberately do NOT cache this
    # snapshot on `app.state` to keep that contract enforceable.
    try:
        startup_config = get_app_config()
        apply_logging_level(startup_config.log_level)
        logger.info("Configuration loaded successfully")
    except Exception as e:
        error_msg = f"Failed to load configuration during gateway startup: {e}"
        logger.exception(error_msg)
        raise RuntimeError(error_msg) from e
    config = get_gateway_config()
    logger.info(f"Starting API Gateway on {config.host}:{config.port}")

    admin_config: AdminConfig = startup_config.admin
    if isinstance(admin_config, dict):
        admin_config = AdminConfig(**admin_config)
    admin_engine = create_async_engine(admin_config.database_url)
    app.state.admin_session_factory = async_sessionmaker(admin_engine, expire_on_commit=False)
    app.state.minio_client = MinioClient(admin_config.minio)
    logger.info("Admin module initialised (DB + MinIO)")

    # Pre-warm tiktoken encoding cache so the first memory-injection request
    # never blocks on the BPE data download (which hits an OpenAI/Azure URL
    # that may be unreachable in restricted networks — see issue #3402).
    try:
        from deerflow.agents.memory.prompt import warm_tiktoken_cache

        warmed = await asyncio.wait_for(
            asyncio.to_thread(warm_tiktoken_cache),
            timeout=5,
        )
        if warmed:
            logger.info("tiktoken encoding cache warmed successfully")
        else:
            logger.warning("tiktoken encoding cache warm-up failed; token counting will use character-based fallback")
    except TimeoutError:
        logger.warning("tiktoken encoding cache warm-up timed out; token counting will use character-based fallback")
    except Exception:
        logger.warning("tiktoken warm-up skipped", exc_info=True)

    # Initialize LangGraph runtime components (StreamBridge, RunManager, checkpointer, store)
    async with langgraph_runtime(app, startup_config):
        logger.info("LangGraph runtime initialised")

        # Check admin bootstrap state and migrate orphan threads after admin exists.
        # Must run AFTER langgraph_runtime so app.state.store is available for thread migration
        await _ensure_admin_user(app)

        # Start IM channel service if any channels are configured
        try:
            from app.channels.service import start_channel_service

            channel_service = await start_channel_service(startup_config)
            logger.info("Channel service started: %s", channel_service.get_status())
        except Exception:
            logger.exception("No IM channels configured or channel service failed to start")

        # Initialize scheduler
        import os
        try:
            from app.admin.services.scheduler_service import load_all_enabled_tasks
            from deerflow.scheduler.executor import TaskExecutor
            from deerflow.scheduler.manager import SchedulerManager

            sched_mgr = SchedulerManager.get_instance()
            langgraph_url = os.environ.get("DEER_FLOW_SCHEDULER_LANGGRAPH_URL", f"http://{config.host}:{config.port}")
            executor = TaskExecutor(app.state.admin_session_factory, langgraph_url=langgraph_url)
            sched_mgr.set_executor(executor)
            sched_mgr.start()
            app.state.scheduler_manager = sched_mgr

            async with app.state.admin_session_factory() as db:
                enabled_tasks = await load_all_enabled_tasks(db)
            for t in enabled_tasks:
                sched_mgr.register_task(str(t.id), t.cron_expression)
            logger.info("Scheduler loaded %d enabled tasks", len(enabled_tasks))
        except Exception:
            logger.exception("Failed to initialize scheduler (non-fatal)")

        yield

        # Stop scheduler
        try:
            from deerflow.scheduler.manager import SchedulerManager
            sched_mgr = SchedulerManager.get_instance()
            if sched_mgr is not None:
                sched_mgr.stop()
                logger.info("Scheduler stopped")
        except Exception:
            logger.exception("Failed to stop scheduler")

        # Stop channel service on shutdown (bounded to prevent worker hang)
        try:
            from app.channels.service import stop_channel_service

            await asyncio.wait_for(
                stop_channel_service(),
                timeout=_SHUTDOWN_HOOK_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.warning(
                "Channel service shutdown exceeded %.1fs; proceeding with worker exit.",
                _SHUTDOWN_HOOK_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.exception("Failed to stop channel service")

    await admin_engine.dispose()
    logger.info("Shutting down API Gateway")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    config = get_gateway_config()
    docs_url = "/docs" if config.enable_docs else None
    redoc_url = "/redoc" if config.enable_docs else None
    openapi_url = "/openapi.json" if config.enable_docs else None

    app = FastAPI(
        title="DeerFlow API Gateway",
        description="""
## DeerFlow API Gateway

API Gateway for DeerFlow - A LangGraph-based AI agent backend with sandbox execution capabilities.

### Features

- **Models Management**: Query and retrieve available AI models
- **MCP Configuration**: Manage Model Context Protocol (MCP) server configurations
- **Memory Management**: Access and manage global memory data for personalized conversations
- **Skills Management**: Query and manage skills and their enabled status
- **Artifacts**: Access thread artifacts and generated files
- **Health Monitoring**: System health check endpoints

### Architecture

LangGraph-compatible requests are routed through nginx to this gateway.
This gateway provides runtime endpoints for agent runs plus custom endpoints for models, MCP configuration, skills, and artifacts.
        """,
        version="0.1.0",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        openapi_tags=[
            {
                "name": "models",
                "description": "Operations for querying available AI models and their configurations",
            },
            {
                "name": "mcp",
                "description": "Manage Model Context Protocol (MCP) server configurations",
            },
            {
                "name": "memory",
                "description": "Access and manage global memory data for personalized conversations",
            },
            {
                "name": "skills",
                "description": "Manage skills and their configurations",
            },
            {
                "name": "artifacts",
                "description": "Access and download thread artifacts and generated files",
            },
            {
                "name": "uploads",
                "description": "Upload and manage user files for threads",
            },
            {
                "name": "threads",
                "description": "Manage DeerFlow thread-local filesystem data",
            },
            {
                "name": "agents",
                "description": "Create and manage custom agents with per-agent config and prompts",
            },
            {
                "name": "suggestions",
                "description": "Generate follow-up question suggestions for conversations",
            },
            {
                "name": "channels",
                "description": "Manage IM channel integrations (Feishu, Slack, Telegram)",
            },
            {
                "name": "assistants-compat",
                "description": "LangGraph Platform-compatible assistants API (stub)",
            },
            {
                "name": "runs",
                "description": "LangGraph Platform-compatible runs lifecycle (create, stream, cancel)",
            },
            {
                "name": "health",
                "description": "Health check and system status endpoints",
            },
        ],
    )

    @app.exception_handler(HTTPException)
    async def localized_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": localize_error_detail(exc.detail)},
            headers=exc.headers,
        )

    # Auth: reject unauthenticated requests to non-public paths (fail-closed safety net)
    app.add_middleware(AuthMiddleware)

    # CSRF: Double Submit Cookie pattern for state-changing requests
    app.add_middleware(CSRFMiddleware)

    # CORS: the unified nginx endpoint is same-origin by default. Split-origin
    # browser clients must opt in with this explicit Gateway allowlist so CORS
    # and CSRF origin checks share the same source of truth.
    cors_origins = sorted(get_configured_cors_origins())
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Include routers
    # Models API is mounted at /api/models
    app.include_router(models.router)

    # MCP API is mounted at /api/mcp
    app.include_router(mcp.router)

    # Memory API is mounted at /api/memory
    app.include_router(memory.router)

    # Skills API is mounted at /api/skills
    app.include_router(skills.router)

    # Artifacts API is mounted at /api/threads/{thread_id}/artifacts
    app.include_router(artifacts.router)

    # Uploads API is mounted at /api/threads/{thread_id}/uploads
    app.include_router(uploads.router)

    # Thread cleanup API is mounted at /api/threads/{thread_id}
    app.include_router(threads.router)

    # Agents API is mounted at /api/agents
    app.include_router(agents.router)

    # User lookup API is mounted at /api/users
    app.include_router(users.router)

    # Suggestions API is mounted at /api/threads/{thread_id}/suggestions
    app.include_router(suggestions.router)

    # Channels API is mounted at /api/channels
    app.include_router(channels.router)

    # Assistants compatibility API (LangGraph Platform stub)
    app.include_router(assistants_compat.router)

    # Auth API is mounted at /api/v1/auth
    app.include_router(auth.router)

    # Feedback API is mounted at /api/threads/{thread_id}/runs/{run_id}/feedback
    app.include_router(feedback.router)

    # Thread Runs API (LangGraph Platform-compatible runs lifecycle)
    app.include_router(thread_runs.router)

    # Admin API routes
    app.include_router(admin_auth.router)
    app.include_router(admin_users.router)
    app.include_router(admin_depts.router)
    app.include_router(admin_skills.router)
    app.include_router(admin_audit_threads.router)
    app.include_router(admin_agent_share_records.router)

    # Scheduler API
    app.include_router(scheduler.router)

    # Stateless Runs API (stream/wait without a pre-existing thread)
    app.include_router(runs.router)

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        """Health check endpoint.

        Returns:
            Service health status information.
        """
        return {"status": "healthy", "service": "deer-flow-gateway"}

    return app


def get_app() -> FastAPI:
    return app


# Create app instance for uvicorn
app = create_app()
