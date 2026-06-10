from fastapi import Request
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/auth/login", auto_error=False)


async def get_token_from_request(request: Request) -> str | None:
    token = await oauth2_scheme(request)
    if token:
        return token
    return request.cookies.get("access_token")
