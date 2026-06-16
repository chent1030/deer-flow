"""LangGraph compatibility auth handler — shares JWT logic with Gateway.

The default DeerFlow runtime is embedded in the FastAPI Gateway; scripts and
Docker deployments do not load this module.  It is retained for LangGraph
tooling, Studio, or direct LangGraph Server compatibility through
``langgraph.json``'s ``auth.path``.

When that compatibility path is used, this module reuses the same JWT and CSRF
rules as Gateway so both modes validate sessions consistently.

Two layers:
  1. @auth.authenticate — validates JWT cookie, extracts user_id,
     and enforces CSRF on state-changing methods (POST/PUT/DELETE/PATCH)
  2. @auth.on — returns metadata filter so each user only sees own threads
"""

import secrets

from langgraph_sdk import Auth

from app.gateway.auth.errors import TokenError
from app.gateway.auth.jwt import decode_token
from app.gateway.deps import get_local_provider

auth = Auth()

# Methods that require CSRF validation (state-changing per RFC 7231).
_CSRF_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})


def _check_csrf(request) -> None:
    """Enforce Double Submit Cookie CSRF check for state-changing requests.

    Mirrors Gateway's CSRFMiddleware logic so that LangGraph routes
    proxied directly by nginx have the same CSRF protection.
    """
    method = getattr(request, "method", "") or ""
    if method.upper() not in _CSRF_METHODS:
        return

    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("x-csrf-token")

    if not cookie_token or not header_token:
        raise Auth.exceptions.HTTPException(
            status_code=403,
            detail="缺少 CSRF 令牌，请携带 X-CSRF-Token 请求头。",
        )

    if not secrets.compare_digest(cookie_token, header_token):
        raise Auth.exceptions.HTTPException(
            status_code=403,
            detail="CSRF 令牌不匹配。",
        )


@auth.authenticate
async def authenticate(request):
    """Validate the session cookie, decode JWT, and check token_version.

    Same validation chain as Gateway's get_current_user_from_request:
      cookie → decode JWT → DB lookup → token_version match
    Also enforces CSRF on state-changing methods.
    """
    # CSRF check before authentication so forged cross-site requests
    # are rejected early, even if the cookie carries a valid JWT.
    _check_csrf(request)

    token = request.cookies.get("access_token")
    if not token:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="请先登录。",
        )

    payload = decode_token(token)
    if isinstance(payload, TokenError):
        if payload == TokenError.EXPIRED:
            raise Auth.exceptions.HTTPException(
                status_code=401,
                detail="登录状态无效，请重新登录。",
            )
        from types import SimpleNamespace

        from fastapi import HTTPException

        from app.gateway.deps import get_admin_session_user_from_request

        try:
            user = await get_admin_session_user_from_request(
                SimpleNamespace(cookies=request.cookies, app=getattr(request, "app", None))
            )
        except HTTPException as exc:
            if exc.status_code == 401:
                raise Auth.exceptions.HTTPException(
                    status_code=401,
                    detail="登录状态无效，请重新登录。",
                ) from exc
            raise Auth.exceptions.HTTPException(
                status_code=exc.status_code,
                detail=exc.detail,
            ) from exc
        return str(user.id)

    user = await get_local_provider().get_user(payload.sub)
    if user is None:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="用户不存在。",
        )
    if user.token_version != payload.ver:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="登录状态已失效，请重新登录。",
        )

    return payload.sub


@auth.on
async def add_owner_filter(ctx: Auth.types.AuthContext, value: dict):
    """Inject user_id metadata on writes; filter by user_id on reads.

    Gateway stores thread ownership as ``metadata.user_id``.
    This handler ensures LangGraph Server enforces the same isolation.
    """
    # On create/update: stamp user_id into metadata
    metadata = value.setdefault("metadata", {})
    metadata["user_id"] = ctx.user.identity

    # Return filter dict — LangGraph applies it to search/read/delete
    return {"user_id": ctx.user.identity}
