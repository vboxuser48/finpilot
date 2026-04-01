from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=True)


def http_error(status_code: int, error: str, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": error, "detail": detail})


async def get_db() -> AsyncSession:
    async for session in get_session():
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Return the authenticated user based on the bearer token."""

    try:
        payload = decode_access_token(token)
    except ValueError:
        logger.error("Token validation failed")
        raise http_error(status.HTTP_401_UNAUTHORIZED, "auth_error", "Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise http_error(status.HTTP_401_UNAUTHORIZED, "auth_error", "Missing subject in token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise http_error(status.HTTP_401_UNAUTHORIZED, "auth_error", "User is inactive or not found")

    return user


def require_role(*roles: UserRole):
    """Ensure the current user has one of the allowed roles."""

    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if not roles:
            return current_user
        if current_user.role not in roles:
            raise http_error(status.HTTP_403_FORBIDDEN, "forbidden", "Insufficient role to access this resource")
        return current_user

    return _checker
