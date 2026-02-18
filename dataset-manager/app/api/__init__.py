"""
API package — aggregates all routers for inclusion in the main app.
"""

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.datasets import router as datasets_router
from app.api.rows import router as rows_router
from app.api.permissions import router as permissions_router

all_routers = [
    health_router,
    auth_router,
    datasets_router,
    rows_router,
    permissions_router,
]
