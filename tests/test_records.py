from datetime import date
from decimal import Decimal

import pytest

from app.models.record import FinancialRecord, RecordType
from app.models.user import User, UserRole
from app.schemas.record import RecordFilter
from app.services.record_service import RecordService


@pytest.mark.anyio
async def test_record_listing_filters_by_category(db_session):
    user = User(email="viewer@example.com", full_name="Viewer", role=UserRole.viewer, hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    record_food = FinancialRecord(
        user_id=user.id,
        amount=Decimal("50"),
        type=RecordType.expense,
        category="Food",
        date=date(2025, 3, 10),
    )
    record_rent = FinancialRecord(
        user_id=user.id,
        amount=Decimal("1200"),
        type=RecordType.expense,
        category="Rent",
        date=date(2025, 3, 5),
    )
    db_session.add_all([record_food, record_rent])
    await db_session.commit()

    filters = RecordFilter(category="food")
    result = await RecordService.list_records(db_session, user, filters)

    assert result["total"] == 1
    assert result["items"][0].category == "Food"


@pytest.mark.anyio
async def test_soft_delete_marks_record(db_session):
    user = User(email="admin@example.com", full_name="Admin", role=UserRole.admin, hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    record = FinancialRecord(
        user_id=user.id,
        amount=Decimal("200"),
        type=RecordType.income,
        category="Bonus",
        date=date(2025, 3, 1),
    )
    db_session.add(record)
    await db_session.commit()

    success = await RecordService.soft_delete_record(db_session, record.id)
    await db_session.refresh(record)

    assert success is True
    assert record.is_deleted is True
