"""
main.py — GridSense FastAPI application factory.

Start with:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

Or from project root:
    python -m uvicorn backend.main:app --reload
"""

import warnings
warnings.filterwarnings("ignore", message=".*NumPy.*")
warnings.filterwarnings("ignore", message=".*numpy.*")
warnings.filterwarnings("ignore", category=UserWarning, module="xgboost")

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.config import get_settings
from backend.core.middleware import register_middleware
from backend.core.logging import get_logger
from backend.api.routes.health import router as health_router
from backend.api.routes.predict import router as predict_router
from backend.api.routes.incidents import router as incidents_router
from backend.api.routes.corridors import router as corridors_router
from backend.api.routes.forecast import router as forecast_router
from backend.api.routes.deploy import router as deploy_router
from backend.api.routes.logistics import router as logistics_router
from backend.api.routes.blackspot import router as blackspot_router
from backend.api.routes.surge import router as surge_router

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: warm artifact cache. Shutdown: nothing to clean up."""
    settings = get_settings()
    logger.info(f"GridSense backend starting (env={settings.ENV})")

    from backend.services.artifact_loader import get_artifacts
    arts = get_artifacts()

    if arts.all_core_loaded:
        logger.info("✅ All ML artifacts loaded")
    else:
        logger.warning("⚠️  Some ML artifacts missing — running in mock/degraded mode")

    yield
    logger.info("GridSense backend shutting down")

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="GridSense API",
        description="Event-driven congestion prediction API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    register_middleware(app)

    prefix = "/api/v1"
    app.include_router(health_router)
    app.include_router(incidents_router,  prefix=prefix)
    app.include_router(corridors_router,  prefix=prefix)
    app.include_router(predict_router,    prefix=prefix)
    app.include_router(forecast_router,   prefix=prefix)
    app.include_router(deploy_router,     prefix=prefix)
    app.include_router(logistics_router,  prefix=prefix)
    app.include_router(blackspot_router,  prefix=prefix)
    app.include_router(surge_router,      prefix=prefix)

    return app


app = create_app()