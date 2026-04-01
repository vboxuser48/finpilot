from datetime import date
import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.record import FinancialRecord
from app.models.user import User, UserRole
from app.schemas.record import RecordCreate, RecordFilter, RecordUpdate


class RecordService:
    """Business logic for financial records and filtering."""

    @staticmethod
    async def list_records(db: AsyncSession, user: User, filters: RecordFilter) -> dict:
        clauses = [FinancialRecord.is_deleted.is_(False)]
        if user.role == UserRole.viewer:
            clauses.append(FinancialRecord.user_id == user.id)
        if filters.type:
            clauses.append(FinancialRecord.type == filters.type)
        if filters.category:
            clauses.append(
                func.lower(FinancialRecord.category).contains(filters.category.lower())
            )
        if filters.date_from:
            clauses.append(FinancialRecord.date >= filters.date_from)
        if filters.date_to:
            clauses.append(FinancialRecord.date <= filters.date_to)

        stmt = (
            select(FinancialRecord)
            .where(and_(*clauses))
            .order_by(FinancialRecord.date.desc(), FinancialRecord.created_at.desc())
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )
        result = await db.execute(stmt)
        items = result.scalars().all()

        count_stmt = select(func.count()).select_from(FinancialRecord).where(and_(*clauses))
        total = await db.scalar(count_stmt)

        return {"items": items, "total": total or 0}

    @staticmethod
    async def create_record(db: AsyncSession, user: User, payload: RecordCreate) -> FinancialRecord:
        try:
            owner_id = user.id if not payload.user_id else uuid.UUID(payload.user_id)
        except ValueError as exc:
            raise ValueError("Invalid user_id format") from exc
        if payload.user_id and user.role != UserRole.admin:
            raise PermissionError("Only admins can create records for other users")

        owner = await db.get(User, owner_id)
        if not owner:
            raise LookupError("Owner user not found")

        record = FinancialRecord(
            user_id=owner.id,
            amount=payload.amount,
            type=payload.type,
            category=payload.category,
            date=payload.date,
            notes=payload.notes,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record

    @staticmethod
    async def get_accessible_record(db: AsyncSession, user: User, record_id: uuid.UUID) -> FinancialRecord | None:
        stmt = select(FinancialRecord).where(
            FinancialRecord.id == record_id,
            FinancialRecord.is_deleted.is_(False),
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()
        if not record:
            return None

        if user.role == UserRole.viewer and record.user_id != user.id:
            return None
        return record

    @staticmethod
    async def update_record(
        db: AsyncSession,
        user: User,
        record_id: uuid.UUID,
        payload: RecordUpdate,
    ) -> FinancialRecord | None:
        record = await RecordService.get_accessible_record(db, user, record_id)
        if not record:
            return None
        if user.role == UserRole.analyst and record.user_id != user.id:
            return None

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(record, field, value)

        await db.commit()
        await db.refresh(record)
        return record

    @staticmethod
    async def soft_delete_record(db: AsyncSession, record_id: uuid.UUID) -> bool:
        record = await db.get(FinancialRecord, record_id)
        if not record or record.is_deleted:
            return False
        record.is_deleted = True
        await db.commit()
        return True
