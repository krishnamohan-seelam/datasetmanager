"""
Redis Cache Service for Dataset Manager
Caches metadata and query results
"""

import logging
import json
import os
from typing import Any, Optional, List
import redis
from datetime import timedelta

logger = logging.getLogger(__name__)


class RedisCacheService:
    """Redis caching service for metadata and results"""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        password: str = None,
        db: int = 0,
        default_ttl: int = 3600,
    ):
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", 6379))
        self.password = password or os.getenv("REDIS_PASSWORD")
        self.db = db
        self.default_ttl = default_ttl
        self.client = None
        self._connect()

    def _connect(self):
        """Connect to Redis"""
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            self.client.ping()
            logger.info(f"Connected to Redis: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise

    def get(self, key: str) -> Any:
        """Get value from cache"""
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {str(e)}")
            return None

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        try:
            ttl = ttl or self.default_ttl
            self.client.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {str(e)}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed for {key}: {str(e)}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        return self.client.exists(key) > 0

    def get_dataset_metadata(self, dataset_id: str) -> Optional[dict]:
        """Get cached dataset metadata"""
        return self.get(f"dataset:{dataset_id}:metadata")

    def set_dataset_metadata(
        self, dataset_id: str, metadata: dict, ttl: int = None
    ) -> bool:
        """Cache dataset metadata"""
        return self.set(f"dataset:{dataset_id}:metadata", metadata, ttl)

    def invalidate_dataset(self, dataset_id: str):
        """Invalidate all cache for a dataset"""
        try:
            pattern = f"dataset:{dataset_id}:*"
            cursor = 0
            while True:
                cursor, keys = self.client.scan(cursor, match=pattern)
                if keys:
                    self.client.delete(*keys)
                if cursor == 0:
                    break
            logger.info(f"Invalidated cache for dataset {dataset_id}")
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {str(e)}")

    def get_user_datasets(self, user_email: str) -> Optional[List[dict]]:
        """Get cached user's datasets list"""
        return self.get(f"user:{user_email}:datasets")

    def set_user_datasets(
        self, user_email: str, datasets: List[dict], ttl: int = None
    ) -> bool:
        """Cache user's datasets list"""
        return self.set(f"user:{user_email}:datasets", datasets, ttl)

    def invalidate_user_cache(self, user_email: str):
        """Invalidate all cache for a user"""
        try:
            pattern = f"user:{user_email}:*"
            cursor = 0
            while True:
                cursor, keys = self.client.scan(cursor, match=pattern)
                if keys:
                    self.client.delete(*keys)
                if cursor == 0:
                    break
            logger.info(f"Invalidated cache for user {user_email}")
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {str(e)}")

    def get_query_result(self, query_hash: str) -> Optional[dict]:
        """Get cached query result"""
        return self.get(f"query:{query_hash}")

    def set_query_result(self, query_hash: str, result: dict, ttl: int = None) -> bool:
        """Cache query result"""
        return self.set(f"query:{query_hash}", result, ttl)

    def get_stats(self) -> dict:
        """Get Redis cache statistics"""
        try:
            info = self.client.info()
            return {
                "used_memory_mb": info.get("used_memory", 0) / 1024 / 1024,
                "keys_count": self.client.dbsize(),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
            }
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {str(e)}")
            return {}

    def clear_all(self):
        """Clear entire cache (USE WITH CAUTION)"""
        try:
            self.client.flushdb()
            logger.warning("Cache cleared")
        except Exception as e:
            logger.error(f"Failed to clear cache: {str(e)}")

    def close(self):
        """Close Redis connection"""
        if self.client:
            self.client.close()
            logger.info("Redis connection closed")
