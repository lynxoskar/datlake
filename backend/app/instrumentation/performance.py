"""
Performance monitoring and instrumentation for DuckLake application.

Provides request timing, throughput tracking, database performance monitoring,
and comprehensive metrics collection.
"""

import time
import asyncio
from typing import Dict, Any, Optional, List, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from prometheus_client import Counter, Histogram, Gauge, Summary
from loguru import logger
import duckdb
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# Prometheus metrics
REQUEST_COUNT = Counter('ducklake_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('ducklake_request_duration_seconds', 'Request duration', ['method', 'endpoint'])
REQUEST_SIZE = Histogram('ducklake_request_size_bytes', 'Request size in bytes', ['method', 'endpoint'])
RESPONSE_SIZE = Histogram('ducklake_response_size_bytes', 'Response size in bytes', ['method', 'endpoint'])

DATABASE_QUERY_COUNT = Counter('ducklake_database_queries_total', 'Total database queries', ['operation'])
DATABASE_QUERY_DURATION = Histogram('ducklake_database_query_duration_seconds', 'Database query duration', ['operation'])
DATABASE_CONNECTIONS = Gauge('ducklake_database_connections', 'Active database connections')

THROUGHPUT_RPS = Gauge('ducklake_throughput_requests_per_second', 'Requests per second')
ACTIVE_REQUESTS = Gauge('ducklake_active_requests', 'Currently active requests')

MINIO_OPERATIONS = Counter('ducklake_minio_operations_total', 'MinIO operations', ['operation', 'status'])
MINIO_OPERATION_DURATION = Histogram('ducklake_minio_operation_duration_seconds', 'MinIO operation duration', ['operation'])

LINEAGE_EVENTS = Counter('ducklake_lineage_events_total', 'Lineage events processed', ['event_type', 'status'])
LINEAGE_PROCESSING_DURATION = Histogram('ducklake_lineage_processing_duration_seconds', 'Lineage processing duration')


@dataclass
class RequestMetrics:
    """Metrics for a single request."""
    start_time: float = field(default_factory=time.time)
    method: str = ""
    endpoint: str = ""
    status_code: int = 0
    duration: float = 0.0
    request_size: int = 0
    response_size: int = 0
    query_count: int = 0
    query_duration: float = 0.0


@dataclass
class ThroughputStats:
    """Throughput statistics."""
    timestamp: datetime = field(default_factory=datetime.now)
    requests_per_second: float = 0.0
    avg_response_time: float = 0.0
    error_rate: float = 0.0
    active_requests: int = 0


class PerformanceTracker:
    """Track performance metrics for individual operations."""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = time.time()
        self.metrics: Dict[str, Any] = {}
    
    def add_metric(self, key: str, value: Any) -> None:
        """Add a custom metric."""
        self.metrics[key] = value
    
    def finish(self) -> float:
        """Finish tracking and return duration."""
        duration = time.time() - self.start_time
        
        logger.debug(
            "Operation completed",
            operation=self.operation_name,
            duration=duration,
            **self.metrics
        )
        
        return duration


class DatabasePerformanceMonitor:
    """Monitor DuckDB performance."""
    
    def __init__(self):
        self.active_queries: Set[str] = set()
        self.query_stats: List[Dict[str, Any]] = []
    
    @contextmanager
    def track_query(self, operation: str, query: str = ""):
        """Context manager to track database query performance."""
        query_id = f"{operation}_{id(query)}"
        start_time = time.time()
        
        self.active_queries.add(query_id)
        DATABASE_CONNECTIONS.set(len(self.active_queries))
        
        try:
            yield query_id
        finally:
            duration = time.time() - start_time
            self.active_queries.discard(query_id)
            
            DATABASE_QUERY_COUNT.labels(operation=operation).inc()
            DATABASE_QUERY_DURATION.labels(operation=operation).observe(duration)
            DATABASE_CONNECTIONS.set(len(self.active_queries))
            
            query_stat = {
                "query_id": query_id,
                "operation": operation,
                "duration": duration,
                "timestamp": datetime.now(),
                "query": query[:100] + "..." if len(query) > 100 else query
            }
            
            self.query_stats.append(query_stat)
            
            # Keep only recent stats
            cutoff_time = datetime.now() - timedelta(hours=1)
            self.query_stats = [
                stat for stat in self.query_stats 
                if stat["timestamp"] >= cutoff_time
            ]
            
            logger.debug(
                "Database query completed",
                operation=operation,
                duration=duration,
                query_preview=query[:50] + "..." if len(query) > 50 else query
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database performance statistics."""
        if not self.query_stats:
            return {
                "total_queries": 0,
                "avg_duration": 0.0,
                "active_queries": len(self.active_queries)
            }
        
        durations = [stat["duration"] for stat in self.query_stats]
        operations = [stat["operation"] for stat in self.query_stats]
        
        operation_counts = {}
        for op in operations:
            operation_counts[op] = operation_counts.get(op, 0) + 1
        
        return {
            "total_queries": len(self.query_stats),
            "avg_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "active_queries": len(self.active_queries),
            "operations": operation_counts
        }


class MinIOPerformanceMonitor:
    """Monitor MinIO operation performance."""
    
    @contextmanager
    def track_operation(self, operation: str):
        """Context manager to track MinIO operation performance."""
        start_time = time.time()
        status = "success"
        
        try:
            yield
        except Exception as e:
            status = "error"
            logger.error(f"MinIO operation failed", operation=operation, error=str(e))
            raise
        finally:
            duration = time.time() - start_time
            
            MINIO_OPERATIONS.labels(operation=operation, status=status).inc()
            MINIO_OPERATION_DURATION.labels(operation=operation).observe(duration)
            
            logger.debug(
                "MinIO operation completed",
                operation=operation,
                duration=duration,
                status=status
            )


class PerformanceMonitor:
    """
    Comprehensive performance monitoring for the DuckLake application.
    
    Features:
    - Request timing and throughput tracking
    - Database performance monitoring
    - MinIO operation tracking
    - Lineage processing performance
    - Custom operation tracking
    """
    
    def __init__(self):
        self.request_history: List[RequestMetrics] = []
        self.active_requests: Dict[str, RequestMetrics] = {}
        self.throughput_stats: List[ThroughputStats] = []
        
        self.db_monitor = DatabasePerformanceMonitor()
        self.minio_monitor = MinIOPerformanceMonitor()
        
        # Start throughput calculation task
        self._start_throughput_calculation()
    
    def start_request(self, request_id: str, method: str, endpoint: str, request_size: int = 0) -> None:
        """Start tracking a request."""
        metrics = RequestMetrics(
            method=method,
            endpoint=endpoint,
            request_size=request_size
        )
        
        self.active_requests[request_id] = metrics
        ACTIVE_REQUESTS.set(len(self.active_requests))
        
        logger.debug(
            "Request started",
            request_id=request_id,
            method=method,
            endpoint=endpoint
        )
    
    def finish_request(
        self, 
        request_id: str, 
        status_code: int, 
        response_size: int = 0,
        query_count: int = 0,
        query_duration: float = 0.0
    ) -> float:
        """Finish tracking a request and return duration."""
        if request_id not in self.active_requests:
            logger.warning("Request not found in active requests", request_id=request_id)
            return 0.0
        
        metrics = self.active_requests.pop(request_id)
        metrics.duration = time.time() - metrics.start_time
        metrics.status_code = status_code
        metrics.response_size = response_size
        metrics.query_count = query_count
        metrics.query_duration = query_duration
        
        # Update Prometheus metrics
        REQUEST_COUNT.labels(
            method=metrics.method,
            endpoint=metrics.endpoint,
            status=str(status_code)
        ).inc()
        
        REQUEST_DURATION.labels(
            method=metrics.method,
            endpoint=metrics.endpoint
        ).observe(metrics.duration)
        
        REQUEST_SIZE.labels(
            method=metrics.method,
            endpoint=metrics.endpoint
        ).observe(metrics.request_size)
        
        RESPONSE_SIZE.labels(
            method=metrics.method,
            endpoint=metrics.endpoint
        ).observe(metrics.response_size)
        
        ACTIVE_REQUESTS.set(len(self.active_requests))
        
        # Store in history
        self.request_history.append(metrics)
        
        # Clean up old history
        cutoff_time = time.time() - 3600  # 1 hour
        self.request_history = [
            r for r in self.request_history 
            if r.start_time >= cutoff_time
        ]
        
        logger.info(
            "Request completed",
            request_id=request_id,
            method=metrics.method,
            endpoint=metrics.endpoint,
            status_code=status_code,
            duration=metrics.duration,
            query_count=query_count
        )
        
        return metrics.duration
    
    @asynccontextmanager
    async def track_async_operation(self, operation_name: str):
        """Context manager for tracking async operations."""
        tracker = PerformanceTracker(operation_name)
        try:
            yield tracker
        finally:
            tracker.finish()
    
    @contextmanager
    def track_operation(self, operation_name: str):
        """Context manager for tracking synchronous operations."""
        tracker = PerformanceTracker(operation_name)
        try:
            yield tracker
        finally:
            tracker.finish()
    
    def track_lineage_event(self, event_type: str, processing_duration: float, success: bool = True) -> None:
        """Track lineage event processing."""
        status = "success" if success else "error"
        
        LINEAGE_EVENTS.labels(event_type=event_type, status=status).inc()
        LINEAGE_PROCESSING_DURATION.observe(processing_duration)
        
        logger.debug(
            "Lineage event processed",
            event_type=event_type,
            duration=processing_duration,
            success=success
        )
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        # Recent request stats
        recent_requests = [
            r for r in self.request_history
            if r.start_time >= time.time() - 300  # Last 5 minutes
        ]
        
        request_stats = {}
        if recent_requests:
            durations = [r.duration for r in recent_requests]
            request_stats = {
                "total_requests": len(recent_requests),
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "requests_per_second": len(recent_requests) / 300,
                "error_rate": sum(1 for r in recent_requests if r.status_code >= 400) / len(recent_requests)
            }
        
        return {
            "requests": request_stats,
            "database": self.db_monitor.get_stats(),
            "active_requests": len(self.active_requests),
            "throughput": self.throughput_stats[-1].__dict__ if self.throughput_stats else {}
        }
    
    def _start_throughput_calculation(self) -> None:
        """Start background task to calculate throughput."""
        def calculate_throughput():
            while True:
                try:
                    # Calculate throughput for last minute
                    cutoff_time = time.time() - 60
                    recent_requests = [
                        r for r in self.request_history
                        if r.start_time >= cutoff_time
                    ]
                    
                    if recent_requests:
                        rps = len(recent_requests) / 60
                        avg_response_time = sum(r.duration for r in recent_requests) / len(recent_requests)
                        error_count = sum(1 for r in recent_requests if r.status_code >= 400)
                        error_rate = error_count / len(recent_requests)
                    else:
                        rps = 0.0
                        avg_response_time = 0.0
                        error_rate = 0.0
                    
                    stats = ThroughputStats(
                        requests_per_second=rps,
                        avg_response_time=avg_response_time,
                        error_rate=error_rate,
                        active_requests=len(self.active_requests)
                    )
                    
                    self.throughput_stats.append(stats)
                    
                    # Update Prometheus metric
                    THROUGHPUT_RPS.set(rps)
                    
                    # Keep only recent stats
                    cutoff_stats_time = datetime.now() - timedelta(hours=1)
                    self.throughput_stats = [
                        s for s in self.throughput_stats
                        if s.timestamp >= cutoff_stats_time
                    ]
                    
                    time.sleep(10)  # Update every 10 seconds
                    
                except Exception as e:
                    logger.error("Error calculating throughput", error=str(e))
                    time.sleep(10)
        
        import threading
        thread = threading.Thread(target=calculate_throughput, daemon=True)
        thread.start()


class PerformanceMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for automatic performance tracking."""
    
    def __init__(self, app, performance_monitor: PerformanceMonitor):
        super().__init__(app)
        self.performance_monitor = performance_monitor
    
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = f"{request.method}_{id(request)}"
        
        # Get request size
        content_length = request.headers.get("content-length", "0")
        request_size = int(content_length) if content_length.isdigit() else 0
        
        # Extract endpoint pattern
        endpoint = str(request.url.path)
        
        # Start tracking
        self.performance_monitor.start_request(
            request_id=request_id,
            method=request.method,
            endpoint=endpoint,
            request_size=request_size
        )
        
        try:
            response = await call_next(request)
            
            # Get response size
            response_size = 0
            if hasattr(response, 'headers') and 'content-length' in response.headers:
                response_size = int(response.headers['content-length'])
            
            # Finish tracking
            self.performance_monitor.finish_request(
                request_id=request_id,
                status_code=response.status_code,
                response_size=response_size
            )
            
            return response
            
        except Exception as e:
            # Finish tracking with error
            self.performance_monitor.finish_request(
                request_id=request_id,
                status_code=500
            )
            raise


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


def setup_performance_monitoring() -> PerformanceMonitor:
    """Setup and configure performance monitoring."""
    logger.info("Performance monitoring configured")
    return performance_monitor


# Decorators for easy performance tracking
def track_performance(operation_name: str):
    """Decorator to track function performance."""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                async with performance_monitor.track_async_operation(operation_name) as tracker:
                    try:
                        result = await func(*args, **kwargs)
                        tracker.add_metric("success", True)
                        return result
                    except Exception as e:
                        tracker.add_metric("success", False)
                        tracker.add_metric("error", str(e))
                        raise
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                with performance_monitor.track_operation(operation_name) as tracker:
                    try:
                        result = func(*args, **kwargs)
                        tracker.add_metric("success", True)
                        return result
                    except Exception as e:
                        tracker.add_metric("success", False)
                        tracker.add_metric("error", str(e))
                        raise
            return sync_wrapper
    return decorator 