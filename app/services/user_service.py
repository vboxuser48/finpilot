default_settings_hint = "Set DEFAULT_ADMIN_EMAIL/DEFAULT_ADMIN_PASSWORD in .env"
import uuid

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.security import get_password_hash, verify_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    """Business logic for managing platform users."""

    @staticmethod
    async def list_users(db: AsyncSession, page: int, page_size: int) -> dict:
        total = await db.scalar(select(func.count()).select_from(User))
        stmt = (
            select(User)
            .order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        items = result.scalars().all()
        return {"items": items, "total": total or 0}

    @staticmethod
    async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_user(db: AsyncSession, payload: UserCreate) -> User:
        existing = await db.execute(select(User).where(User.email == payload.email))
        if existing.scalar_one_or_none():
            raise ValueError("Email already registered")

        user = User(
            email=payload.email,
            full_name=payload.full_name,
            role=payload.role,
            is_active=payload.is_active,
            hashed_password=get_password_hash(payload.password),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def update_user(db: AsyncSession, user_id: uuid.UUID, payload: UserUpdate) -> User | None:
        user = await UserService.get_user(db, user_id)
        if not user:
            return None

        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.role is not None:
            user.role = payload.role
        if payload.is_active is not None:
            user.is_active = payload.is_active
        if payload.password:
            user.hashed_password = get_password_hash(payload.password)

        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def deactivate_user(db: AsyncSession, user_id: uuid.UUID) -> bool:
        user = await UserService.get_user(db, user_id)
        if not user:
            return False
        user.is_active = False
        await db.commit()
        return True

    @staticmethod
    async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    async def ensure_seed_admin(session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> None:
        """Seed a default admin user if the table is empty."""

        async with session_factory() as session:
            total = await session.scalar(select(func.count()).select_from(User))
            if total:
                return
            try:
                admin = User(
                    email=settings.default_admin_email,
                    full_name="FinPilot Administrator",
                    role=UserRole.admin,
                    is_active=True,
                    hashed_password=get_password_hash(settings.default_admin_password),
                )
                session.add(admin)
                await session.commit()
                logger.info("Seeded default admin user %s", settings.default_admin_email)
            except IntegrityError as exc:  # pragma: no cover - defensive
                await session.rollback()
                logger.error("Failed to seed admin: %s", exc)
                raise
