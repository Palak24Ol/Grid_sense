"""
api/routes/__init__.py — Export all routers for registration in main.py.

Note: main.py currently imports each router module directly rather than
from this package's __all__ (that's the pattern actually exercised at
runtime). This file is kept in sync anyway since other code may import
from here in the future, and a stale __all__ is worse than no __all__.
"""

from backend.api.routes.health import router as health_router
from backend.api.routes.predict import router as predict_router
from backend.api.routes.incidents import router as incidents_router
from backend.api.routes.corridors import router as corridors_router
from backend.api.routes.forecast import router as forecast_router
from backend.api.routes.deploy import router as deploy_router
from backend.api.routes.logistics import router as logistics_router
from backend.api.routes.blackspot import router as blackspot_router
from backend.api.routes.surge import router as surge_router

__all__ = [
    "health_router",
    "predict_router",
    "incidents_router",
    "corridors_router",
    "forecast_router",
    "deploy_router",
    "logistics_router",
    "blackspot_router",
    "surge_router",
]