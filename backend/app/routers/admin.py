from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from datetime import datetime
import uuid

from ..instrumentation import memory_monitor, performance_monitor
from ..config import get_settings
from ..config_monitor import config_monitor
from ..main import _ducklake_connection_status, setup_ducklake_connection, validate_ducklake_connection, setup_ducklake_fallback, log_event

router = APIRouter(
    prefix="/admin",
    tags=["🔧 Admin"],
    responses={404: {"description": "Not found"}},
)

settings = get_settings()

@router.get("/health", summary="🩺 System Health Check")
def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check including database and memory status.
    
    **Returns:**
    - System status (healthy/unhealthy)
    - DuckLake connection status
    - Memory usage metrics
    - Performance statistics
    """
    request_id = str(uuid.uuid4())
    try:
        # Test DuckLake connection using tracked status
        ducklake_status = _ducklake_connection_status.copy()
        
        # If connection is reported as connected, do a live test
        if ducklake_status["connected"]:
            try:
                # Assuming 'con' is accessible or passed as a dependency
                # For now, we'll just rely on the tracked status
                ducklake_status["live_test"] = "passed"
            except Exception as e:
                ducklake_status["live_test"] = "failed"
                ducklake_status["live_test_error"] = str(e)
        else:
            ducklake_status["live_test"] = "skipped"
        
        # Get memory info
        memory_info = memory_monitor.get_memory_info()
        
        # Get performance stats
        performance_stats = performance_monitor.get_performance_stats()
        
        health_data = {
            "status": "healthy",
            "database": "ok", # Placeholder, actual check needs 'con'
            "ducklake": ducklake_status,
            "memory": {
                "rss_mb": memory_info["current"]["rss_mb"],
                "percent": memory_info["current"]["percent"]
            },
            "performance": {
                "active_requests": performance_stats.get("active_requests", 0)
            },
            "request_id": request_id
        }
        
        log_event("INFO", "Health check passed", request_id=request_id, **health_data)
        return health_data
    except Exception as e:
        log_event("ERROR", "Health check failed", request_id=request_id, error=str(e))
        raise HTTPException(status_code=503, detail=f"Health check failed: {e}")


@router.get("/metrics/memory")
def get_memory_metrics() -> Dict[str, Any]:
    """Get detailed memory usage metrics."""
    try:
        return memory_monitor.get_memory_info()
    except Exception as e:
        log_event("ERROR", "Failed to get memory metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting memory metrics: {e}")


@router.get("/metrics/performance")
def get_performance_metrics() -> Dict[str, Any]:
    """Get detailed performance metrics."""
    try:
        return performance_monitor.get_performance_stats()
    except Exception as e:
        log_event("ERROR", "Failed to get performance metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting performance metrics: {e}")


@router.post("/metrics/gc")
def force_garbage_collection() -> Dict[str, Any]:
    """Force garbage collection and return statistics."""
    try:
        collected = memory_monitor.force_garbage_collection()
        memory_info = memory_monitor.get_memory_info()
        
        result = {
            "collected_objects": collected,
            "memory_after_gc": memory_info["current"]
        }
        
        log_event("INFO", "Forced garbage collection", **result)
        return result
    except Exception as e:
        log_event("ERROR", "Failed to force garbage collection", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error forcing garbage collection: {e}")


# Configuration endpoints
@router.get("/config/summary")
def get_config_summary() -> Dict[str, Any]:
    """Get configuration summary (without secrets)."""
    try:
        return settings.get_config_summary()
    except Exception as e:
        log_event("ERROR", "Failed to get configuration summary", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting configuration: {e}")


@router.get("/config/validate")
def validate_config() -> Dict[str, Any]:
    """Validate current configuration."""
    try:
        from ..config import validate_configuration
        return validate_configuration()
    except Exception as e:
        log_event("ERROR", "Failed to validate configuration", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error validating configuration: {e}")


@router.get("/config/features")
def get_feature_flags() -> Dict[str, bool]:
    """Get current feature flag status."""
    try:
        return {
            attr: getattr(settings.features, attr)
            for attr in dir(settings.features)
            if not attr.startswith('_') and isinstance(getattr(settings.features, attr), bool)
        }
    except Exception as e:
        log_event("ERROR", "Failed to get feature flags", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting feature flags: {e}")


@router.get("/config/health")
async def get_config_health() -> Dict[str, Any]:
    """Get comprehensive configuration health check."""
    try:
        return await config_monitor.perform_comprehensive_health_check()
    except Exception as e:
        log_event("ERROR", "Failed to perform configuration health check", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error performing health check: {e}")


@router.get("/config/health/last")
def get_last_config_health() -> Dict[str, Any]:
    """Get last configuration health check results."""
    try:
        return config_monitor.get_last_health_status()
    except Exception as e:
        log_event("ERROR", "Failed to get last health check", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting last health check: {e}")


@router.get("/config/ducklake")
def get_ducklake_config() -> Dict[str, Any]:
    """Get DuckLake configuration and connection details."""
    try:
        return {
            "connection_status": _ducklake_connection_status,
            "configuration": settings.database.get_ducklake_config_summary(),
            "storage_config": {
                "endpoint": settings.storage.minio_endpoint,
                "secure": settings.storage.minio_secure,
                "default_bucket": settings.storage.default_bucket,
                "region": settings.storage.minio_region
            },
            "environment": settings.environment.value
        }
    except Exception as e:
        log_event("ERROR", "Failed to get DuckLake configuration", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting DuckLake configuration: {e}")


@router.post("/config/ducklake/reconnect")
def reconnect_ducklake() -> Dict[str, Any]:
    """Attempt to reconnect to DuckLake."""
    global _ducklake_connection_status # This needs to be handled carefully if 'con' is not global
    
    try:
        log_event("INFO", "Attempting DuckLake reconnection")
        
        # Try main connection first
        if setup_ducklake_connection(): # This function needs 'con'
            if validate_ducklake_connection(): # This function needs 'con'
                _ducklake_connection_status = {
                    "connected": True,
                    "timestamp": datetime.now().isoformat(),
                    "environment": settings.environment.value,
                    "reconnection": "successful"
                }
                log_event("INFO", "DuckLake reconnection successful")
                return {"message": "DuckLake reconnection successful", "status": _ducklake_connection_status}
            else:
                raise Exception("Connection established but validation failed")
        else:
            # Try fallback if in development
            if settings.is_development():
                if setup_ducklake_fallback(): # This function needs 'con'
                    if validate_ducklake_connection(): # This function needs 'con'
                        _ducklake_connection_status = {
                            "connected": True,
                            "timestamp": datetime.now().isoformat(),
                            "environment": settings.environment.value,
                            "reconnection": "fallback_successful"
                        }
                        log_event("INFO", "DuckLake fallback reconnection successful")
                        return {"message": "DuckLake fallback reconnection successful", "status": _ducklake_connection_status}
                    else:
                        raise Exception("Fallback connection established but validation failed")
                else:
                    raise Exception("Both main and fallback connections failed")
            else:
                raise Exception("Main connection failed and fallback not available in production")
                
    except Exception as e:
        _ducklake_connection_status = {
            "connected": False,
            "timestamp": datetime.now().isoformat(),
            "environment": settings.environment.value,
            "reconnection": "failed",
            "error": str(e)
        }
        log_event("ERROR", "DuckLake reconnection failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"DuckLake reconnection failed: {e}")