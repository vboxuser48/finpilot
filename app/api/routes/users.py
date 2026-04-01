import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, http_error, require_role
from app.models.user import UserRole
from app.schemas.user import UserCreate, UserListResponse, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_role(UserRole.admin))])


@router.get("/", response_model=UserListResponse, summary="List users (admin only)")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    """Return a paginated list of platform users."""

    payload = await UserService.list_users(db, page=page, page_size=page_size)
    return UserListResponse(
        items=[UserRead.model_validate(user) for user in payload["items"]],
        total=payload["total"],
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Create a new user")
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db)) -> UserRead:
    """Create a user with the given payload."""

    try:
        user = await UserService.create_user(db, body)
    except ValueError as exc:
        raise http_error(status.HTTP_400_BAD_REQUEST, "validation_error", str(exc)) from exc
    return UserRead.model_validate(user)


@router.get("/{user_id}", response_model=UserRead, summary="Retrieve a user by id")
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> UserRead:
    """Return details for a single user."""

    user = await UserService.get_user(db, user_id)
    if not user:
        raise http_error(status.HTTP_404_NOT_FOUND, "not_found", "User not found")
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead, summary="Update a user")
async def update_user(user_id: uuid.UUID, body: UserUpdate, db: AsyncSession = Depends(get_db)) -> UserRead:
    """Apply partial updates to a user."""

    user = await UserService.update_user(db, user_id, body)
    if not user:
        raise http_error(status.HTTP_404_NOT_FOUND, "not_found", "User not found")
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Deactivate a user")
async def deactivate_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    """Soft delete a user by marking them inactive."""

    success = await UserService.deactivate_user(db, user_id)
    if not success:
        raise http_error(status.HTTP_404_NOT_FOUND, "not_found", "User not found")
    return None
