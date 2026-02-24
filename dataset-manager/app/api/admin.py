"""
Admin API router — system statistics, user management, and cache management.
All endpoints require admin role.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.cassandra_client import CassandraClient
from app.core.config import settings
from app.core.security import get_current_user
from app.api.dependencies import db, logger

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


def require_admin(current_user: dict = Depends(get_current_user)):
    """Dependency that requires admin role"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/stats")
def get_admin_stats(current_user: dict = Depends(require_admin)):
    """Get system-wide statistics for admin dashboard"""
    try:
        # Count users
        users_result = db.execute("SELECT COUNT(*) as count FROM dataset_manager.users;")
        total_users = users_result.one().count if users_result.one is not None else 0
        try:
            row = users_result.one()
            total_users = row.count if row else 0
        except Exception:
            total_users = 0

        # Count datasets
        datasets_result = db.execute(
            "SELECT COUNT(*) as count FROM dataset_manager.datasets;"
        )
        try:
            row = datasets_result.one()
            total_datasets = row.count if row else 0
        except Exception:
            total_datasets = 0

        # Sum storage
        storage_result = db.execute(
            "SELECT SUM(size_bytes) as total_size FROM dataset_manager.datasets;"
        )
        try:
            row = storage_result.one()
            total_storage_bytes = row.total_size if row and row.total_size else 0
        except Exception:
            total_storage_bytes = 0

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
    except Exception as e:
        logger.error(f"Failed to get admin stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve admin statistics")


@router.get("/users")
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(require_admin),
):
    """List all users (admin only)"""
    try:
        result = db.execute("SELECT email, role, created_at FROM dataset_manager.users;")
        all_users = []
        for row in result:
            all_users.append(
                {
                    "email": row.email,
                    "role": row.role,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
            )

        # Sort by email
        all_users.sort(key=lambda u: u["email"])

        # Paginate
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
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(status_code=500, detail="Failed to list users")


@router.post("/cache/clear")
def clear_cache(current_user: dict = Depends(require_admin)):
    """Clear Redis cache (admin only)"""
    try:
        from app.integrations.redis_cache import RedisCacheService

        cache = RedisCacheService()
        cache.clear_all()
        cache.close()
        logger.info(f"Cache cleared by admin: {current_user.get('email')}")
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")
