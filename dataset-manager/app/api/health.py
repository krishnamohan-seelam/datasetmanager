"""
Health check router
"""

from datetime import datetime

from fastapi import APIRouter

from app.cassandra_client import CassandraClient
from app.core.config import settings
from app.api.dependencies import logger

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    """Health check endpoint"""
    logger.info("Health check endpoint called")
    cassandra_status = "unhealthy"
    try:
        client = CassandraClient([settings.CASSANDRA_HOST], settings.CASSANDRA_PORT)
        client.execute("SELECT now() FROM system.local;")
        cassandra_status = "healthy"
    except Exception as e:
        logger.error(f"Cassandra health check failed: {e}")

    return {
        "status": "healthy",
        "cassandra": cassandra_status,
        "timestamp": datetime.utcnow().isoformat(),
    }
