"""
Redis-backed Pagination Cache for Dataset Manager

Caches paginated row results and dataset listings to avoid
redundant Cassandra queries. Keys are scoped by dataset, page,
page_size, user role, masking mode, batch, and a schema/masking revision.

Ownership: this service owns ALL row-page and dataset-listing caching.
``app.integrations.redis_cache.RedisCacheService`` is limited to
dataset-metadata / user-listing / query-result caching and delegates its
``invalidate_dataset`` here so one "dataset changed" signal clears both.
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PageRequest:
    """A row-page read request (replaces the dataset_id/page/page_size/role/columns clump)."""

    dataset_id: UUID
    page: int = 1
    page_size: int = 100
    user_role: str = "viewer"
    columns: Optional[Tuple[str, ...]] = None
    apply_masking: bool = True
    batch_id: Optional[UUID] = None

    @property
    def columns_key(self) -> Optional[str]:
        return ",".join(sorted(self.columns)) if self.columns else None


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
    def _rows_key(req: "PageRequest", schema_rev: str = "") -> str:
        """Build a row-page key.

        Segments: dataset, page, page_size, role, masking mode, batch, and a
        schema/masking revision fingerprint. ``apply_masking`` is part of the key
        so a masked and an unmasked read can never share an entry; ``schema_rev``
        changes whenever active columns or their masking rules change, so a stale
        entry is unreachable even before explicit invalidation runs.
        """
        mask_part = "m1" if req.apply_masking else "m0"
        batch_part = str(req.batch_id) if req.batch_id else "latest"
        rev_part = schema_rev or "0"
        col_key = req.columns_key
        col_part = f":{col_key}" if col_key else ""
        return (
            f"rows:{req.dataset_id}:{req.page}:{req.page_size}:{req.user_role}"
            f":{mask_part}:{batch_part}:{rev_part}{col_part}"
        )

    @staticmethod
    def _datasets_list_key(page: int, page_size: int, search: Optional[str] = None) -> str:
        search_hash = hashlib.md5((search or "").encode()).hexdigest()[:8]
        return f"datasets:list:{page}:{page_size}:{search_hash}"

    # ── Row page cache ──────────────────────────────────────────

    def get_rows_page(
        self, req: "PageRequest", schema_rev: str = ""
    ) -> Optional[Tuple[List[Dict[str, Any]], int]]:
        """Get cached rows page. Returns (rows, total) or None on miss."""
        if not self.enabled:
            return None
        try:
            raw = self.client.get(self._rows_key(req, schema_rev))
            if raw is None:
                return None
            data = json.loads(raw)
            return data["rows"], data["total"]
        except Exception as e:
            logger.warning(f"Cache get failed for rows page: {e}")
            return None

    def set_rows_page(
        self,
        req: "PageRequest",
        rows: List[Dict[str, Any]],
        total: int,
        schema_rev: str = "",
        ttl: int = None,
    ) -> bool:
        """Cache a rows page result."""
        if not self.enabled:
            return False
        try:
            key = self._rows_key(req, schema_rev)
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

    def _invalidate_pattern(self, pattern: str) -> int:
        """Scan-and-delete every key matching ``pattern``. Returns count deleted."""
        if not self.enabled:
            return 0
        try:
            deleted = 0
            cursor = 0
            while True:
                cursor, keys = self.client.scan(cursor, match=pattern, count=200)
                if keys:
                    deleted += self.client.delete(*keys)
                if cursor == 0:
                    break
            return deleted
        except Exception as e:
            logger.warning(f"Cache invalidation failed for pattern {pattern}: {e}")
            return 0

    def invalidate_dataset(self, dataset_id: UUID) -> int:
        """Single "dataset rows/schema/masking changed" invalidation entrypoint.

        Clears every cached row page for the dataset (all roles, masking modes,
        batches, revisions, column selections). Every mutation that changes a
        dataset's rows, schema, or masking must call this (or
        ``invalidate_all_for_dataset``). Currently wired: ``DatasetService.insert_rows``
        and ``DatasetService.update_masking_rule``; ``RedisCacheService.invalidate_dataset``
        also delegates here.
        TODO(Module 6): ``SchemaService.drop_column`` must call this.
        TODO(Module 7): ``BatchService.delete_batch`` / ``delete_all_batches`` must call this.
        """
        deleted = self._invalidate_pattern(f"rows:{dataset_id}:*")
        if self.enabled:
            logger.info(f"Invalidated {deleted} cache entries for dataset {dataset_id}")
        return deleted

    def invalidate_datasets_list(self) -> int:
        """Invalidate all cached dataset listings."""
        deleted = self._invalidate_pattern("datasets:list:*")
        if self.enabled:
            logger.info(f"Invalidated {deleted} dataset list cache entries")
        return deleted

    def invalidate_all_for_dataset(self, dataset_id: UUID) -> int:
        """Invalidate both row pages and dataset listings for a dataset."""
        count = self.invalidate_dataset(dataset_id)
        count += self.invalidate_datasets_list()
        return count
