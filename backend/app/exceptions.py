"""
Custom exception types for DuckLake application.

Provides specific exception classes for different error categories to improve
error handling, debugging, and user experience.
"""

from typing import Any, Dict, Optional, List
from uuid import UUID


class DuckLakeException(Exception):
    """Base exception for all DuckLake-specific errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context,
            "cause": str(self.cause) if self.cause else None
        }


# Database-related exceptions
class DatabaseException(DuckLakeException):
    """Base class for database-related errors."""
    pass


class DatabaseConnectionError(DatabaseException):
    """Raised when database connection fails."""
    
    def __init__(self, database: str, cause: Optional[Exception] = None):
        super().__init__(
            f"Failed to connect to database: {database}",
            error_code="DB_CONNECTION_FAILED",
            context={"database": database},
            cause=cause
        )


class DatabaseQueryError(DatabaseException):
    """Raised when database query execution fails."""
    
    def __init__(
        self, 
        query: str, 
        table_name: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            f"Database query failed: {query[:100]}{'...' if len(query) > 100 else ''}",
            error_code="DB_QUERY_FAILED",
            context={
                "query": query,
                "table_name": table_name,
                "query_length": len(query)
            },
            cause=cause
        )


class TableNotFoundError(DatabaseException):
    """Raised when requested table does not exist."""
    
    def __init__(self, table_name: str):
        super().__init__(
            f"Table '{table_name}' not found",
            error_code="TABLE_NOT_FOUND",
            context={"table_name": table_name}
        )


class TableAlreadyExistsError(DatabaseException):
    """Raised when trying to create a table that already exists."""
    
    def __init__(self, table_name: str):
        super().__init__(
            f"Table '{table_name}' already exists",
            error_code="TABLE_ALREADY_EXISTS",
            context={"table_name": table_name}
        )


class SchemaValidationError(DatabaseException):
    """Raised when data doesn't match expected schema."""
    
    def __init__(
        self, 
        table_name: str, 
        expected_schema: Dict[str, str],
        validation_errors: List[str]
    ):
        super().__init__(
            f"Schema validation failed for table '{table_name}': {'; '.join(validation_errors)}",
            error_code="SCHEMA_VALIDATION_FAILED",
            context={
                "table_name": table_name,
                "expected_schema": expected_schema,
                "validation_errors": validation_errors
            }
        )


# Storage-related exceptions
class StorageException(DuckLakeException):
    """Base class for storage-related errors."""
    pass


class MinIOConnectionError(StorageException):
    """Raised when MinIO connection fails."""
    
    def __init__(self, endpoint: str, cause: Optional[Exception] = None):
        super().__init__(
            f"Failed to connect to MinIO at {endpoint}",
            error_code="MINIO_CONNECTION_FAILED",
            context={"endpoint": endpoint},
            cause=cause
        )


class BucketNotFoundError(StorageException):
    """Raised when requested bucket does not exist."""
    
    def __init__(self, bucket_name: str):
        super().__init__(
            f"Bucket '{bucket_name}' not found",
            error_code="BUCKET_NOT_FOUND",
            context={"bucket_name": bucket_name}
        )


class ObjectNotFoundError(StorageException):
    """Raised when requested object does not exist."""
    
    def __init__(self, bucket_name: str, object_name: str):
        super().__init__(
            f"Object '{object_name}' not found in bucket '{bucket_name}'",
            error_code="OBJECT_NOT_FOUND",
            context={"bucket_name": bucket_name, "object_name": object_name}
        )


class StorageQuotaExceededError(StorageException):
    """Raised when storage quota is exceeded."""
    
    def __init__(self, bucket_name: str, requested_size: int, available_size: int):
        super().__init__(
            f"Storage quota exceeded for bucket '{bucket_name}': "
            f"requested {requested_size} bytes, available {available_size} bytes",
            error_code="STORAGE_QUOTA_EXCEEDED",
            context={
                "bucket_name": bucket_name,
                "requested_size": requested_size,
                "available_size": available_size
            }
        )


# Lineage-related exceptions
class LineageException(DuckLakeException):
    """Base class for lineage-related errors."""
    pass


class LineageEventValidationError(LineageException):
    """Raised when lineage event validation fails."""
    
    def __init__(self, event_type: str, validation_errors: List[str]):
        super().__init__(
            f"Lineage event validation failed for {event_type}: {'; '.join(validation_errors)}",
            error_code="LINEAGE_VALIDATION_FAILED",
            context={
                "event_type": event_type,
                "validation_errors": validation_errors
            }
        )


class JobRunNotFoundError(LineageException):
    """Raised when requested job run does not exist."""
    
    def __init__(self, job_name: str, run_id: UUID):
        super().__init__(
            f"Job run '{run_id}' not found for job '{job_name}'",
            error_code="JOB_RUN_NOT_FOUND",
            context={"job_name": job_name, "run_id": str(run_id)}
        )


class LineageProcessingError(LineageException):
    """Raised when lineage event processing fails."""
    
    def __init__(
        self, 
        event_type: str, 
        job_name: str,
        run_id: UUID,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            f"Failed to process {event_type} event for job '{job_name}', run '{run_id}'",
            error_code="LINEAGE_PROCESSING_FAILED",
            context={
                "event_type": event_type,
                "job_name": job_name,
                "run_id": str(run_id)
            },
            cause=cause
        )


# Queue-related exceptions
class QueueException(DuckLakeException):
    """Base class for queue-related errors."""
    pass


class QueueConnectionError(QueueException):
    """Raised when queue connection fails."""
    
    def __init__(self, queue_name: str, cause: Optional[Exception] = None):
        super().__init__(
            f"Failed to connect to queue: {queue_name}",
            error_code="QUEUE_CONNECTION_FAILED",
            context={"queue_name": queue_name},
            cause=cause
        )


class MessageProcessingError(QueueException):
    """Raised when message processing fails."""
    
    def __init__(
        self, 
        queue_name: str, 
        message_id: int,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            f"Failed to process message {message_id} from queue {queue_name}",
            error_code="MESSAGE_PROCESSING_FAILED",
            context={
                "queue_name": queue_name,
                "message_id": message_id
            },
            cause=cause
        )


class DeadLetterQueueError(QueueException):
    """Raised when dead letter queue operations fail."""
    
    def __init__(
        self, 
        original_queue: str,
        dlq_name: str,
        message_id: int,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            f"Failed to move message {message_id} from {original_queue} to DLQ {dlq_name}",
            error_code="DLQ_OPERATION_FAILED",
            context={
                "original_queue": original_queue,
                "dlq_name": dlq_name,
                "message_id": message_id
            },
            cause=cause
        )


# Configuration-related exceptions
class ConfigurationException(DuckLakeException):
    """Base class for configuration-related errors."""
    pass


class InvalidConfigurationError(ConfigurationException):
    """Raised when configuration is invalid."""
    
    def __init__(self, config_key: str, config_value: Any, expected_type: str):
        super().__init__(
            f"Invalid configuration for '{config_key}': "
            f"expected {expected_type}, got {type(config_value).__name__}",
            error_code="INVALID_CONFIGURATION",
            context={
                "config_key": config_key,
                "config_value": str(config_value),
                "expected_type": expected_type,
                "actual_type": type(config_value).__name__
            }
        )


class MissingConfigurationError(ConfigurationException):
    """Raised when required configuration is missing."""
    
    def __init__(self, config_key: str):
        super().__init__(
            f"Missing required configuration: {config_key}",
            error_code="MISSING_CONFIGURATION",
            context={"config_key": config_key}
        )


# Resource-related exceptions
class ResourceException(DuckLakeException):
    """Base class for resource-related errors."""
    pass


class MemoryLimitExceededError(ResourceException):
    """Raised when memory limit is exceeded."""
    
    def __init__(self, current_usage: int, limit: int, component: str):
        super().__init__(
            f"Memory limit exceeded for {component}: "
            f"using {current_usage} bytes, limit {limit} bytes",
            error_code="MEMORY_LIMIT_EXCEEDED",
            context={
                "current_usage": current_usage,
                "limit": limit,
                "component": component,
                "usage_mb": current_usage / 1024 / 1024,
                "limit_mb": limit / 1024 / 1024
            }
        )


class TimeoutError(ResourceException):
    """Raised when operation times out."""
    
    def __init__(self, operation: str, timeout_seconds: float):
        super().__init__(
            f"Operation '{operation}' timed out after {timeout_seconds} seconds",
            error_code="OPERATION_TIMEOUT",
            context={
                "operation": operation,
                "timeout_seconds": timeout_seconds
            }
        )


class RateLimitExceededError(ResourceException):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self, 
        operation: str, 
        current_rate: float, 
        limit: float,
        window_seconds: int
    ):
        super().__init__(
            f"Rate limit exceeded for {operation}: "
            f"{current_rate:.2f} ops/sec exceeds limit of {limit:.2f} ops/sec",
            error_code="RATE_LIMIT_EXCEEDED",
            context={
                "operation": operation,
                "current_rate": current_rate,
                "limit": limit,
                "window_seconds": window_seconds
            }
        )


# Validation-related exceptions
class ValidationException(DuckLakeException):
    """Base class for validation-related errors."""
    pass


class DataValidationError(ValidationException):
    """Raised when data validation fails."""
    
    def __init__(
        self, 
        field_name: str, 
        field_value: Any,
        validation_rule: str,
        expected_format: Optional[str] = None
    ):
        super().__init__(
            f"Data validation failed for field '{field_name}': {validation_rule}",
            error_code="DATA_VALIDATION_FAILED",
            context={
                "field_name": field_name,
                "field_value": str(field_value),
                "validation_rule": validation_rule,
                "expected_format": expected_format
            }
        )


class RequestValidationError(ValidationException):
    """Raised when request validation fails."""
    
    def __init__(self, errors: List[Dict[str, Any]]):
        error_messages = [f"{err['field']}: {err['message']}" for err in errors]
        super().__init__(
            f"Request validation failed: {'; '.join(error_messages)}",
            error_code="REQUEST_VALIDATION_FAILED",
            context={"validation_errors": errors}
        ) 