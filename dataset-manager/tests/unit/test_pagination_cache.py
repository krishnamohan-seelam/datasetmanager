"""
Unit tests for PaginationCacheService
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.pagination_cache import PaginationCacheService


class TestPaginationCacheService:
    """Tests for Redis-backed pagination cache"""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client"""
        with patch.object(PaginationCacheService, "_connect"):
            service = PaginationCacheService.__new__(PaginationCacheService)
            service.client = MagicMock()
            service._enabled = True
            service.default_ttl = 300
            service.host = "localhost"
            service.port = 6379
            service.password = None
            service.db = 1
            yield service

    @pytest.fixture
    def disabled_cache(self):
        """Create a disabled cache (Redis unavailable)"""
        with patch.object(PaginationCacheService, "_connect"):
            service = PaginationCacheService.__new__(PaginationCacheService)
            service.client = None
            service._enabled = False
            service.default_ttl = 300
            service.host = "localhost"
            service.port = 6379
            service.password = None
            service.db = 1
            yield service

    # ── Row page caching ────────────────────────────────────────

    def test_rows_cache_miss(self, mock_redis):
        """Cache miss returns None"""
        mock_redis.client.get.return_value = None
        dataset_id = uuid4()

        result = mock_redis.get_rows_page(dataset_id, 1, 100, "viewer")

        assert result is None
        mock_redis.client.get.assert_called_once()

    def test_rows_cache_hit(self, mock_redis):
        """Cache hit returns (rows, total)"""
        dataset_id = uuid4()
        cached_data = {"rows": [{"name": "Alice"}], "total": 50}
        mock_redis.client.get.return_value = json.dumps(cached_data)

        result = mock_redis.get_rows_page(dataset_id, 1, 100, "viewer")

        assert result is not None
        rows, total = result
        assert rows == [{"name": "Alice"}]
        assert total == 50

    def test_rows_cache_set(self, mock_redis):
        """Setting rows cache calls setex with correct TTL"""
        dataset_id = uuid4()
        rows = [{"name": "Bob"}, {"name": "Carol"}]

        success = mock_redis.set_rows_page(dataset_id, 1, 100, "viewer", rows, 200)

        assert success is True
        mock_redis.client.setex.assert_called_once()
        args = mock_redis.client.setex.call_args
        assert args[0][1] == 300  # default TTL

    def test_rows_cache_custom_ttl(self, mock_redis):
        """Setting rows cache with custom TTL"""
        dataset_id = uuid4()

        mock_redis.set_rows_page(dataset_id, 1, 100, "admin", [{"x": 1}], 10, ttl=60)

        args = mock_redis.client.setex.call_args
        assert args[0][1] == 60

    def test_rows_cache_with_columns(self, mock_redis):
        """Cache key includes columns parameter"""
        dataset_id = uuid4()

        mock_redis.get_rows_page(dataset_id, 1, 100, "viewer", columns="email,name")

        key_arg = mock_redis.client.get.call_args[0][0]
        assert "email,name" in key_arg

    # ── Dataset list caching ────────────────────────────────────

    def test_datasets_list_cache_miss(self, mock_redis):
        """Dataset list cache miss returns None"""
        mock_redis.client.get.return_value = None

        result = mock_redis.get_datasets_list(1, 100)

        assert result is None

    def test_datasets_list_cache_hit(self, mock_redis):
        """Dataset list cache hit returns (datasets, total)"""
        cached_data = {"datasets": [{"id": "abc", "name": "TestDS"}], "total": 1}
        mock_redis.client.get.return_value = json.dumps(cached_data)

        result = mock_redis.get_datasets_list(1, 100)

        assert result is not None
        datasets, total = result
        assert len(datasets) == 1
        assert total == 1

    def test_datasets_list_cache_set(self, mock_redis):
        """Setting datasets list cache works"""
        datasets = [{"id": "x1", "name": "DS1"}]

        success = mock_redis.set_datasets_list(1, 100, datasets, 5)

        assert success is True
        mock_redis.client.setex.assert_called_once()

    def test_datasets_list_with_search(self, mock_redis):
        """Dataset list cache key varies by search query"""
        mock_redis.client.get.return_value = None

        mock_redis.get_datasets_list(1, 100, search="finance")
        key1 = mock_redis.client.get.call_args[0][0]

        mock_redis.get_datasets_list(1, 100, search="health")
        key2 = mock_redis.client.get.call_args[0][0]

        assert key1 != key2

    # ── Invalidation ────────────────────────────────────────────

    def test_invalidate_dataset(self, mock_redis):
        """Invalidate removes row cache entries for a dataset"""
        dataset_id = uuid4()
        mock_redis.client.scan.return_value = (0, [f"rows:{dataset_id}:1:100:viewer"])
        mock_redis.client.delete.return_value = 1

        count = mock_redis.invalidate_dataset(dataset_id)

        assert count == 1
        mock_redis.client.delete.assert_called_once()

    def test_invalidate_datasets_list(self, mock_redis):
        """Invalidate removes all dataset list entries"""
        mock_redis.client.scan.return_value = (0, ["datasets:list:1:100:abc123"])
        mock_redis.client.delete.return_value = 1

        count = mock_redis.invalidate_datasets_list()

        assert count == 1

    def test_invalidate_all_for_dataset(self, mock_redis):
        """Invalidate all removes both row pages and list entries"""
        dataset_id = uuid4()
        mock_redis.client.scan.return_value = (0, ["key1"])
        mock_redis.client.delete.return_value = 1

        count = mock_redis.invalidate_all_for_dataset(dataset_id)

        assert count == 2  # 1 from invalidate_dataset + 1 from invalidate_datasets_list

    # ── Graceful degradation ────────────────────────────────────

    def test_disabled_cache_returns_none(self, disabled_cache):
        """Disabled cache always returns None on get"""
        result = disabled_cache.get_rows_page(uuid4(), 1, 100, "viewer")
        assert result is None

    def test_disabled_cache_set_returns_false(self, disabled_cache):
        """Disabled cache set returns False"""
        result = disabled_cache.set_rows_page(uuid4(), 1, 100, "viewer", [], 0)
        assert result is False

    def test_disabled_cache_invalidate_returns_zero(self, disabled_cache):
        """Disabled cache invalidation returns 0"""
        count = disabled_cache.invalidate_dataset(uuid4())
        assert count == 0


class TestCacheKeyGeneration:
    """Tests for cache key format and uniqueness"""

    def test_rows_key_format(self):
        """Row key contains all parameters"""
        dataset_id = uuid4()
        key = PaginationCacheService._rows_key(dataset_id, 2, 50, "admin")
        assert f"rows:{dataset_id}:2:50:admin" == key

    def test_rows_key_with_columns(self):
        """Row key includes column suffix"""
        dataset_id = uuid4()
        key = PaginationCacheService._rows_key(dataset_id, 1, 100, "viewer", "email,name")
        assert key.endswith(":email,name")

    def test_rows_key_role_isolation(self):
        """Different roles produce different cache keys"""
        dataset_id = uuid4()
        k1 = PaginationCacheService._rows_key(dataset_id, 1, 100, "admin")
        k2 = PaginationCacheService._rows_key(dataset_id, 1, 100, "viewer")
        assert k1 != k2

    def test_datasets_list_key_search_isolation(self):
        """Different search queries produce different keys"""
        k1 = PaginationCacheService._datasets_list_key(1, 100, "foo")
        k2 = PaginationCacheService._datasets_list_key(1, 100, "bar")
        assert k1 != k2
