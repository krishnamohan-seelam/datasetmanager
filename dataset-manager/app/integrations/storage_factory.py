"""
Storage Service Factory - Supports Multiple Backends
AWS S3, MinIO (local S3-compatible), or Local Filesystem
"""

import logging
import os
from typing import Optional, BinaryIO, Union
from enum import Enum

logger = logging.getLogger(__name__)


class StorageBackend(str, Enum):
    """Storage backend types"""

    AWS = "aws"
    MINIO = "minio"
    LOCAL = "local"


def get_storage_service():
    """
    Factory function to get appropriate storage service
    based on STORAGE_BACKEND environment variable

    Returns:
        StorageService instance (S3 or Local)
    """
    backend = os.getenv("STORAGE_BACKEND", "minio").lower()

    if backend == StorageBackend.LOCAL:
        logger.info("Using Local Filesystem storage backend")
        from .local_storage import LocalStorageService

        return LocalStorageService()

    elif backend in (StorageBackend.MINIO, StorageBackend.AWS):
        logger.info(f"Using {backend.upper()} S3-compatible storage backend")
        from .s3_storage import S3StorageService

        if backend == StorageBackend.MINIO:
            # MinIO configuration
            return S3StorageService(
                endpoint_url=os.getenv("MINIO_ENDPOINT", "http://localhost:9000"),
                aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
                aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
                bucket_name=os.getenv("MINIO_BUCKET_NAME", "dataset-manager-storage"),
                use_ssl=os.getenv("MINIO_SECURE", "False").lower() == "true",
            )
        else:
            # AWS S3 configuration
            return S3StorageService(
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION", "us-east-1"),
                bucket_name=os.getenv("S3_BUCKET_NAME", "dataset-manager-storage"),
            )

    else:
        raise ValueError(f"Unknown storage backend: {backend}")
