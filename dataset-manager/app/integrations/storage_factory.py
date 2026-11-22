"""
Storage Service Factory - Supports Multiple Backends
AWS S3, MinIO (local S3-compatible), or Local Filesystem
"""

import logging
import os
from typing import Optional, BinaryIO, Union
from enum import Enum

from app.core.config import settings

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
    backend = settings.STORAGE_BACKEND.lower()

    if backend == StorageBackend.LOCAL:
        logger.info("Using Local Filesystem storage backend")
        from .local_storage import LocalStorageService

        return LocalStorageService()

    elif backend in (StorageBackend.MINIO, StorageBackend.AWS):
        logger.info(f"Using {backend.upper()} S3-compatible storage backend")
        from .s3_storage import S3StorageService

        if backend == StorageBackend.MINIO:
            # MinIO configuration — no hardcoded fallback; Settings already
            # fails startup outside development if these are unset.
            return S3StorageService(
                endpoint_url=settings.MINIO_ENDPOINT,
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
                bucket_name=settings.MINIO_BUCKET_NAME,
                use_ssl=settings.MINIO_SECURE,
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
