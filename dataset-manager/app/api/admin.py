"""
Admin API router — system statistics, user management, and cache management.
All endpoints require admin role.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.core.exceptions import translate_domain_exceptions
from app.core.security import require_role
from app.schemas.common import Role
from app.api.dependencies import get_db, logger

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

# Reuses the shared require_role dependency (app/core/security.py) instead of
# a second, independently-maintained admin check.
require_admin = require_role([Role.ADMIN])


@router.get("/stats")
@translate_domain_exceptions
def get_admin_stats(current_user: dict = Depends(require_admin)):
    """Get system-wide statistics for admin dashboard"""
    db = get_db()

    # Count users
    row = db.execute("SELECT COUNT(*) as count FROM dataset_manager.users;").one()
    total_users = row.count if row else 0

    # Count datasets
    row = db.execute("SELECT COUNT(*) as count FROM dataset_manager.datasets;").one()
    total_datasets = row.count if row else 0

    # Sum storage
    row = db.execute("SELECT SUM(size_bytes) as total_size FROM dataset_manager.datasets;").one()
    total_storage_bytes = row.total_size if row and row.total_size else 0

    # System status based on Cassandra health
    system_status = "Healthy"
    try:
        db.execute("SELECT now() FROM system.local;")
    except Exception:
        system_status = "Degraded"

    return {
        "total_users": total_users,
        "total_datasets": total_datasets,
        "total_storage_bytes": total_storage_bytes,
        "system_status": system_status,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/users")
@translate_domain_exceptions
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(require_admin),
):
    """List all users (admin only).

    NOTE: still a full-table scan sorted/paginated in Python (Normal #4 in
    the code review) — left as-is in this pass since a correct server-side
    fix needs a secondary index or materialized view keyed by email, which is
    a larger schema change than this phase covers. Acceptable for an
    admin-only, low-traffic endpoint today; revisit if the user table grows
    large enough for this to matter.
    """
    db = get_db()
    result = db.execute("SELECT email, role, created_at FROM dataset_manager.users;")
    all_users = [
        {
            "email": row.email,
            "role": row.role,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in result
    ]

    all_users.sort(key=lambda u: u["email"])

    total = len(all_users)
    start = (page - 1) * page_size
    end = start + page_size
    items = all_users[start:end]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 1,
        "items": items,
    }


@router.post("/cache/clear")
@translate_domain_exceptions
def clear_cache(current_user: dict = Depends(require_admin)):
    """Clear Redis cache (admin only)"""
    from app.integrations.redis_cache import RedisCacheService

    cache = RedisCacheService()
    cache.clear_all()
    cache.close()
    logger.info(f"Cache cleared by admin: {current_user.get('email')}")
    return {"message": "Cache cleared successfully"}
