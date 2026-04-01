from datetime import date
from decimal import Decimal
from typing import List

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    total_income: Decimal = Field(default=Decimal("0"))
    total_expenses: Decimal = Field(default=Decimal("0"))
    net_balance: Decimal = Field(default=Decimal("0"))
    record_count: int = 0


class CategorySummary(BaseModel):
    category: str
    total: Decimal
    percentage: float


class MonthlyTrend(BaseModel):
    month: str
    income: Decimal
    expenses: Decimal
    net: Decimal


class RecentTransaction(BaseModel):
    id: str
    amount: Decimal
    type: str
    category: str
    date: date


class DashboardSummaryPayload(BaseModel):
    summary: DashboardSummary
    by_category: List[CategorySummary]
    monthly_trend: List[MonthlyTrend]
    recent: List[RecentTransaction]
