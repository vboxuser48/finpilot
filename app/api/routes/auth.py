from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, http_error
from app.core.security import create_access_token, create_refresh_token, decode_refresh_token
from app.schemas.auth import AccessTokenResponse, RefreshTokenRequest, TokenPair
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair, summary="Authenticate and obtain JWT pair")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)) -> TokenPair:
    """Authenticate via OAuth2 password flow."""

    user = await UserService.authenticate(db, form_data.username, form_data.password)
    if not user:
        raise http_error(status.HTTP_401_UNAUTHORIZED, "invalid_credentials", "Incorrect email or password")

    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=AccessTokenResponse, summary="Exchange refresh token for access token")
async def refresh(payload: RefreshTokenRequest) -> AccessTokenResponse:
    """Issue a new access token using a refresh token."""

    try:
        data = decode_refresh_token(payload.refresh_token)
    except ValueError:
        raise http_error(status.HTTP_401_UNAUTHORIZED, "invalid_refresh", "Refresh token is invalid or expired")

    subject = data.get("sub")
    if not subject:
        raise http_error(status.HTTP_400_BAD_REQUEST, "invalid_refresh", "Refresh token missing subject")

    return AccessTokenResponse(access_token=create_access_token(subject))
