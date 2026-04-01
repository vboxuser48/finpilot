import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, http_error, require_role
from app.models.user import User, UserRole
from app.schemas.record import RecordCreate, RecordFilter, RecordListResponse, RecordRead, RecordUpdate
from app.services.record_service import RecordService

router = APIRouter(prefix="/records", tags=["records"])


@router.get("/", response_model=RecordListResponse, summary="List financial records")
async def list_records(
    filters: RecordFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.viewer, UserRole.analyst, UserRole.admin)),
) -> RecordListResponse:
    """Return a filtered, paginated collection of financial records."""

    payload = await RecordService.list_records(db, current_user, filters)
    return RecordListResponse(
        items=[RecordRead.model_validate(record) for record in payload["items"]],
        total=payload["total"],
        page=filters.page,
        page_size=filters.page_size,
    )


@router.post(
    "/",
    response_model=RecordRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a financial record",
)
async def create_record(
    body: RecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.analyst, UserRole.admin)),
) -> RecordRead:
    """Create a financial record for the authenticated user or a specified owner."""

    try:
        record = await RecordService.create_record(db, current_user, body)
    except PermissionError as exc:
        raise http_error(status.HTTP_403_FORBIDDEN, "forbidden", str(exc)) from exc
    except LookupError as exc:
        raise http_error(status.HTTP_404_NOT_FOUND, "not_found", str(exc)) from exc
    except ValueError as exc:
        raise http_error(status.HTTP_400_BAD_REQUEST, "validation_error", str(exc)) from exc
    return RecordRead.model_validate(record)


@router.get("/{record_id}", response_model=RecordRead, summary="Retrieve a financial record")
async def get_record(
    record_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.viewer, UserRole.analyst, UserRole.admin)),
) -> RecordRead:
    """Return a single record if the user has access."""

    record = await RecordService.get_accessible_record(db, current_user, record_id)
    if not record:
        raise http_error(status.HTTP_404_NOT_FOUND, "not_found", "Record not found")
    return RecordRead.model_validate(record)


@router.patch("/{record_id}", response_model=RecordRead, summary="Update a financial record")
async def update_record(
    record_id: uuid.UUID,
    body: RecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.analyst, UserRole.admin)),
) -> RecordRead:
    """Patch a record, enforcing ownership rules."""

    record = await RecordService.update_record(db, current_user, record_id, body)
    if not record:
        raise http_error(status.HTTP_404_NOT_FOUND, "not_found", "Record not found or access denied")
    return RecordRead.model_validate(record)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Soft delete a record")
async def delete_record(
    record_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
) -> None:
    """Soft delete a financial record (admin only)."""

    success = await RecordService.soft_delete_record(db, record_id)
    if not success:
        raise http_error(status.HTTP_404_NOT_FOUND, "not_found", "Record not found")
    return None
