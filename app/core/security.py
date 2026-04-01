from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if the candidate password matches the stored hash."""

    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""

    return pwd_context.hash(password)


def _create_token(data: Dict[str, Any], expires_delta: timedelta, secret_key: str) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm=settings.algorithm)


def create_access_token(subject: str) -> str:
    """Issue a short-lived access token."""

    return _create_token(
        {"sub": subject, "scope": "access"},
        timedelta(minutes=settings.access_token_expire_minutes),
        settings.jwt_secret_key,
    )


def create_refresh_token(subject: str) -> str:
    """Issue a long-lived refresh token."""

    return _create_token(
        {"sub": subject, "scope": "refresh"},
        timedelta(minutes=settings.refresh_token_expire_minutes),
        settings.jwt_refresh_secret_key,
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate an access token."""

    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.algorithm])
        if payload.get("scope") != "access":
            raise JWTError("Invalid token scope")
        return payload
    except JWTError as exc:
        raise ValueError("Invalid access token") from exc


def decode_refresh_token(token: str) -> Dict[str, Any]:
    """Decode and validate a refresh token."""

    try:
        payload = jwt.decode(token, settings.jwt_refresh_secret_key, algorithms=[settings.algorithm])
        if payload.get("scope") != "refresh":
            raise JWTError("Invalid token scope")
        return payload
    except JWTError as exc:
        raise ValueError("Invalid refresh token") from exc
