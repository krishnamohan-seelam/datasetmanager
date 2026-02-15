import os
from pydantic_settings import BaseSettings
from typing import Optional

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
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET_NAME: str = os.getenv("MINIO_BUCKET_NAME", "dataset-manager-storage")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "False").lower() == "true"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-for-local-dev")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

    class Config:
        case_sensitive = True

settings = Settings()
