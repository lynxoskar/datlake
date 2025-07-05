"""
Configuration management for DuckLake application
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # MinIO settings
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    
    # PostgreSQL settings
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "ducklakedb"
    postgres_user: str = "postgres"
    postgres_password: str = "postgrespassword"
    
    # OpenLineage settings
    openlineage_url: Optional[str] = None
    openlineage_api_key: Optional[str] = None
    
    # Queue settings
    queue_batch_size: int = 10
    queue_poll_interval: int = 5
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()