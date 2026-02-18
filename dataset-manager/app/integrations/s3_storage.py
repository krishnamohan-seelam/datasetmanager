"""
S3 Storage Service for Dataset Manager
Manages file uploads/downloads to AWS S3 or MinIO (S3-compatible)
"""

import logging
import os
from typing import Optional, BinaryIO
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class S3StorageService:
    """AWS S3 or MinIO storage management service"""

    def __init__(
        self,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        region_name: str = None,
        bucket_name: str = None,
        endpoint_url: str = None,
        use_ssl: bool = True,
    ):
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv(
            "AWS_SECRET_ACCESS_KEY"
        )
        self.region_name = region_name or os.getenv("AWS_REGION", "us-east-1")
        self.bucket_name = bucket_name or os.getenv(
            "S3_BUCKET_NAME", "dataset-manager-storage"
        )
        self.endpoint_url = endpoint_url  # For MinIO support
        self.use_ssl = use_ssl

        self.s3_client = None
        self._connect()

    def _connect(self):
        """Connect to S3 or MinIO"""
        try:
            client_kwargs = {
                "aws_access_key_id": self.aws_access_key_id,
                "aws_secret_access_key": self.aws_secret_access_key,
                "region_name": self.region_name,
            }

            # Add endpoint URL for MinIO
            if self.endpoint_url:
                client_kwargs["endpoint_url"] = self.endpoint_url
                logger.info(f"Connecting to MinIO at: {self.endpoint_url}")

            self.s3_client = boto3.client("s3", **client_kwargs)
            logger.info(f"Connected to S3 bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Failed to connect to S3/MinIO: {str(e)}")
            raise

    def upload_file(
        self,
        file_obj: BinaryIO,
        dataset_id: str,
        filename: str,
        file_size: int,
        metadata: dict = None,
    ) -> str:
        """
        Upload file to S3

        Args:
            file_obj: File object to upload
            dataset_id: Dataset ID
            filename: Original filename
            file_size: File size in bytes
            metadata: Optional metadata dict

        Returns:
            S3 object key/path
        """
        try:
            # Create S3 key
            s3_key = f"{dataset_id}/raw/{datetime.utcnow().isoformat()}_{filename}"

            # Prepare metadata
            extra_args = {
                "ServerSideEncryption": "AES256",
                "Metadata": {
                    "original-filename": filename,
                    "upload-timestamp": datetime.utcnow().isoformat(),
                    "file-size": str(file_size),
                },
            }

            if metadata:
                extra_args["Metadata"].update({k: str(v) for k, v in metadata.items()})

            # Upload file
            self.s3_client.upload_fileobj(
                file_obj, self.bucket_name, s3_key, ExtraArgs=extra_args
            )

            logger.info(f"Uploaded file to S3: s3://{self.bucket_name}/{s3_key}")
            return s3_key

        except ClientError as e:
            logger.error(f"S3 upload failed: {str(e)}")
            raise

    def download_file(self, s3_key: str, local_path: str = None) -> BinaryIO:
        """
        Download file from S3

        Args:
            s3_key: S3 object key
            local_path: Optional local path to save

        Returns:
            File object or local path
        """
        try:
            if local_path:
                self.s3_client.download_file(self.bucket_name, s3_key, local_path)
                logger.info(f"Downloaded file from S3 to {local_path}")
                return local_path
            else:
                obj = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
                logger.info(f"Downloaded file from S3: {s3_key}")
                return obj["Body"]

        except ClientError as e:
            logger.error(f"S3 download failed: {str(e)}")
            raise

    def delete_file(self, s3_key: str) -> bool:
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Deleted file from S3: {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"S3 deletion failed: {str(e)}")
            return False

    def delete_dataset_files(self, dataset_id: str) -> int:
        """Delete all files for a dataset"""
        try:
            prefix = f"{dataset_id}/"
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix=prefix
            )

            deleted_count = 0
            if "Contents" in response:
                for obj in response["Contents"]:
                    self.s3_client.delete_object(
                        Bucket=self.bucket_name, Key=obj["Key"]
                    )
                    deleted_count += 1

            logger.info(f"Deleted {deleted_count} files for dataset {dataset_id}")
            return deleted_count

        except ClientError as e:
            logger.error(f"S3 batch deletion failed: {str(e)}")
            return 0

    def get_file_size(self, s3_key: str) -> int:
        """Get file size from S3"""
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return response["ContentLength"]
        except ClientError as e:
            logger.error(f"Failed to get file size: {str(e)}")
            return 0

    def generate_presigned_url(self, s3_key: str, expiration_hours: int = 24) -> str:
        """
        Generate presigned URL for file access

        Args:
            s3_key: S3 object key
            expiration_hours: URL expiration time in hours

        Returns:
            Presigned URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expiration_hours * 3600,
            )
            logger.info(f"Generated presigned URL for {s3_key}")
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            return ""

    def archive_old_files(self, retention_days: int = 90) -> int:
        """
        Archive files older than retention period

        Args:
            retention_days: Days to retain active files

        Returns:
            Number of archived files
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name)

            archived_count = 0
            if "Contents" in response:
                for obj in response["Contents"]:
                    if obj["LastModified"].replace(tzinfo=None) < cutoff_date:
                        # Move to archive storage class (Glacier)
                        self.s3_client.copy_object(
                            Bucket=self.bucket_name,
                            CopySource={"Bucket": self.bucket_name, "Key": obj["Key"]},
                            Key=obj["Key"],
                            StorageClass="GLACIER",
                        )
                        archived_count += 1

            logger.info(f"Archived {archived_count} files")
            return archived_count

        except ClientError as e:
            logger.error(f"Archival failed: {str(e)}")
            return 0
