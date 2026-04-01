from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.record import FinancialRecord, RecordType
from app.models.user import User, UserRole
from app.schemas.insights import NLQueryRequest
from app.services.insight_service import InsightService


def test_parse_nl_query_detects_category_and_type():
    query = "Show food spending for last month"
    parsed = InsightService.parse_nl_query(query)
    assert parsed["record_type"] == RecordType.expense
    assert parsed["category"] == "food"
    assert parsed["period"] is not None


@pytest.mark.anyio
async def test_run_nl_query_returns_results(db_session):
    user = User(email="analyst@example.com", full_name="Analyst", role=UserRole.analyst, hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    today = date.today()
    last_month_day = (today.replace(day=1) - timedelta(days=1)).replace(day=15)

    record = FinancialRecord(
        user_id=user.id,
        amount=Decimal("250"),
        type=RecordType.expense,
        category="Food",
        date=last_month_day,
    )
    db_session.add(record)
    await db_session.commit()

    payload = NLQueryRequest(query="How much did I spend on food last month?")
    response = await InsightService.run_nl_query(db_session, user, payload)

    assert response.query_understood is True
    assert response.result_value == Decimal("250")
    assert response.raw_records
