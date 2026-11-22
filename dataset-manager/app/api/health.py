"""
Health check router
"""

from datetime import datetime

from fastapi import APIRouter

from app.api.dependencies import get_db, logger

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    """Health check endpoint"""
    logger.info("Health check endpoint called")
    cassandra_status = "unhealthy"
    try:
        # Reuses the shared CassandraClient singleton instead of constructing
        # a new one per request — repeated health-check traffic no longer
        # grows the Cassandra connection count.
        client = get_db()
        client.execute("SELECT now() FROM system.local;")
        cassandra_status = "healthy"
    except Exception as e:
        logger.error(f"Cassandra health check failed: {e}")

    return {
        "status": "healthy",
        "cassandra": cassandra_status,
        "timestamp": datetime.utcnow().isoformat(),
    }
