"""
Prometheus metrics and monitoring for Dataset Manager
"""

import logging
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
import time
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)

# Create registry
registry = CollectorRegistry()


class DatasetManagerMetrics:
    """Centralized metrics collection"""

    # API Metrics
    api_requests_total = Counter(
        "dataset_manager_api_requests_total",
        "Total API requests",
        ["method", "endpoint", "status"],
        registry=registry,
    )

    api_request_duration_seconds = Histogram(
        "dataset_manager_api_request_duration_seconds",
        "API request duration in seconds",
        ["method", "endpoint"],
        registry=registry,
    )

    api_errors_total = Counter(
        "dataset_manager_api_errors_total",
        "Total API errors",
        ["error_type", "endpoint"],
        registry=registry,
    )

    # Dataset Metrics
    datasets_total = Gauge(
        "dataset_manager_datasets_total", "Total number of datasets", registry=registry
    )

    dataset_rows_total = Gauge(
        "dataset_manager_dataset_rows_total",
        "Total rows across all datasets",
        registry=registry,
    )

    dataset_storage_bytes = Gauge(
        "dataset_manager_dataset_storage_bytes",
        "Total storage used in bytes",
        registry=registry,
    )

    dataset_upload_duration_seconds = Histogram(
        "dataset_manager_dataset_upload_duration_seconds",
        "Dataset upload duration in seconds",
        registry=registry,
    )

    # Authentication Metrics
    auth_login_total = Counter(
        "dataset_manager_auth_login_total",
        "Total login attempts",
        ["status"],
        registry=registry,
    )

    active_sessions = Gauge(
        "dataset_manager_active_sessions",
        "Number of active sessions",
        registry=registry,
    )

    # Permission Metrics
    permission_checks_total = Counter(
        "dataset_manager_permission_checks_total",
        "Total permission checks",
        ["result"],
        registry=registry,
    )

    # Masking Metrics
    masking_operations_total = Counter(
        "dataset_manager_masking_operations_total",
        "Total masking operations",
        ["rule_type"],
        registry=registry,
    )

    masking_duration_seconds = Histogram(
        "dataset_manager_masking_duration_seconds",
        "Masking operation duration in seconds",
        ["rule_type"],
        registry=registry,
    )

    # Cache Metrics
    cache_hits_total = Counter(
        "dataset_manager_cache_hits_total",
        "Total cache hits",
        ["cache_type"],
        registry=registry,
    )

    cache_misses_total = Counter(
        "dataset_manager_cache_misses_total",
        "Total cache misses",
        ["cache_type"],
        registry=registry,
    )

    cache_size_bytes = Gauge(
        "dataset_manager_cache_size_bytes",
        "Cache size in bytes",
        ["cache_type"],
        registry=registry,
    )

    # Database Metrics
    db_query_duration_seconds = Histogram(
        "dataset_manager_db_query_duration_seconds",
        "Database query duration in seconds",
        ["query_type"],
        registry=registry,
    )

    db_connection_pool_size = Gauge(
        "dataset_manager_db_connection_pool_size",
        "Database connection pool size",
        registry=registry,
    )

    # ETL Metrics
    etl_jobs_total = Counter(
        "dataset_manager_etl_jobs_total",
        "Total ETL jobs",
        ["status"],
        registry=registry,
    )

    etl_job_duration_seconds = Histogram(
        "dataset_manager_etl_job_duration_seconds",
        "ETL job duration in seconds",
        ["stage"],
        registry=registry,
    )

    etl_rows_processed_total = Counter(
        "dataset_manager_etl_rows_processed_total",
        "Total rows processed by ETL",
        registry=registry,
    )

    # Kafka Metrics
    kafka_messages_produced_total = Counter(
        "dataset_manager_kafka_messages_produced_total",
        "Total Kafka messages produced",
        ["topic"],
        registry=registry,
    )

    kafka_messages_consumed_total = Counter(
        "dataset_manager_kafka_messages_consumed_total",
        "Total Kafka messages consumed",
        ["topic"],
        registry=registry,
    )

    kafka_consumer_lag = Gauge(
        "dataset_manager_kafka_consumer_lag",
        "Kafka consumer lag",
        ["consumer_group", "topic"],
        registry=registry,
    )

    # S3 Metrics
    s3_upload_bytes_total = Counter(
        "dataset_manager_s3_upload_bytes_total",
        "Total bytes uploaded to S3",
        registry=registry,
    )

    s3_download_bytes_total = Counter(
        "dataset_manager_s3_download_bytes_total",
        "Total bytes downloaded from S3",
        registry=registry,
    )

    s3_operation_duration_seconds = Histogram(
        "dataset_manager_s3_operation_duration_seconds",
        "S3 operation duration in seconds",
        ["operation"],
        registry=registry,
    )

    # System Metrics
    active_users = Gauge(
        "dataset_manager_active_users", "Number of active users", registry=registry
    )


def track_api_call(endpoint: str, method: str = "GET"):
    """Decorator to track API calls"""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                status = "success"
                DatasetManagerMetrics.api_requests_total.labels(
                    method=method, endpoint=endpoint, status=status
                ).inc()
                return result
            except Exception as e:
                status = "error"
                DatasetManagerMetrics.api_requests_total.labels(
                    method=method, endpoint=endpoint, status=status
                ).inc()
                DatasetManagerMetrics.api_errors_total.labels(
                    error_type=type(e).__name__, endpoint=endpoint
                ).inc()
                raise
            finally:
                duration = time.time() - start_time
                DatasetManagerMetrics.api_request_duration_seconds.labels(
                    method=method, endpoint=endpoint
                ).observe(duration)

        return wrapper

    return decorator


def track_operation(operation_name: str):
    """Generic operation tracking decorator"""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                logger.info(f"Operation {operation_name} took {duration:.2f}s")

        return wrapper

    return decorator
