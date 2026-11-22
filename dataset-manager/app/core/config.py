import os
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional

# Values that must never be accepted as real secrets outside development —
# they are the old hardcoded defaults this config used to ship, now kept only
# as a deny-list so a forgotten env var fails startup instead of silently
# running with a well-known credential.
_PLACEHOLDER_SECRETS = {
    "your-secret-key",
    "your-secret-key-for-local-dev",
    "minioadmin",
}

_SECRET_FIELDS = ("SECRET_KEY", "JWT_SECRET_KEY", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY")


class Settings(BaseSettings):
    APP_V: str = "1.0.0"
    APP_NAME: str = "Dataset Manager"
    APP_ENV: str = os.getenv("APP_ENV", "development")

    # Database
    CASSANDRA_HOST: str = os.getenv("CASSANDRA_HOST", "localhost")
    CASSANDRA_PORT: int = int(os.getenv("CASSANDRA_PORT", 9042))
    CASSANDRA_KEYSPACE: str = os.getenv("CASSANDRA_KEYSPACE", "dataset_manager")

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))

    # MinIO / Storage
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "minio")
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "")
    MINIO_BUCKET_NAME: str = os.getenv("MINIO_BUCKET_NAME", "dataset-manager-storage")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "False").lower() == "true"

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

    # Uploads — server-side source of truth; keep in sync with the frontend's
    # VITE_UPLOAD_MAX_SIZE (see frontend/.env.*).
    MAX_UPLOAD_SIZE_BYTES: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", 10737418240))

    class Config:
        case_sensitive = True

    @field_validator(*_SECRET_FIELDS)
    @classmethod
    def _no_missing_or_placeholder_secrets_outside_dev(cls, value: str, info) -> str:
        app_env = os.getenv("APP_ENV", "development")
        if app_env != "development" and (not value or value in _PLACEHOLDER_SECRETS):
            raise ValueError(
                f"{info.field_name} must be set to a real, non-placeholder value when "
                f"APP_ENV={app_env!r}. Set it via environment variable / secrets manager — "
                f"see .env.example for local development defaults."
            )
        return value

settings = Settings()
