from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.record import RecordRead


class SpendingSummary(BaseModel):
    total: Decimal
    daily_avg: Decimal


class TopCategory(BaseModel):
    category: str
    amount: Decimal
    pct_of_total: float


class MonthOverMonthComparison(BaseModel):
    income_change_pct: float
    expense_change_pct: float
    notable_changes: List[str]


class InsightAnomaly(BaseModel):
    date: date
    category: str
    amount: Decimal
    reason: str


class InsightReport(BaseModel):
    period: str
    spending_summary: SpendingSummary
    top_categories: List[TopCategory]
    mom_comparison: MonthOverMonthComparison
    anomalies: List[InsightAnomaly]


class NLQueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)


class NLQueryResponse(BaseModel):
    query_understood: bool
    filters_applied: Dict[str, str]
    result_value: Optional[Decimal]
    result_label: str
    raw_records: List[RecordRead]
