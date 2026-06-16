"""Regression coverage for the Gateway-owned LangGraph API runtime."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_root_makefile_no_longer_exposes_transition_gateway_targets():
    makefile = _read("Makefile")

    assert "dev-pro" not in makefile
    assert "start-pro" not in makefile
    assert "dev-daemon-pro" not in makefile
    assert "start-daemon-pro" not in makefile
    assert "docker-start-pro" not in makefile
    assert "up-pro" not in makefile
    assert not re.search(r"serve\.sh .*--gateway", makefile)
    assert "docker.sh start --gateway" not in makefile
    assert "deploy.sh --gateway" not in makefile


def test_service_launchers_always_use_gateway_runtime():
    operational_files = {
        "scripts/serve.sh": _read("scripts/serve.sh"),
        "scripts/docker.sh": _read("scripts/docker.sh"),
        "scripts/deploy.sh": _read("scripts/deploy.sh"),
        "docker/docker-compose-dev.yaml": _read("docker/docker-compose-dev.yaml"),
        "docker/docker-compose.yaml": _read("docker/docker-compose.yaml"),
    }

    for path, content in operational_files.items():
        assert "start --gateway" not in content, path
        assert "deploy.sh --gateway" not in content, path
        assert "langgraph dev" not in content, path
        assert "LANGGRAPH_UPSTREAM" not in content, path
        assert "LANGGRAPH_REWRITE" not in content, path


def test_local_dev_gateway_reload_excludes_runtime_state_with_absolute_dirs():
    serve_sh = _read("scripts/serve.sh")

    assert 'export DEER_FLOW_PROJECT_ROOT="$REPO_ROOT"' in serve_sh
    assert 'BACKEND_RUNTIME_HOME="$REPO_ROOT/backend/.deer-flow"' in serve_sh
    assert 'export DEER_FLOW_HOME="$BACKEND_RUNTIME_HOME"' in serve_sh
    # Every absolute reload-exclude must be pre-created, including backend/sandbox
    # (#3459 / #3454) — see test_uvicorn_reload_exclude.py for the mechanism.
    assert 'mkdir -p "$DEER_FLOW_HOME" "$BACKEND_RUNTIME_HOME" "$REPO_ROOT/backend/sandbox"' in serve_sh
    assert "--reload-exclude='$DEER_FLOW_HOME'" in serve_sh
    assert "--reload-exclude='$BACKEND_RUNTIME_HOME'" in serve_sh
    assert "--reload-exclude='sandbox/'" not in serve_sh
    assert "--reload-exclude='.deer-flow/'" not in serve_sh


def test_backend_container_only_exposes_gateway_port():
    dockerfile = _read("backend/Dockerfile")

    assert not re.search(r"^EXPOSE\s+.*\b2024\b", dockerfile, re.M)
    assert "langgraph: 2024" not in dockerfile
    assert re.search(r"^EXPOSE\s+8001\b", dockerfile, re.M)


def test_root_makefile_clean_does_not_reference_langgraph_server_cache():
    makefile = _read("Makefile")

    assert ".langgraph_api" not in makefile


def test_nginx_routes_official_langgraph_prefix_to_gateway_api():
    for path in ("docker/nginx/nginx.local.conf", "docker/nginx/nginx.conf"):
        content = _read(path)

        assert "/api/langgraph-compat" not in content
        assert "proxy_pass http://langgraph" not in content
        assert "rewrite ^/api/langgraph/(.*) /api/$1 break;" in content
        assert "proxy_pass http://gateway" in content or "proxy_pass http://$gateway_upstream" in content


def test_nginx_defers_cors_to_gateway_allowlist():
    for path in ("docker/nginx/nginx.local.conf", "docker/nginx/nginx.conf"):
        content = _read(path)

        assert "Access-Control-Allow-Origin" not in content
        assert "Access-Control-Allow-Methods" not in content
        assert "Access-Control-Allow-Headers" not in content
        assert "Access-Control-Allow-Credentials" not in content
        assert "proxy_hide_header 'Access-Control-Allow-" not in content
        assert "if ($request_method = 'OPTIONS')" not in content


def test_local_nginx_admin_route_matches_windows_admin_preview_port():
    nginx_config = _read("docker/nginx/nginx.local.conf")
    windows_launcher = _read("scripts/start-prod-windows.ps1")

    assert "location = /admin" in nginx_config
    assert "return 308 /admin/;" in nginx_config
    assert "location /admin" in nginx_config
    assert "proxy_pass http://127.0.0.1:3002;" in nginx_config
    assert "$adminCmd = \"pnpm preview --host 0.0.0.0 --port 3002\"" in windows_launcher


def test_local_nginx_routes_next_login_api_to_frontend_before_gateway_catchall():
    nginx_config = _read("docker/nginx/nginx.local.conf")
    login_api_block = re.search(r"location = /api/login \{(?P<body>.*?)\n        \}", nginx_config, re.S)
    api_catchall = nginx_config.index("location /api/ {")

    assert login_api_block is not None
    assert nginx_config.index("location = /api/login {") < api_catchall
    assert "proxy_pass http://frontend;" in login_api_block.group("body")


def test_gateway_app_exports_get_app_for_admin_dependencies():
    gateway_app = _read("backend/app/gateway/app.py")

    assert "def get_app() -> FastAPI:" in gateway_app
    assert "return app" in gateway_app


def test_local_nginx_admin_api_preserves_port_in_forwarded_host():
    nginx_config = _read("docker/nginx/nginx.local.conf")
    admin_api_block = re.search(r"location /api/admin \{(?P<body>.*?)\n        \}", nginx_config, re.S)

    assert admin_api_block is not None
    assert "proxy_set_header Host $http_host;" in admin_api_block.group("body")


def test_frontend_root_is_clerk_style_login_flow():
    root_page = _read("frontend/src/app/page.tsx")

    assert 'fetch("/api/login"' in root_page
    assert 'router.push("/workspace")' in root_page
    assert 'redirect("/login")' not in root_page
    assert "LandingPage" not in root_page


def test_workspace_layout_uses_clerk_cookie_flow_without_gateway_session_gate():
    workspace_layout = _read("frontend/src/app/workspace/layout.tsx")

    assert 'export const dynamic = "force-dynamic"' in workspace_layout
    assert "getServerSideUser" not in workspace_layout
    assert "redirect(\"/login\")" not in workspace_layout
    assert "WorkspaceSidebar" in workspace_layout
    assert "QueryClientProvider" in workspace_layout


def test_admin_router_uses_admin_basename_under_unified_nginx_path():
    app = _read("admin/src/App.tsx")
    layout = _read("admin/src/layouts/AdminLayout.tsx")

    assert "adminBasename" in app
    assert "window.location.pathname.startsWith('/admin')" in app
    assert "<BrowserRouter basename={adminBasename}>" in app
    assert 'path="/admin"' not in app
    assert "key: '/dashboard'" in layout
    assert "key: '/admin/dashboard'" not in layout
    assert "replace(/^\\/admin(?=\\/|$)/, '') || '/'" in layout


def test_admin_vite_proxy_preserves_browser_host_for_csrf_origin_check():
    vite_config = _read("admin/vite.config.ts")

    assert "const apiProxy" in vite_config
    assert "base: '/admin/'" in vite_config
    assert "changeOrigin: false" in vite_config
    assert "server: {" in vite_config
    assert "preview: {" in vite_config
    assert "proxy: apiProxy" in vite_config


def test_frontend_login_route_returns_to_clerk_username_login():
    auth_layout = _read("frontend/src/app/(auth)/layout.tsx")
    login_page = _read("frontend/src/app/(auth)/login/page.tsx")

    assert "getServerSideUser" not in auth_layout
    assert 'redirect("/")' in login_page
    assert "/api/v1/auth/login/local" not in login_page
    assert 'type="email"' not in login_page


def test_clerk_login_route_forwards_csrf_cookie_from_gateway():
    login_route = _read("frontend/src/app/api/login/route.ts")

    assert "getUpstreamSetCookies(res.headers)" in login_route
    assert "headers.getSetCookie?.()" in login_route
    assert 'readCookieValue(setCookie, "csrf_token")' in login_route
    assert 'response.cookies.set("csrf_token"' in login_route


def test_clerk_login_route_handles_non_json_gateway_errors():
    login_route = _read("frontend/src/app/api/login/route.ts")

    assert "async function readUpstreamError" in login_route
    assert "res.headers.get(\"content-type\")" in login_route
    assert "await res.text()" in login_route


def test_windows_launcher_validates_existing_builds_when_skipping_build_step():
    windows_launcher = _read("scripts/start-prod-windows.ps1")

    assert "function Ensure-FrontendBuild" in windows_launcher
    assert "function Ensure-AdminBuild" in windows_launcher
    assert "Ensure-FrontendBuild $repoRoot" in windows_launcher
    assert "Ensure-AdminBuild $repoRoot" in windows_launcher


def test_windows_launcher_uses_repo_local_uv_cache():
    windows_launcher = _read("scripts/start-prod-windows.ps1")

    assert "$env:UV_CACHE_DIR = Join-Path $repoRoot \".uv-cache\"" in windows_launcher
    assert "New-Item -ItemType Directory -Force -Path $env:UV_CACHE_DIR" in windows_launcher


def test_windows_launcher_rejects_stale_frontend_builds():
    windows_launcher = _read("scripts/start-prod-windows.ps1")

    assert "function Get-LatestWriteTime" in windows_launcher
    assert "frontend\\src" in windows_launcher
    assert "frontend\\package.json" in windows_launcher
    assert "frontend\\pnpm-lock.yaml" in windows_launcher
    assert "Frontend production build is stale" in windows_launcher


def test_windows_stop_script_cleans_known_service_ports():
    stop_script = _read("scripts/stop-prod-windows.ps1")

    assert "function Stop-PortProcess" in stop_script
    for port in ("2024", "8001", "3000", "3002", "2026"):
        assert port in stop_script


def test_gateway_cors_configuration_uses_gateway_allowlist():
    gateway_config = _read("backend/app/gateway/config.py")
    gateway_app = _read("backend/app/gateway/app.py")
    csrf_middleware = _read("backend/app/gateway/csrf_middleware.py")

    assert not re.search(r"(?<!GATEWAY_)[\"']CORS_ORIGINS[\"']", gateway_config)
    assert "cors_origins" not in gateway_config
    assert "get_configured_cors_origins" in gateway_app
    assert "GATEWAY_CORS_ORIGINS" in csrf_middleware


def test_frontend_rewrites_langgraph_prefix_to_gateway():
    next_config = _read("frontend/next.config.js")
    api_client = _read("frontend/src/core/api/api-client.ts")

    assert "DEER_FLOW_INTERNAL_LANGGRAPH_BASE_URL" not in next_config
    assert "http://127.0.0.1:2024" not in next_config
    assert "langgraph-compat" not in api_client


def test_smoke_test_docs_do_not_expect_standalone_langgraph_server():
    smoke_files = {
        ".agent/skills/smoke-test/SKILL.md": _read(".agent/skills/smoke-test/SKILL.md"),
        ".agent/skills/smoke-test/references/SOP.md": _read(".agent/skills/smoke-test/references/SOP.md"),
        ".agent/skills/smoke-test/references/troubleshooting.md": _read(".agent/skills/smoke-test/references/troubleshooting.md"),
        ".agent/skills/smoke-test/scripts/check_local_env.sh": _read(".agent/skills/smoke-test/scripts/check_local_env.sh"),
        ".agent/skills/smoke-test/scripts/deploy_local.sh": _read(".agent/skills/smoke-test/scripts/deploy_local.sh"),
        ".agent/skills/smoke-test/scripts/health_check.sh": _read(".agent/skills/smoke-test/scripts/health_check.sh"),
        ".agent/skills/smoke-test/templates/report.local.template.md": _read(".agent/skills/smoke-test/templates/report.local.template.md"),
        ".agent/skills/smoke-test/templates/report.docker.template.md": _read(".agent/skills/smoke-test/templates/report.docker.template.md"),
    }

    for path, content in smoke_files.items():
        assert "localhost:2024" not in content, path
        assert "127.0.0.1:2024" not in content, path
        assert "deer-flow-langgraph" not in content, path
        assert "langgraph.log" not in content, path
        assert "LangGraph service" not in content, path
        assert "langgraph dev" not in content, path


def test_gateway_runtime_docs_do_not_reference_transition_modes():
    docs = {
        "backend/docs/AUTH_UPGRADE.md": _read("backend/docs/AUTH_UPGRADE.md"),
        "backend/docs/AUTH_TEST_DOCKER_GAP.md": _read("backend/docs/AUTH_TEST_DOCKER_GAP.md"),
        "docs/CODE_CHANGE_SUMMARY_BY_FILE.md": _read("docs/CODE_CHANGE_SUMMARY_BY_FILE.md"),
    }

    for path, content in docs.items():
        assert "make dev-pro" not in content, path
        assert "./scripts/deploy.sh --gateway" not in content, path
        assert "docker compose --profile gateway" not in content, path
        assert "`/api/langgraph/*` → LangGraph" not in content, path
