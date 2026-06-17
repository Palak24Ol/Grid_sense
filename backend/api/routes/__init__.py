"""
api/routes/__init__.py — Export all routers for registration in main.py.
"""

from backend.api.routes.health import router as health_router
from backend.api.routes.predict import router as predict_router
from backend.api.routes.incidents import router as incidents_router
from backend.api.routes.corridors import router as corridors_router
from backend.api.routes.forecast import router as forecast_router
from backend.api.routes.deploy import router as deploy_router
from backend.api.routes.flipkart import router as flipkart_router

__all__ = [
    "health_router",
    "predict_router",
    "incidents_router",
    "corridors_router",
    "forecast_router",
    "deploy_router",
    "flipkart_router",
]