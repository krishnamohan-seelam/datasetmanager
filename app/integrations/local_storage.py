"""
Local Filesystem Storage Service for Dataset Manager
Use for local development/testing without S3 or MinIO
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional, BinaryIO
from datetime import datetime

logger = logging.getLogger(__name__)


class LocalStorageService:
    """Local filesystem storage service (development/demo only)"""

    def __init__(self, base_path: str = None):
        """
        Initialize local storage service

        Args:
            base_path: Base directory for storage (default: ./storage)
        """
        self.base_path = Path(base_path or os.getenv("LOCAL_STORAGE_PATH", "./storage"))
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized local storage at: {self.base_path}")

    def _get_file_path(self, key: str) -> Path:
        """Convert S3-like key to local file path"""
        # key format: {dataset_id}/raw/{timestamp}_{filename}
        file_path = self.base_path / key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        return file_path

    def upload_file(
        self,
        file_obj: BinaryIO,
        dataset_id: str,
        filename: str,
        file_size: int,
        metadata: dict = None,
    ) -> str:
        """
        Upload file to local storage

        Args:
            file_obj: File object to upload
            dataset_id: Dataset ID
            filename: Original filename
            file_size: File size in bytes
            metadata: Optional metadata dict

        Returns:
            File key/path (S3-like format for compatibility)
        """
        try:
            # Create S3-style key for consistency
            file_key = f"{dataset_id}/raw/{datetime.utcnow().isoformat()}_{filename}"
            file_path = self._get_file_path(file_key)

            # Write file
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file_obj, f)

            logger.info(f"Uploaded file to local storage: {file_path}")
            return file_key

        except Exception as e:
            logger.error(f"Local upload failed: {str(e)}")
            raise

    def download_file(
        self, file_key: str, local_path: str = None
    ) -> Union[str, BinaryIO]:
        """
        Download file from local storage

        Args:
            file_key: File key/path
            local_path: Optional local path to save

        Returns:
            File object or local path
        """
        try:
            file_path = self._get_file_path(file_key)

            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_key}")

            if local_path:
                shutil.copy2(file_path, local_path)
                logger.info(f"Downloaded file to {local_path}")
                return local_path
            else:
                logger.info(f"Downloaded file: {file_key}")
                return open(file_path, "rb")

        except Exception as e:
            logger.error(f"Local download failed: {str(e)}")
            raise

    def delete_file(self, file_key: str) -> bool:
        """Delete file from local storage"""
        try:
            file_path = self._get_file_path(file_key)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted file: {file_key}")
                return True
            return False
        except Exception as e:
            logger.error(f"Local deletion failed: {str(e)}")
            return False

    def delete_dataset_files(self, dataset_id: str) -> int:
        """Delete all files for a dataset"""
        try:
            dataset_path = self.base_path / dataset_id
            deleted_count = 0

            if dataset_path.exists():
                for file_path in dataset_path.rglob("*"):
                    if file_path.is_file():
                        file_path.unlink()
                        deleted_count += 1

                # Remove empty directories
                shutil.rmtree(dataset_path, ignore_errors=True)

            logger.info(f"Deleted {deleted_count} files for dataset {dataset_id}")
            return deleted_count

        except Exception as e:
            logger.error(f"Local batch deletion failed: {str(e)}")
            return 0

    def get_file_size(self, file_key: str) -> int:
        """Get file size from local storage"""
        try:
            file_path = self._get_file_path(file_key)
            if file_path.exists():
                return file_path.stat().st_size
            return 0
        except Exception as e:
            logger.error(f"Failed to get file size: {str(e)}")
            return 0

    def generate_presigned_url(self, file_key: str, expiration_hours: int = 24) -> str:
        """
        Generate presigned URL (local storage returns local path for compatibility)

        Args:
            file_key: File key
            expiration_hours: Ignored for local storage

        Returns:
            Local file path (for demo purposes)
        """
        file_path = self._get_file_path(file_key)
        if file_path.exists():
            logger.info(f"Generated local path for {file_key}")
            return str(file_path)
        return ""

    def archive_old_files(self, retention_days: int = 90) -> int:
        """
        Archive files older than retention period
        (For local storage, just logs - no actual archival)

        Args:
            retention_days: Days to retain active files

        Returns:
            Number of old files found
        """
        try:
            from datetime import datetime, timedelta

            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            archived_count = 0

            for file_path in self.base_path.rglob("*"):
                if file_path.is_file():
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_date:
                        archived_count += 1

            logger.info(
                f"Found {archived_count} files older than {retention_days} days"
            )
            return archived_count

        except Exception as e:
            logger.error(f"Archival check failed: {str(e)}")
            return 0
