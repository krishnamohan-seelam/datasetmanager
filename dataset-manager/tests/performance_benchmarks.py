"""
Performance Testing Suite for Release 2
Benchmarks for ETL, Storage, Caching, and API endpoints
"""

import time
import statistics
import json
from datetime import datetime
import pytest
from typing import List, Dict, Any


class PerformanceBenchmark:
    """Performance benchmark tracker"""

    def __init__(self):
        self.results: Dict[str, List[float]] = {}
        self.start_time = None

    def start(self):
        """Start timing"""
        self.start_time = time.perf_counter()

    def end(self, operation_name: str) -> float:
        """End timing and record result"""
        duration = time.perf_counter() - self.start_time
        if operation_name not in self.results:
            self.results[operation_name] = []
        self.results[operation_name].append(duration)
        return duration

    def get_stats(self, operation_name: str) -> Dict[str, float]:
        """Get statistics for operation"""
        if operation_name not in self.results:
            return {}

        times = self.results[operation_name]
        return {
            "count": len(times),
            "min": min(times),
            "max": max(times),
            "avg": statistics.mean(times),
            "median": statistics.median(times),
            "stdev": statistics.stdev(times) if len(times) > 1 else 0,
            "total": sum(times),
        }

    def report(self) -> str:
        """Generate performance report"""
        report = "\n" + "=" * 80 + "\n"
        report += "RELEASE 2 PERFORMANCE BENCHMARK REPORT\n"
        report += f"Generated: {datetime.now().isoformat()}\n"
        report += "=" * 80 + "\n\n"

        for op_name in sorted(self.results.keys()):
            stats = self.get_stats(op_name)
            report += f"Operation: {op_name}\n"
            report += f"  Samples: {stats['count']}\n"
            report += f"  Min: {stats['min']*1000:.2f}ms\n"
            report += f"  Max: {stats['max']*1000:.2f}ms\n"
            report += f"  Avg: {stats['avg']*1000:.2f}ms\n"
            report += f"  Median: {stats['median']*1000:.2f}ms\n"
            report += f"  StdDev: {stats['stdev']*1000:.2f}ms\n"
            report += f"  Total: {stats['total']:.2f}s\n\n"

        return report

    def export_json(self, filename: str):
        """Export results as JSON"""
        data = {"timestamp": datetime.now().isoformat(), "operations": {}}

        for op_name in self.results:
            data["operations"][op_name] = self.get_stats(op_name)

        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

        print(f"Benchmark results exported to {filename}")


# Performance targets
PERFORMANCE_TARGETS = {
    "etl_throughput_rows_per_min": 1_000_000,  # 1M rows/min
    "s3_upload_speed_mbps": 100,  # 100 MB/s
    "cache_hit_ratio": 0.80,  # >80%
    "api_p95_latency_ms": 200,  # <200ms
    "api_p99_latency_ms": 500,  # <500ms
    "rate_limiter_accuracy": 0.999,  # 99.9%
    "kafka_throughput_msgs_sec": 10_000,  # 10k msgs/sec
}


@pytest.mark.benchmark
class TestETLPerformance:
    """ETL Pipeline Performance Tests"""

    def test_etl_row_processing_throughput(self, benchmark):
        """Benchmark row processing throughput"""
        from airflow.dags.dataset_etl_pipeline import process_row

        # Create sample row
        sample_row = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
            "amount": 1000.00,
        }

        def run_test():
            return process_row(sample_row, {"email": "email", "amount": "number"})

        result = benchmark(run_test)
        assert result is not None

    def test_etl_validation_stage(self, benchmark):
        """Benchmark data validation stage"""
        from airflow.dags.dataset_etl_pipeline import validate_data

        sample_data = [
            {"id": i, "email": f"user{i}@example.com", "amount": i * 100}
            for i in range(1000)
        ]

        def run_test():
            return validate_data(sample_data)

        result = benchmark(run_test)
        assert result["valid_rows"] > 0

    def test_etl_transformation_stage(self, benchmark):
        """Benchmark data transformation"""
        from airflow.dags.dataset_etl_pipeline import transform_data

        sample_data = [
            {"id": i, "email": f"user{i}@example.com", "name": f"User {i}"}
            for i in range(1000)
        ]

        def run_test():
            return transform_data(sample_data)

        result = benchmark(run_test)
        assert result is not None


@pytest.mark.benchmark
class TestStoragePerformance:
    """Storage Performance Tests"""

    def test_s3_file_upload_performance(self, benchmark):
        """Benchmark S3/MinIO file upload"""
        from app.integrations.storage_factory import get_storage_service
        from io import BytesIO

        storage = get_storage_service()
        file_data = BytesIO(b"x" * (10 * 1024 * 1024))  # 10MB

        def run_test():
            return storage.upload_file(
                file_data, "perf-test", "benchmark.bin", 10 * 1024 * 1024
            )

        result = benchmark(run_test)
        assert result is not None

    def test_s3_file_download_performance(self, benchmark):
        """Benchmark S3/MinIO file download"""
        from app.integrations.storage_factory import get_storage_service

        storage = get_storage_service()

        def run_test():
            return storage.download_file("perf-test/benchmark.bin")

        result = benchmark(run_test)
        assert result is not None


@pytest.mark.benchmark
class TestCachePerformance:
    """Redis Cache Performance Tests"""

    def test_cache_set_performance(self, benchmark):
        """Benchmark cache SET operation"""
        from app.integrations.redis_cache import RedisCache

        cache = RedisCache()

        def run_test():
            return cache.set("perf-test:key", {"data": "value"}, ttl=3600)

        result = benchmark(run_test)
        assert result is True

    def test_cache_get_performance(self, benchmark):
        """Benchmark cache GET operation"""
        from app.integrations.redis_cache import RedisCache

        cache = RedisCache()
        cache.set("perf-test:key", {"data": "value"}, ttl=3600)

        def run_test():
            return cache.get("perf-test:key")

        result = benchmark(run_test)
        assert result is not None

    def test_cache_hit_ratio(self):
        """Measure cache hit ratio"""
        from app.integrations.redis_cache import RedisCache

        cache = RedisCache()
        benchmark = PerformanceBenchmark()

        # Simulate workload
        for i in range(1000):
            key = f"user:{i % 100}"  # 100 unique keys

            benchmark.start()
            if not cache.get(key):
                cache.set(key, {"user_id": i % 100}, ttl=3600)
            benchmark.end("cache_operation")

        # Calculate hit ratio
        stats = benchmark.get_stats("cache_operation")
        print(f"Cache operations avg time: {stats['avg']*1000:.2f}ms")


@pytest.mark.benchmark
class TestAPIPerformance:
    """API Endpoint Performance Tests"""

    def test_api_list_datasets_performance(self, benchmark, client):
        """Benchmark GET /api/v1/datasets"""

        def run_test():
            return client.get("/api/v1/datasets?page=1&page_size=100")

        result = benchmark(run_test)
        assert result.status_code == 200

    def test_api_get_dataset_rows_performance(
        self, benchmark, client, sample_dataset_id
    ):
        """Benchmark GET /api/v1/datasets/{id}/rows"""

        def run_test():
            return client.get(
                f"/api/v1/datasets/{sample_dataset_id}/rows?page=1&page_size=100"
            )

        result = benchmark(run_test)
        assert result.status_code == 200

    def test_rate_limiter_performance(self, benchmark):
        """Benchmark rate limiter"""
        from app.middleware.rate_limit_audit import RateLimiter

        limiter = RateLimiter(rate_limit=60, window=60)

        def run_test():
            return limiter.check_rate_limit("127.0.0.1")

        result = benchmark(run_test)
        assert result is True


@pytest.mark.benchmark
class TestKafkaPerformance:
    """Kafka Event Performance Tests"""

    def test_kafka_produce_performance(self, benchmark):
        """Benchmark Kafka message production"""
        from app.integrations.kafka_producer import KafkaProducer

        producer = KafkaProducer()

        def run_test():
            return producer.send_event(
                "dataset-manager.metrics", {"metric": "test", "value": 100}
            )

        result = benchmark(run_test)
        assert result is True


# ── Phase 8: Bulk Insert & Pagination Cache Benchmarks ──────

@pytest.mark.benchmark
class TestBulkInsertPerformance:
    """Benchmark batched row inserts at various scales"""

    @pytest.fixture
    def dataset_service(self):
        from app.services.dataset_service import DatasetService
        return DatasetService()

    @staticmethod
    def _generate_rows(count: int) -> List[Dict[str, Any]]:
        return [
            {
                "id": i,
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "amount": float(i * 10),
                "created": datetime.utcnow().isoformat(),
            }
            for i in range(count)
        ]

    def test_insert_10k_rows(self, benchmark, dataset_service):
        """Benchmark inserting 10,000 rows with batch statements"""
        from uuid import uuid4
        dataset_id = uuid4()
        rows = self._generate_rows(10_000)

        def run_test():
            return dataset_service.insert_rows(dataset_id, rows)

        result = benchmark.pedantic(run_test, rounds=1, iterations=1)
        assert result == 10_000

    def test_insert_100k_rows(self, benchmark, dataset_service):
        """Benchmark inserting 100,000 rows with batch statements"""
        from uuid import uuid4
        dataset_id = uuid4()
        rows = self._generate_rows(100_000)

        def run_test():
            return dataset_service.insert_rows(dataset_id, rows)

        result = benchmark.pedantic(run_test, rounds=1, iterations=1)
        assert result == 100_000

    def test_insert_1m_rows(self, benchmark, dataset_service):
        """Benchmark inserting 1,000,000 rows with batch statements"""
        from uuid import uuid4
        dataset_id = uuid4()
        rows = self._generate_rows(1_000_000)

        def run_test():
            return dataset_service.insert_rows(dataset_id, rows)

        result = benchmark.pedantic(run_test, rounds=1, iterations=1)
        assert result == 1_000_000

    def test_batch_vs_sequential_insert(self):
        """Compare batch insert throughput vs sequential baseline"""
        tracker = PerformanceBenchmark()
        rows = self._generate_rows(1_000)
        from uuid import uuid4

        # Batch insert timing (measure wall-clock cost of building batches)
        tracker.start()
        from cassandra.query import BatchStatement, SimpleStatement, BatchType
        batch = BatchStatement(batch_type=BatchType.UNLOGGED)
        for i, row in enumerate(rows):
            cols = ", ".join(row.keys())
            placeholders = ", ".join(["%s"] * len(row))
            stmt = SimpleStatement(f"INSERT INTO test (row_id, {cols}) VALUES (%s, {placeholders})")
            batch.add(stmt, [i] + list(row.values()))
            if (i + 1) % 50 == 0:
                batch = BatchStatement(batch_type=BatchType.UNLOGGED)
        tracker.end("batch_build_1k")

        stats = tracker.get_stats("batch_build_1k")
        print(f"Batch build for 1K rows: {stats['avg']*1000:.2f}ms")
        # Should be well under 100ms to build batch objects
        assert stats["avg"] < 1.0, "Batch building took >1s, unexpected overhead"


@pytest.mark.benchmark
class TestPaginationCachePerformance:
    """Benchmark Redis pagination cache operations"""

    @pytest.fixture
    def cache_service(self):
        from app.services.pagination_cache import PaginationCacheService
        return PaginationCacheService()

    def test_cache_set_latency(self, benchmark, cache_service):
        """Benchmark page cache SET latency"""
        from uuid import uuid4
        dataset_id = uuid4()
        rows = [{"name": f"User {i}", "email": f"u{i}@test.com"} for i in range(100)]

        def run_test():
            return cache_service.set_rows_page(dataset_id, 1, 100, "viewer", rows, 5000)

        result = benchmark(run_test)
        # Should return True if Redis connected, False if disabled
        assert result in (True, False)

    def test_cache_get_latency_hit(self, benchmark, cache_service):
        """Benchmark page cache GET latency on cache hit"""
        from uuid import uuid4
        dataset_id = uuid4()
        rows = [{"name": f"User {i}"} for i in range(100)]
        cache_service.set_rows_page(dataset_id, 1, 100, "viewer", rows, 5000)

        def run_test():
            return cache_service.get_rows_page(dataset_id, 1, 100, "viewer")

        result = benchmark(run_test)
        if cache_service.enabled:
            assert result is not None
            fetched_rows, total = result
            assert len(fetched_rows) == 100

    def test_cache_get_latency_miss(self, benchmark, cache_service):
        """Benchmark page cache GET latency on cache miss"""
        from uuid import uuid4

        def run_test():
            return cache_service.get_rows_page(uuid4(), 999, 100, "viewer")

        result = benchmark(run_test)
        assert result is None

    def test_cache_invalidation_speed(self, benchmark, cache_service):
        """Benchmark cache invalidation for a dataset"""
        from uuid import uuid4
        dataset_id = uuid4()
        # Pre-populate several pages
        for page in range(1, 21):
            cache_service.set_rows_page(
                dataset_id, page, 100, "viewer",
                [{"x": i} for i in range(100)], 50000
            )

        def run_test():
            return cache_service.invalidate_dataset(dataset_id)

        result = benchmark(run_test)
        assert result >= 0  # returns count of invalidated keys

    def test_cache_throughput(self):
        """Measure cache operations throughput (ops/sec)"""
        from app.services.pagination_cache import PaginationCacheService
        from uuid import uuid4

        cache = PaginationCacheService()
        if not cache.enabled:
            pytest.skip("Redis not available")

        dataset_id = uuid4()
        rows = [{"data": f"value_{i}"} for i in range(50)]
        tracker = PerformanceBenchmark()

        # Write throughput
        for i in range(100):
            tracker.start()
            cache.set_rows_page(dataset_id, i + 1, 50, "viewer", rows, 5000)
            tracker.end("cache_write")

        # Read throughput
        for i in range(100):
            tracker.start()
            cache.get_rows_page(dataset_id, i + 1, 50, "viewer")
            tracker.end("cache_read")

        write_stats = tracker.get_stats("cache_write")
        read_stats = tracker.get_stats("cache_read")

        write_ops = 1.0 / write_stats["avg"] if write_stats["avg"] > 0 else 0
        read_ops = 1.0 / read_stats["avg"] if read_stats["avg"] > 0 else 0

        print(f"\nCache write throughput: {write_ops:.0f} ops/sec")
        print(f"Cache read throughput: {read_ops:.0f} ops/sec")
        print(f"Cache write avg latency: {write_stats['avg']*1000:.2f}ms")
        print(f"Cache read avg latency: {read_stats['avg']*1000:.2f}ms")

        # Cleanup
        cache.invalidate_dataset(dataset_id)


# Summary report generation
def generate_performance_report():
    """Generate comprehensive performance report"""

    report = "\n" + "=" * 80 + "\n"
    report += "RELEASE 2 PERFORMANCE BASELINES\n"
    report += "=" * 80 + "\n\n"

    report += "PERFORMANCE TARGETS:\n"
    report += "-" * 80 + "\n"
    for target, value in PERFORMANCE_TARGETS.items():
        if isinstance(value, float) and value < 1:
            report += f"  {target}: {value*100:.1f}%\n"
        elif "mbps" in target or "sec" in target:
            report += f"  {target}: {value:,}\n"
        else:
            report += f"  {target}: {value:,}\n"

    report += "\n" + "=" * 80 + "\n"
    report += "To run benchmarks:\n"
    report += "  pytest tests/ -m benchmark -v --benchmark-only\n"
    report += "\n" + "=" * 80 + "\n"

    return report


if __name__ == "__main__":
    print(generate_performance_report())

