"""
Redis-backed Pagination Cache for Dataset Manager

Caches paginated row results and dataset listings to avoid
redundant Cassandra queries. Keys are scoped by dataset, page,
page_size, and user role (since masking differs by role).
"""

import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


class PaginationCacheService:
    """Redis cache layer for paginated dataset queries"""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        password: str = None,
        db: int = 1,
        default_ttl: int = 300,
    ):
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", 6379))
        self.password = password or os.getenv("REDIS_PASSWORD")
        self.db = db
        self.default_ttl = default_ttl
        self.client = None
        self._enabled = False
        self._connect()

    def _connect(self):
        """Connect to Redis, gracefully degrade if unavailable"""
        try:
            import redis
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=2,
            )
            self.client.ping()
            self._enabled = True
            logger.info(f"Pagination cache connected to Redis: {self.host}:{self.port}")
        except Exception as e:
            self._enabled = False
            logger.warning(f"Redis unavailable, pagination cache disabled: {e}")

    @property
    def enabled(self) -> bool:
        return self._enabled and self.client is not None

    # ── Key builders ────────────────────────────────────────────

    @staticmethod
    def _rows_key(
        dataset_id: UUID, page: int, page_size: int, role: str,
        columns: Optional[str] = None,
    ) -> str:
        col_part = f":{columns}" if columns else ""
        return f"rows:{dataset_id}:{page}:{page_size}:{role}{col_part}"

    @staticmethod
    def _datasets_list_key(page: int, page_size: int, search: Optional[str] = None) -> str:
        search_hash = hashlib.md5((search or "").encode()).hexdigest()[:8]
        return f"datasets:list:{page}:{page_size}:{search_hash}"

    # ── Row page cache ──────────────────────────────────────────

    def get_rows_page(
        self,
        dataset_id: UUID,
        page: int,
        page_size: int,
        role: str,
        columns: Optional[str] = None,
    ) -> Optional[Tuple[List[Dict[str, Any]], int]]:
        """Get cached rows page. Returns (rows, total) or None on miss."""
        if not self.enabled:
            return None
        try:
            key = self._rows_key(dataset_id, page, page_size, role, columns)
            raw = self.client.get(key)
            if raw is None:
                return None
            data = json.loads(raw)
            return data["rows"], data["total"]
        except Exception as e:
            logger.warning(f"Cache get failed for rows page: {e}")
            return None

    def set_rows_page(
        self,
        dataset_id: UUID,
        page: int,
        page_size: int,
        role: str,
        rows: List[Dict[str, Any]],
        total: int,
        columns: Optional[str] = None,
        ttl: int = None,
    ) -> bool:
        """Cache a rows page result."""
        if not self.enabled:
            return False
        try:
            key = self._rows_key(dataset_id, page, page_size, role, columns)
            payload = json.dumps({"rows": rows, "total": total}, default=str)
            self.client.setex(key, ttl or self.default_ttl, payload)
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for rows page: {e}")
            return False

    # ── Dataset list cache ──────────────────────────────────────

    def get_datasets_list(
        self, page: int, page_size: int, search: Optional[str] = None
    ) -> Optional[Tuple[List[Dict[str, Any]], int]]:
        """Get cached datasets listing. Returns (datasets, total) or None."""
        if not self.enabled:
            return None
        try:
            key = self._datasets_list_key(page, page_size, search)
            raw = self.client.get(key)
            if raw is None:
                return None
            data = json.loads(raw)
            return data["datasets"], data["total"]
        except Exception as e:
            logger.warning(f"Cache get failed for datasets list: {e}")
            return None

    def set_datasets_list(
        self,
        page: int,
        page_size: int,
        datasets: List[Dict[str, Any]],
        total: int,
        search: Optional[str] = None,
        ttl: int = None,
    ) -> bool:
        """Cache a datasets list result."""
        if not self.enabled:
            return False
        try:
            key = self._datasets_list_key(page, page_size, search)
            payload = json.dumps({"datasets": datasets, "total": total}, default=str)
            self.client.setex(key, ttl or self.default_ttl, payload)
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for datasets list: {e}")
            return False

    # ── Invalidation ────────────────────────────────────────────

    def invalidate_dataset(self, dataset_id: UUID) -> int:
        """Invalidate all cached row pages for a specific dataset."""
        if not self.enabled:
            return 0
        try:
            deleted = 0
            pattern = f"rows:{dataset_id}:*"
            cursor = 0
            while True:
                cursor, keys = self.client.scan(cursor, match=pattern, count=200)
                if keys:
                    deleted += self.client.delete(*keys)
                if cursor == 0:
                    break
            logger.info(f"Invalidated {deleted} cache entries for dataset {dataset_id}")
            return deleted
        except Exception as e:
            logger.warning(f"Cache invalidation failed for dataset {dataset_id}: {e}")
            return 0

    def invalidate_datasets_list(self) -> int:
        """Invalidate all cached dataset listings."""
        if not self.enabled:
            return 0
        try:
            deleted = 0
            pattern = "datasets:list:*"
            cursor = 0
            while True:
                cursor, keys = self.client.scan(cursor, match=pattern, count=200)
                if keys:
                    deleted += self.client.delete(*keys)
                if cursor == 0:
                    break
            logger.info(f"Invalidated {deleted} dataset list cache entries")
            return deleted
        except Exception as e:
            logger.warning(f"Dataset list cache invalidation failed: {e}")
            return 0

    def invalidate_all_for_dataset(self, dataset_id: UUID) -> int:
        """Invalidate both row pages and dataset listings for a dataset."""
        count = self.invalidate_dataset(dataset_id)
        count += self.invalidate_datasets_list()
        return count
