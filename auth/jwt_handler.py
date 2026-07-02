"""auth/jwt_handler.py — JWT creation and validation"""
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from config.settings import get_settings

settings = get_settings()


def create_access_token(user_id: str, email: str, roles: list[str]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"verify_aud": False},
    )