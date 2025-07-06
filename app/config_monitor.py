"""
Configuration monitoring and health checks for DuckLake application.

Provides runtime monitoring of configuration health, environment validation,
and configuration change detection.
"""

import asyncio
import hashlib
import time
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timedelta

import asyncpg
from loguru import logger
from minio import Minio
from minio.error import S3Error

from .config import get_settings, validate_configuration
from .exceptions import (
    ConfigurationException,
    DatabaseConnectionError,
    MinIOConnectionError,
    InvalidConfigurationError
)


class ConfigurationMonitor:
    """Monitor configuration health and environment connectivity."""
    
    def __init__(self):
        self.settings = get_settings()
        self.last_check_time: Optional[datetime] = None
        self.last_config_hash: Optional[str] = None
        self.health_status: Dict[str, Any] = {}
        self.check_interval = self.settings.monitoring.health_check_interval
        
    def get_config_hash(self) -> str:
        """Generate hash of current configuration for change detection."""
        config_dict = self.settings.dict()
        # Remove dynamic fields that shouldn't trigger config change detection
        config_dict.pop('features', None)  # Feature flags can change dynamically
        
        config_str = str(sorted(config_dict.items()))
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]
    
    async def check_database_connectivity(self) -> Dict[str, Any]:
        """Check PostgreSQL database connectivity."""
        start_time = time.time()
        try:
            conn = await asyncpg.connect(
                host=self.settings.database.postgres_host,
                port=self.settings.database.postgres_port,
                database=self.settings.database.postgres_db,
                user=self.settings.database.postgres_user,
                password=self.settings.database.postgres_password.get_secret_value(),
                timeout=self.settings.monitoring.health_check_timeout
            )
            
            # Test basic query
            result = await conn.fetchval("SELECT version()")
            await conn.close()
            
            duration = time.time() - start_time
            
            return {
                "status": "healthy",
                "response_time": duration,
                "version": result[:50] if result else "unknown",
                "host": self.settings.database.postgres_host,
                "port": self.settings.database.postgres_port,
                "database": self.settings.database.postgres_db
            }
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error("Database connectivity check failed", 
                        host=self.settings.database.postgres_host, 
                        error=str(e))
            
            return {
                "status": "unhealthy",
                "response_time": duration,
                "error": str(e),
                "host": self.settings.database.postgres_host,
                "port": self.settings.database.postgres_port
            }
    
    async def check_storage_connectivity(self) -> Dict[str, Any]:
        """Check MinIO/S3 storage connectivity."""
        start_time = time.time()
        try:
            # Create MinIO client
            client = Minio(
                self.settings.storage.minio_endpoint,
                access_key=self.settings.storage.minio_access_key,
                secret_key=self.settings.storage.minio_secret_key.get_secret_value(),
                secure=self.settings.storage.minio_secure
            )
            
            # Test connectivity by listing buckets
            buckets = list(client.list_buckets())
            bucket_names = [bucket.name for bucket in buckets]
            
            duration = time.time() - start_time
            
            return {
                "status": "healthy",
                "response_time": duration,
                "endpoint": self.settings.storage.minio_endpoint,
                "secure": self.settings.storage.minio_secure,
                "bucket_count": len(buckets),
                "buckets": bucket_names[:5]  # Show first 5 buckets
            }
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error("Storage connectivity check failed", 
                        endpoint=self.settings.storage.minio_endpoint, 
                        error=str(e))
            
            return {
                "status": "unhealthy", 
                "response_time": duration,
                "error": str(e),
                "endpoint": self.settings.storage.minio_endpoint
            }
    
    def check_feature_flags_consistency(self) -> Dict[str, Any]:
        """Check feature flag consistency and dependencies."""
        flags = self.settings.features
        issues = []
        warnings = []
        
        # Check feature dependencies
        if flags.enable_authentication and not flags.enable_input_validation:
            issues.append("Authentication enabled but input validation disabled")
            
        if flags.enable_rate_limiting and not flags.enable_prometheus_metrics:
            warnings.append("Rate limiting enabled but metrics disabled - monitoring recommended")
            
        if flags.enable_backup_automation and not flags.enable_data_compression:
            warnings.append("Backup automation without compression - consider enabling compression")
            
        if self.settings.is_production():
            # Production-specific checks
            if not flags.enable_error_tracking:
                issues.append("Error tracking should be enabled in production")
                
            if not flags.enable_audit_logging:
                issues.append("Audit logging should be enabled in production")
                
            if not flags.enable_prometheus_metrics:
                issues.append("Prometheus metrics should be enabled in production")
        
        enabled_count = sum(1 for attr in dir(flags) 
                          if not attr.startswith('_') 
                          and isinstance(getattr(flags, attr), bool) 
                          and getattr(flags, attr))
        
        return {
            "status": "healthy" if not issues else "warning",
            "enabled_features": enabled_count,
            "issues": issues,
            "warnings": warnings,
            "environment": self.settings.environment.value
        }
    
    def validate_environment_configuration(self) -> Dict[str, Any]:
        """Validate configuration for current environment."""
        env = self.settings.environment
        issues = []
        warnings = []
        
        if env.value == "production":
            # Production validations
            if self.settings.debug:
                issues.append("Debug mode enabled in production")
                
            if not self.settings.monitoring.openlineage_url:
                issues.append("OpenLineage URL not configured for production")
                
            if self.settings.storage.minio_access_key == "minioadmin":
                issues.append("Default MinIO credentials used in production")
                
            if self.settings.database.postgres_password.get_secret_value() == "postgrespassword":
                issues.append("Default database password used in production")
                
        elif env.value == "staging":
            # Staging validations
            if self.settings.debug:
                warnings.append("Debug mode enabled in staging")
                
        elif env.value == "development":
            # Development warnings
            if not self.settings.debug:
                warnings.append("Debug mode disabled in development")
                
        # Resource validations
        if self.settings.database.postgres_max_connections < self.settings.database.postgres_min_connections:
            issues.append("Max database connections less than min connections")
            
        if self.settings.queue.queue_batch_size > 100:
            warnings.append("Large queue batch size may impact performance")
            
        return {
            "status": "healthy" if not issues else "error",
            "environment": env.value,
            "issues": issues,
            "warnings": warnings
        }
    
    async def perform_comprehensive_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive configuration and connectivity health check."""
        start_time = datetime.now()
        
        logger.info("Starting comprehensive configuration health check")
        
        # Run all checks
        config_validation = validate_configuration()
        db_check = await self.check_database_connectivity()
        storage_check = await self.check_storage_connectivity()
        feature_check = self.check_feature_flags_consistency()
        env_check = self.validate_environment_configuration()
        
        # Determine overall health
        checks = [db_check, storage_check, feature_check, env_check]
        unhealthy_checks = [check for check in checks if check.get("status") in ["unhealthy", "error"]]
        warning_checks = [check for check in checks if check.get("status") == "warning"]
        
        if unhealthy_checks:
            overall_status = "unhealthy"
        elif warning_checks or not config_validation["valid"]:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        # Update internal state
        self.last_check_time = start_time
        current_hash = self.get_config_hash()
        config_changed = self.last_config_hash != current_hash
        self.last_config_hash = current_hash
        
        duration = (datetime.now() - start_time).total_seconds()
        
        health_report = {
            "overall_status": overall_status,
            "check_time": start_time.isoformat(),
            "duration_seconds": duration,
            "config_changed": config_changed,
            "config_hash": current_hash,
            "environment": self.settings.environment.value,
            "checks": {
                "configuration": config_validation,
                "database": db_check,
                "storage": storage_check,
                "features": feature_check,
                "environment": env_check
            },
            "summary": {
                "total_checks": len(checks) + 1,  # +1 for config validation
                "healthy_checks": len([c for c in checks if c.get("status") == "healthy"]),
                "warning_checks": len(warning_checks),
                "unhealthy_checks": len(unhealthy_checks)
            }
        }
        
        # Store for future reference
        self.health_status = health_report
        
        # Log results
        if overall_status == "healthy":
            logger.info("Configuration health check completed - all systems healthy", 
                       duration=duration)
        elif overall_status == "warning":
            logger.warning("Configuration health check completed with warnings", 
                          warnings=len(warning_checks), duration=duration)
        else:
            logger.error("Configuration health check failed", 
                        unhealthy_checks=len(unhealthy_checks), duration=duration)
        
        return health_report
    
    def get_last_health_status(self) -> Dict[str, Any]:
        """Get the last health check results."""
        if not self.health_status:
            return {
                "status": "unknown",
                "message": "No health check performed yet",
                "last_check": None
            }
        
        return self.health_status
    
    def is_configuration_stale(self) -> bool:
        """Check if configuration validation is stale."""
        if not self.last_check_time:
            return True
            
        stale_threshold = timedelta(seconds=self.check_interval * 2)
        return datetime.now() - self.last_check_time > stale_threshold


# Global configuration monitor instance
config_monitor = ConfigurationMonitor() 