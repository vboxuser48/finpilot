import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes import auth, dashboard, insights, records, users
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import AsyncSessionMaker, async_engine
from app.services.user_service import UserService

settings = get_settings()
logger.remove()
logger.add(sys.stdout, level=settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Bootstrapping FinPilot AI")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await UserService.ensure_seed_admin(AsyncSessionMaker, settings)
    yield
    await async_engine.dispose()
    logger.info("FinPilot AI shutdown complete")


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.bind(path=request.url.path, method=request.method).info("Request received")
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled exception")
        raise
    logger.bind(status=response.status_code).info("Request completed")
    return response


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(records.router)
app.include_router(dashboard.router)
app.include_router(insights.router)


@app.get("/health", summary="Health check", tags=["meta"])
async def health_check() -> dict:
    """Simple health endpoint for uptime monitoring."""

    return {"status": "ok"}
