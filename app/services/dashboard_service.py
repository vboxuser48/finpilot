from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import List

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.record import FinancialRecord, RecordType
from app.models.user import User, UserRole
from app.schemas.dashboard import CategorySummary, DashboardSummary, MonthlyTrend, RecentTransaction


class DashboardService:
    """Aggregation logic powering dashboard endpoints."""

    @staticmethod
    def _base_scope(user: User) -> Select[tuple[FinancialRecord]]:
        stmt = select(FinancialRecord).where(FinancialRecord.is_deleted.is_(False))
        if user.role == UserRole.viewer:
            stmt = stmt.where(FinancialRecord.user_id == user.id)
        return stmt

    @staticmethod
    async def summary(db: AsyncSession, user: User) -> DashboardSummary:
        stmt = DashboardService._base_scope(user).with_only_columns(
            func.coalesce(
                func.sum(
                    case((FinancialRecord.type == RecordType.income, FinancialRecord.amount), else_=0)
                ),
                0,
            ).label("income"),
            func.coalesce(
                func.sum(
                    case((FinancialRecord.type == RecordType.expense, FinancialRecord.amount), else_=0)
                ),
                0,
            ).label("expenses"),
            func.count(FinancialRecord.id).label("count"),
        )
        result = await db.execute(stmt)
        income, expenses, count = result.one()
        return DashboardSummary(
            total_income=Decimal(income or 0),
            total_expenses=Decimal(expenses or 0),
            net_balance=Decimal(income or 0) - Decimal(expenses or 0),
            record_count=count or 0,
        )

    @staticmethod
    async def by_category(db: AsyncSession, user: User) -> List[CategorySummary]:
        start_date = date.today() - timedelta(days=90)
        stmt = (
            DashboardService._base_scope(user)
            .where(FinancialRecord.date >= start_date, FinancialRecord.type == RecordType.expense)
            .with_only_columns(
                FinancialRecord.category,
                func.sum(FinancialRecord.amount).label("total"),
            )
            .group_by(FinancialRecord.category)
            .order_by(func.sum(FinancialRecord.amount).desc())
        )
        totals = await db.execute(stmt)
        rows = totals.all()
        grand_total = sum(Decimal(row.total or 0) for row in rows)
        denominator = grand_total if grand_total > 0 else Decimal("1")
        return [
            CategorySummary(
                category=row.category,
                total=Decimal(row.total or 0),
                percentage=round(float(Decimal(row.total or 0) / denominator * 100), 2),
            )
            for row in rows
        ]

    @staticmethod
    async def monthly_trend(db: AsyncSession, user: User) -> List[MonthlyTrend]:
        today = date.today().replace(day=1)
        start_date = today - timedelta(days=365)
        stmt = (
            DashboardService._base_scope(user)
            .where(FinancialRecord.date >= start_date)
            .order_by(FinancialRecord.date)
        )
        result = await db.execute(stmt)
        records = result.scalars().all()

        buckets: dict[str, dict[str, Decimal]] = defaultdict(lambda: {
            "income": Decimal("0"),
            "expenses": Decimal("0"),
        })
        for record in records:
            key = record.date.strftime("%Y-%m")
            amount = Decimal(record.amount)
            if record.type == RecordType.income:
                buckets[key]["income"] += amount
            else:
                buckets[key]["expenses"] += amount

        months = sorted(buckets.keys())[-12:]
        return [
            MonthlyTrend(
                month=month,
                income=buckets[month]["income"],
                expenses=buckets[month]["expenses"],
                net=buckets[month]["income"] - buckets[month]["expenses"],
            )
            for month in months
        ]

    @staticmethod
    async def recent_transactions(db: AsyncSession, user: User, limit: int) -> List[RecentTransaction]:
        stmt = (
            DashboardService._base_scope(user)
            .order_by(FinancialRecord.date.desc(), FinancialRecord.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        records = result.scalars().all()
        return [
            RecentTransaction(
                id=str(record.id),
                amount=Decimal(record.amount),
                type=record.type.value,
                category=record.category,
                date=record.date,
            )
            for record in records
        ]
