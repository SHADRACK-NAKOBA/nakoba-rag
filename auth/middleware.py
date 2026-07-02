"""auth/middleware.py — FastAPI auth dependency"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from auth.jwt_handler import decode_token
from auth.models import UserContext

bearer = HTTPBearer()


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
) -> UserContext:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(creds.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise exc
        return UserContext(
            user_id=user_id,
            email=payload.get("email", ""),
            display_name=payload.get("name", ""),
            roles=payload.get("roles", []),
            token=creds.credentials,
        )
    except JWTError:
        raise exc


async def get_current_user_optional(
    creds: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
) -> UserContext | None:
    if not creds:
        return None
    try:
        return await get_current_user(creds)
    except HTTPException:
        return None