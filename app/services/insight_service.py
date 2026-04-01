from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.record import FinancialRecord, RecordType
from app.models.user import User, UserRole
from app.schemas.insights import (
    InsightAnomaly,
    InsightReport,
    MonthOverMonthComparison,
    NLQueryRequest,
    NLQueryResponse,
    SpendingSummary,
    TopCategory,
)
from app.schemas.record import RecordRead


class InsightService:
    """Insight generation and NL query handling."""

    @staticmethod
    def _base_query(user: User) -> Select[tuple[FinancialRecord]]:
        stmt = select(FinancialRecord).where(FinancialRecord.is_deleted.is_(False))
        if user.role == UserRole.viewer:
            stmt = stmt.where(FinancialRecord.user_id == user.id)
        return stmt

    @staticmethod
    def _period_last_month() -> Tuple[date, date]:
        today = date.today().replace(day=1)
        last_month_end = today - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start, last_month_end

    @staticmethod
    def _period_previous_month(start: date) -> Tuple[date, date]:
        prev_end = start - timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        return prev_start, prev_end

    @staticmethod
    async def _load_records(
        db: AsyncSession,
        user: User,
        start: date,
        end: date,
        record_type: Optional[RecordType] = None,
        category_like: Optional[str] = None,
    ) -> List[FinancialRecord]:
        stmt = InsightService._base_query(user).where(
            FinancialRecord.date >= start,
            FinancialRecord.date <= end,
        )
        if record_type:
            stmt = stmt.where(FinancialRecord.type == record_type)
        if category_like:
            stmt = stmt.where(FinancialRecord.category.ilike(f"%{category_like}%"))
        stmt = stmt.order_by(FinancialRecord.date)
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    def _spending_summary(records: List[FinancialRecord], start: date, end: date) -> SpendingSummary:
        expense_total = sum(Decimal(record.amount) for record in records if record.type == RecordType.expense)
        days = (end - start).days + 1
        if days:
            daily_avg = (expense_total / days).quantize(Decimal("0.01"))
        else:
            daily_avg = Decimal("0.00")
        return SpendingSummary(total=expense_total, daily_avg=daily_avg)

    @staticmethod
    def _top_categories(records: List[FinancialRecord]) -> List[TopCategory]:
        totals: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for record in records:
            if record.type == RecordType.expense:
                totals[record.category] += Decimal(record.amount)
        grand_total = sum(totals.values()) or Decimal("1")
        sorted_rows = sorted(totals.items(), key=lambda item: item[1], reverse=True)
        return [
            TopCategory(
                category=category,
                amount=amount,
                pct_of_total=float((amount / grand_total) * 100),
            )
            for category, amount in sorted_rows[:5]
        ]

    @staticmethod
    def _mom_comparison(
        current_income: Decimal,
        current_expenses: Decimal,
        previous_income: Decimal,
        previous_expenses: Decimal,
    ) -> MonthOverMonthComparison:
        def pct_change(current: Decimal, previous: Decimal) -> float:
            if previous == 0:
                return 100.0 if current > 0 else 0.0
            return float(((current - previous) / previous) * 100)

        notable: List[str] = []
        if pct_change(current_expenses, previous_expenses) > 20:
            notable.append("Expenses increased more than 20% over last month")
        if pct_change(current_income, previous_income) < -10:
            notable.append("Income dropped more than 10% vs last month")

        return MonthOverMonthComparison(
            income_change_pct=round(pct_change(current_income, previous_income), 2),
            expense_change_pct=round(pct_change(current_expenses, previous_expenses), 2),
            notable_changes=notable,
        )

    @staticmethod
    def _detect_anomalies(records: List[FinancialRecord]) -> List[InsightAnomaly]:
        if not records:
            return []
        category_amounts: Dict[str, List[Decimal]] = defaultdict(list)
        for record in records:
            if record.type == RecordType.expense:
                category_amounts[record.category].append(Decimal(record.amount))

        anomalies: List[InsightAnomaly] = []
        for record in records:
            if record.type != RecordType.expense:
                continue
            amounts = category_amounts[record.category]
            if not amounts:
                continue
            avg = sum(amounts) / len(amounts)
            if Decimal(record.amount) > avg * Decimal("2.5"):
                anomalies.append(
                    InsightAnomaly(
                        date=record.date,
                        category=record.category,
                        amount=Decimal(record.amount),
                        reason="{:.1f}x above the category average".format(
                            Decimal(record.amount) / (avg or Decimal("1"))
                        ),
                    )
                )
        return anomalies[:5]

    @staticmethod
    def _aggregate(records: List[FinancialRecord]) -> Dict[str, Decimal]:
        totals = {"income": Decimal("0"), "expenses": Decimal("0")}
        for record in records:
            if record.type == RecordType.income:
                totals["income"] += Decimal(record.amount)
            else:
                totals["expenses"] += Decimal(record.amount)
        return totals

    @staticmethod
    async def generate_report(db: AsyncSession, user: User) -> InsightReport:
        current_start, current_end = InsightService._period_last_month()
        previous_start, previous_end = InsightService._period_previous_month(current_start)

        current_records = await InsightService._load_records(db, user, current_start, current_end)
        previous_records = await InsightService._load_records(db, user, previous_start, previous_end)

        current_totals = InsightService._aggregate(current_records)
        previous_totals = InsightService._aggregate(previous_records)
        summary = InsightService._spending_summary(current_records, current_start, current_end)
        categories = InsightService._top_categories(current_records)
        comparison = InsightService._mom_comparison(
            current_totals["income"],
            current_totals["expenses"],
            previous_totals["income"],
            previous_totals["expenses"],
        )
        anomalies = InsightService._detect_anomalies(current_records)

        return InsightReport(
            period=current_start.strftime("%Y-%m"),
            spending_summary=summary,
            top_categories=categories,
            mom_comparison=comparison,
            anomalies=anomalies,
        )

    @staticmethod
    def parse_nl_query(query: str) -> dict:
        text = query.lower()
        period: Tuple[date, date] | None = None
        today = date.today()
        if "last month" in text:
            period = InsightService._period_last_month()
        elif "this month" in text:
            start = today.replace(day=1)
            period = (start, today)
        elif "last 3 months" in text or "last three months" in text:
            start = today - timedelta(days=90)
            period = (start, today)
        else:
            period = (today - timedelta(days=30), today)

        record_type = None
        if any(keyword in text for keyword in ["spend", "expense", "spent"]):
            record_type = RecordType.expense
        elif any(keyword in text for keyword in ["income", "earned", "revenue"]):
            record_type = RecordType.income

        category = None
        known_categories = [
            "food",
            "rent",
            "salary",
            "travel",
            "entertainment",
            "utilities",
            "health",
            "education",
        ]
        for candidate in known_categories:
            if candidate in text:
                category = candidate
                break

        return {
            "period": period,
            "record_type": record_type,
            "category": category,
        }

    @staticmethod
    async def run_nl_query(
        db: AsyncSession,
        user: User,
        payload: NLQueryRequest,
    ) -> NLQueryResponse:
        parsed = InsightService.parse_nl_query(payload.query)
        start, end = parsed["period"]
        records = await InsightService._load_records(
            db,
            user,
            start,
            end,
            record_type=parsed["record_type"],
            category_like=parsed["category"],
        )
        total_value = sum(Decimal(record.amount) for record in records)
        label_parts = []
        if parsed["record_type"] == RecordType.expense:
            label_parts.append("Total spending")
        elif parsed["record_type"] == RecordType.income:
            label_parts.append("Total income")
        else:
            label_parts.append("Net activity")
        if parsed["category"]:
            label_parts.append(f"for {parsed['category']}")
        label_parts.append(f"between {start} and {end}")

        return NLQueryResponse(
            query_understood=bool(payload.query.strip()),
            filters_applied={
                "start": start.isoformat(),
                "end": end.isoformat(),
                "type": parsed["record_type"].value if parsed["record_type"] else "all",
                "category": parsed["category"] or "all",
            },
            result_value=total_value,
            result_label=" ".join(label_parts),
            raw_records=[RecordRead.model_validate(record) for record in records],
        )
