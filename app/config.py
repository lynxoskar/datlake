"""
Configuration management for DuckLake application.

Provides comprehensive configuration with validation, secrets management,
environment-specific settings, and feature flags.
"""

import os
import secrets
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import BaseSettings, Field, SecretStr, validator, root_validator
from pydantic.networks import AnyHttpUrl, PostgresDsn

from .exceptions import InvalidConfigurationError, MissingConfigurationError


class Environment(str, Enum):
    """Application environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class FeatureFlags(BaseSettings):
    """Feature flags for runtime configuration."""
    
    # Data processing features
    enable_async_processing: bool = True
    enable_batch_optimization: bool = True
    enable_memory_monitoring: bool = True
    enable_performance_tracking: bool = True
    
    # API features
    enable_rate_limiting: bool = False
    enable_request_caching: bool = False
    enable_cors: bool = True
    enable_api_versioning: bool = False
    
    # Monitoring features
    enable_prometheus_metrics: bool = True
    enable_health_checks: bool = True
    enable_error_tracking: bool = True
    enable_distributed_tracing: bool = False
    
    # Storage features
    enable_s3_encryption: bool = False
    enable_data_compression: bool = True
    enable_backup_automation: bool = False
    
    # Security features
    enable_authentication: bool = False
    enable_authorization: bool = False
    enable_audit_logging: bool = True
    enable_input_validation: bool = True
    
    class Config:
        env_prefix = "FEATURE_"
        env_file = ".env"


class SecuritySettings(BaseSettings):
    """Security-related configuration."""
    
    # API Security
    api_key_header: str = "X-API-Key"
    cors_origins: List[str] = ["*"]
    cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_headers: List[str] = ["*"]
    
    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds
    rate_limit_burst: int = 150
    
    # Secrets
    secret_key: SecretStr = Field(default_factory=lambda: SecretStr(secrets.token_urlsafe(32)))
    jwt_secret: Optional[SecretStr] = None
    encryption_key: Optional[SecretStr] = None
    
    class Config:
        env_prefix = "SECURITY_"
        env_file = ".env"


class DatabaseSettings(BaseSettings):
    """Database configuration with validation."""
    
    # PostgreSQL connection
    postgres_host: str = "localhost"
    postgres_port: int = Field(5432, ge=1, le=65535)
    postgres_db: str = "ducklakedb"
    postgres_user: str = "postgres"
    postgres_password: SecretStr = SecretStr("postgrespassword")
    postgres_schema: str = "public"
    
    # Connection pool settings
    postgres_min_connections: int = Field(2, ge=1, le=50)
    postgres_max_connections: int = Field(10, ge=1, le=100)
    postgres_connection_timeout: float = Field(30.0, ge=1.0, le=300.0)
    postgres_command_timeout: float = Field(60.0, ge=1.0, le=3600.0)
    
    # DuckDB settings
    duckdb_memory_limit: str = "75%"
    duckdb_threads: int = Field(4, ge=1, le=32)
    duckdb_enable_optimizer: bool = True
    
    @validator("postgres_max_connections")
    def validate_max_connections(cls, v, values):
        if "postgres_min_connections" in values and v < values["postgres_min_connections"]:
            raise ValueError("max_connections must be >= min_connections")
        return v
    
    @property
    def postgres_dsn(self) -> str:
        """Build PostgreSQL DSN."""
        return f"postgresql://{self.postgres_user}:{self.postgres_password.get_secret_value()}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    class Config:
        env_prefix = "DB_"
        env_file = ".env"


class StorageSettings(BaseSettings):
    """Storage configuration for MinIO/S3."""
    
    # MinIO/S3 connection
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: SecretStr = SecretStr("minioadmin")
    minio_secure: bool = False
    minio_region: str = "us-east-1"
    
    # Bucket settings
    default_bucket: str = "ducklake-data"
    backup_bucket: Optional[str] = None
    temp_bucket: str = "ducklake-temp"
    
    # Upload settings
    max_file_size: int = Field(100 * 1024 * 1024, ge=1024)  # 100MB default
    allowed_extensions: Set[str] = {".parquet", ".csv", ".json", ".txt", ".log"}
    upload_timeout: float = Field(300.0, ge=10.0, le=3600.0)  # 5 minutes
    
    # Performance settings
    multipart_threshold: int = Field(8 * 1024 * 1024, ge=1024 * 1024)  # 8MB
    max_concurrency: int = Field(10, ge=1, le=50)
    
    @validator("minio_endpoint")
    def validate_endpoint(cls, v):
        if not v or ":" not in v:
            raise ValueError("MinIO endpoint must include port (e.g., localhost:9000)")
        return v
    
    class Config:
        env_prefix = "STORAGE_"
        env_file = ".env"


class MonitoringSettings(BaseSettings):
    """Monitoring and observability configuration."""
    
    # OpenLineage
    openlineage_url: Optional[AnyHttpUrl] = None
    openlineage_api_key: Optional[SecretStr] = None
    openlineage_namespace: str = "ducklake"
    
    # Prometheus metrics
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"
    metrics_port: Optional[int] = Field(None, ge=1024, le=65535)
    
    # Health checks
    health_check_timeout: float = Field(10.0, ge=1.0, le=60.0)
    health_check_interval: float = Field(30.0, ge=5.0, le=300.0)
    
    # Memory monitoring
    memory_threshold_warning: float = Field(0.8, ge=0.1, le=0.95)  # 80%
    memory_threshold_critical: float = Field(0.9, ge=0.1, le=0.99)  # 90%
    memory_check_interval: float = Field(5.0, ge=1.0, le=60.0)  # seconds
    
    # Performance monitoring
    slow_query_threshold: float = Field(1.0, ge=0.1, le=10.0)  # seconds
    request_timeout: float = Field(30.0, ge=1.0, le=300.0)  # seconds
    
    class Config:
        env_prefix = "MONITORING_"
        env_file = ".env"


class QueueSettings(BaseSettings):
    """Queue processing configuration."""
    
    # PGMQ settings
    queue_batch_size: int = Field(10, ge=1, le=100)
    queue_poll_interval: int = Field(5, ge=1, le=60)
    queue_retry_attempts: int = Field(3, ge=1, le=10)
    queue_retry_delay: float = Field(1.0, ge=0.1, le=60.0)
    
    # Dead letter queue settings
    dlq_enabled: bool = True
    dlq_max_age: int = Field(7 * 24 * 3600, ge=3600)  # 7 days in seconds
    
    # Worker settings
    worker_count: int = Field(2, ge=1, le=10)
    worker_timeout: float = Field(60.0, ge=10.0, le=600.0)
    
    class Config:
        env_prefix = "QUEUE_"
        env_file = ".env"


class Settings(BaseSettings):
    """Main application settings with comprehensive validation."""
    
    # Environment
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = Field(default=False)
    log_level: LogLevel = LogLevel.INFO
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = Field(8000, ge=1024, le=65535)
    reload: bool = False
    workers: int = Field(1, ge=1, le=16)
    
    # Application info
    app_name: str = "DuckLake API"
    app_version: str = "1.0.2"
    app_description: str = "Data lake with OpenLineage integration"
    
    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    queue: QueueSettings = Field(default_factory=QueueSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    
    @root_validator
    def validate_environment_settings(cls, values):
        """Validate settings based on environment."""
        environment = values.get("environment", Environment.DEVELOPMENT)
        
        if environment == Environment.PRODUCTION:
            # Production-specific validations
            if values.get("debug", False):
                raise ValueError("Debug mode must be disabled in production")
            
            monitoring = values.get("monitoring")
            if monitoring and not monitoring.openlineage_url:
                raise ValueError("OpenLineage URL required in production")
        
        return values
    
    @validator("debug")
    def validate_debug_in_production(cls, v, values):
        """Ensure debug is disabled in production."""
        if values.get("environment") == Environment.PRODUCTION and v:
            raise ValueError("Debug mode must be disabled in production")
        return v
    
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == Environment.DEVELOPMENT
    
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == Environment.PRODUCTION
    
    def is_testing(self) -> bool:
        """Check if running in testing mode."""
        return self.environment == Environment.TESTING
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of configuration (without secrets)."""
        return {
            "environment": self.environment.value,
            "debug": self.debug,
            "log_level": self.log_level.value,
            "host": self.host,
            "port": self.port,
            "database": {
                "host": self.database.postgres_host,
                "port": self.database.postgres_port,
                "database": self.database.postgres_db,
                "pool_size": f"{self.database.postgres_min_connections}-{self.database.postgres_max_connections}"
            },
            "storage": {
                "endpoint": self.storage.minio_endpoint,
                "secure": self.storage.minio_secure,
                "default_bucket": self.storage.default_bucket
            },
            "features_enabled": sum(1 for v in self.features.__dict__.values() if v is True),
            "monitoring_enabled": self.monitoring.metrics_enabled
        }
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance with validation."""
    try:
        return Settings()
    except Exception as e:
        if "required" in str(e):
            raise MissingConfigurationError(str(e))
        else:
            raise InvalidConfigurationError("general", str(e), "valid configuration")


def validate_configuration() -> Dict[str, Any]:
    """Validate current configuration and return status."""
    try:
        settings = get_settings()
        return {
            "valid": True,
            "environment": settings.environment.value,
            "config_summary": settings.get_config_summary(),
            "validation_errors": []
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "validation_errors": [str(e)]
        }