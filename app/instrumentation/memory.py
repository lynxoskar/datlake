"""
Memory monitoring and instrumentation for DuckLake application.

Provides real-time memory usage tracking, garbage collection monitoring,
and memory leak detection capabilities.
"""

import gc
import psutil
import asyncio
import threading
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from prometheus_client import Gauge, Counter, Histogram
from loguru import logger

# Prometheus metrics
MEMORY_USAGE_BYTES = Gauge('ducklake_memory_usage_bytes', 'Memory usage in bytes', ['type'])
MEMORY_ALLOCATIONS = Counter('ducklake_memory_allocations_total', 'Total memory allocations', ['component'])
GC_COLLECTIONS = Counter('ducklake_gc_collections_total', 'Garbage collection runs', ['generation'])
GC_OBJECTS = Gauge('ducklake_gc_objects', 'Objects tracked by garbage collector', ['generation'])
MEMORY_LEAK_ALERTS = Counter('ducklake_memory_leak_alerts_total', 'Memory leak alerts triggered')


@dataclass
class MemorySnapshot:
    """Snapshot of memory usage at a point in time."""
    timestamp: datetime = field(default_factory=datetime.now)
    rss: int = 0  # Resident Set Size
    vms: int = 0  # Virtual Memory Size
    percent: float = 0.0  # Memory percentage
    available: int = 0  # Available system memory
    gc_objects: Dict[int, int] = field(default_factory=dict)  # Objects per GC generation
    thread_count: int = 0
    open_files: int = 0


@dataclass
class MemoryStats:
    """Memory statistics over a time period."""
    min_rss: int = 0
    max_rss: int = 0
    avg_rss: float = 0.0
    memory_growth_rate: float = 0.0  # bytes per second
    snapshots: List[MemorySnapshot] = field(default_factory=list)


class MemoryMonitor:
    """
    Comprehensive memory monitoring for the DuckLake application.
    
    Features:
    - Real-time memory usage tracking
    - Garbage collection monitoring
    - Memory leak detection
    - DuckDB and PyArrow memory tracking
    - Automatic alerting on memory issues
    """
    
    def __init__(
        self,
        sample_interval: float = 5.0,
        history_duration: int = 3600,  # 1 hour
        leak_threshold: float = 100 * 1024 * 1024,  # 100MB growth
        alert_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ):
        self.sample_interval = sample_interval
        self.history_duration = history_duration
        self.leak_threshold = leak_threshold
        self.alert_callback = alert_callback or self._default_alert_handler
        
        self.process = psutil.Process()
        self.snapshots: List[MemorySnapshot] = []
        self.monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Component-specific memory tracking
        self.component_allocations: Dict[str, int] = {}
        
        # Initialize Prometheus metrics
        self._update_prometheus_metrics()
    
    async def start_monitoring(self) -> None:
        """Start asynchronous memory monitoring."""
        if self.monitoring:
            logger.warning("Memory monitoring already started")
            return
        
        self.monitoring = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Memory monitoring started", interval=self.sample_interval)
    
    def start_monitoring_sync(self) -> None:
        """Start synchronous memory monitoring in a separate thread."""
        if self.monitoring:
            logger.warning("Memory monitoring already started")
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop_sync, daemon=True)
        self.monitor_thread.start()
        logger.info("Memory monitoring started (sync)", interval=self.sample_interval)
    
    async def stop_monitoring(self) -> None:
        """Stop memory monitoring."""
        self.monitoring = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Memory monitoring stopped")
    
    def stop_monitoring_sync(self) -> None:
        """Stop synchronous memory monitoring."""
        self.monitoring = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        
        logger.info("Memory monitoring stopped (sync)")
    
    def take_snapshot(self) -> MemorySnapshot:
        """Take a memory snapshot."""
        try:
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            system_memory = psutil.virtual_memory()
            
            # Garbage collection info
            gc_objects = {}
            for i in range(3):  # 3 GC generations
                gc_objects[i] = len(gc.get_objects(i))
            
            # Process info
            try:
                thread_count = self.process.num_threads()
                open_files = len(self.process.open_files())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                thread_count = 0
                open_files = 0
            
            snapshot = MemorySnapshot(
                timestamp=datetime.now(),
                rss=memory_info.rss,
                vms=memory_info.vms,
                percent=memory_percent,
                available=system_memory.available,
                gc_objects=gc_objects,
                thread_count=thread_count,
                open_files=open_files
            )
            
            # Store snapshot with history management
            self._add_snapshot(snapshot)
            
            # Update metrics
            self._update_prometheus_metrics()
            
            # Check for memory leaks
            self._check_memory_leaks()
            
            return snapshot
            
        except Exception as e:
            logger.error("Failed to take memory snapshot", error=str(e))
            return MemorySnapshot()
    
    def get_stats(self, duration_minutes: int = 60) -> MemoryStats:
        """Get memory statistics for the specified duration."""
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
        recent_snapshots = [
            s for s in self.snapshots 
            if s.timestamp >= cutoff_time
        ]
        
        if not recent_snapshots:
            return MemoryStats()
        
        rss_values = [s.rss for s in recent_snapshots]
        
        # Calculate growth rate
        growth_rate = 0.0
        if len(recent_snapshots) >= 2:
            time_diff = (recent_snapshots[-1].timestamp - recent_snapshots[0].timestamp).total_seconds()
            if time_diff > 0:
                memory_diff = recent_snapshots[-1].rss - recent_snapshots[0].rss
                growth_rate = memory_diff / time_diff
        
        return MemoryStats(
            min_rss=min(rss_values),
            max_rss=max(rss_values),
            avg_rss=sum(rss_values) / len(rss_values),
            memory_growth_rate=growth_rate,
            snapshots=recent_snapshots
        )
    
    def track_allocation(self, component: str, size_bytes: int) -> None:
        """Track memory allocation for a specific component."""
        self.component_allocations[component] = self.component_allocations.get(component, 0) + size_bytes
        MEMORY_ALLOCATIONS.labels(component=component).inc(size_bytes)
        
        logger.debug(
            "Memory allocation tracked",
            component=component,
            size_bytes=size_bytes,
            total_bytes=self.component_allocations[component]
        )
    
    def force_garbage_collection(self) -> Dict[str, int]:
        """Force garbage collection and return statistics."""
        logger.info("Forcing garbage collection")
        
        before_objects = {gen: len(gc.get_objects(gen)) for gen in range(3)}
        
        # Force collection for each generation
        collected = {}
        for gen in range(3):
            collected[gen] = gc.collect(gen)
            GC_COLLECTIONS.labels(generation=str(gen)).inc()
        
        after_objects = {gen: len(gc.get_objects(gen)) for gen in range(3)}
        
        logger.info(
            "Garbage collection completed",
            collected=collected,
            before_objects=before_objects,
            after_objects=after_objects
        )
        
        return collected
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Get comprehensive memory information."""
        current_snapshot = self.take_snapshot()
        stats = self.get_stats()
        
        return {
            "current": {
                "rss_mb": current_snapshot.rss / 1024 / 1024,
                "vms_mb": current_snapshot.vms / 1024 / 1024,
                "percent": current_snapshot.percent,
                "available_mb": current_snapshot.available / 1024 / 1024,
                "thread_count": current_snapshot.thread_count,
                "open_files": current_snapshot.open_files,
                "gc_objects": current_snapshot.gc_objects
            },
            "stats": {
                "min_rss_mb": stats.min_rss / 1024 / 1024,
                "max_rss_mb": stats.max_rss / 1024 / 1024,
                "avg_rss_mb": stats.avg_rss / 1024 / 1024,
                "growth_rate_mb_per_sec": stats.memory_growth_rate / 1024 / 1024
            },
            "components": {
                comp: size / 1024 / 1024 
                for comp, size in self.component_allocations.items()
            }
        }
    
    async def _monitoring_loop(self) -> None:
        """Asynchronous monitoring loop."""
        while self.monitoring:
            try:
                self.take_snapshot()
                await asyncio.sleep(self.sample_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in memory monitoring loop", error=str(e))
                await asyncio.sleep(self.sample_interval)
    
    def _monitoring_loop_sync(self) -> None:
        """Synchronous monitoring loop."""
        while self.monitoring:
            try:
                self.take_snapshot()
                time.sleep(self.sample_interval)
            except Exception as e:
                logger.error("Error in memory monitoring loop", error=str(e))
                time.sleep(self.sample_interval)
    
    def _add_snapshot(self, snapshot: MemorySnapshot) -> None:
        """Add snapshot to history with cleanup."""
        self.snapshots.append(snapshot)
        
        # Clean up old snapshots
        cutoff_time = datetime.now() - timedelta(seconds=self.history_duration)
        self.snapshots = [s for s in self.snapshots if s.timestamp >= cutoff_time]
    
    def _update_prometheus_metrics(self) -> None:
        """Update Prometheus metrics."""
        if not self.snapshots:
            return
        
        latest = self.snapshots[-1]
        
        MEMORY_USAGE_BYTES.labels(type='rss').set(latest.rss)
        MEMORY_USAGE_BYTES.labels(type='vms').set(latest.vms)
        MEMORY_USAGE_BYTES.labels(type='available').set(latest.available)
        
        for gen, count in latest.gc_objects.items():
            GC_OBJECTS.labels(generation=str(gen)).set(count)
    
    def _check_memory_leaks(self) -> None:
        """Check for potential memory leaks."""
        if len(self.snapshots) < 10:  # Need enough data points
            return
        
        # Check growth over last 10 snapshots
        recent_snapshots = self.snapshots[-10:]
        growth = recent_snapshots[-1].rss - recent_snapshots[0].rss
        
        if growth > self.leak_threshold:
            MEMORY_LEAK_ALERTS.inc()
            
            alert_data = {
                "growth_bytes": growth,
                "growth_mb": growth / 1024 / 1024,
                "threshold_mb": self.leak_threshold / 1024 / 1024,
                "current_rss_mb": recent_snapshots[-1].rss / 1024 / 1024,
                "time_window": f"{len(recent_snapshots)} samples"
            }
            
            self.alert_callback("memory_leak_detected", alert_data)
    
    def _default_alert_handler(self, alert_type: str, data: Dict[str, Any]) -> None:
        """Default alert handler."""
        logger.warning(
            f"Memory alert: {alert_type}",
            alert_type=alert_type,
            **data
        )


# Global memory monitor instance
memory_monitor = MemoryMonitor()


def setup_memory_monitoring(
    sample_interval: float = 5.0,
    auto_start: bool = True,
    alert_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
) -> MemoryMonitor:
    """
    Setup and configure memory monitoring.
    
    Args:
        sample_interval: Sampling interval in seconds
        auto_start: Whether to start monitoring immediately
        alert_callback: Custom alert handler function
        
    Returns:
        Configured MemoryMonitor instance
    """
    global memory_monitor
    
    memory_monitor = MemoryMonitor(
        sample_interval=sample_interval,
        alert_callback=alert_callback
    )
    
    if auto_start:
        memory_monitor.start_monitoring_sync()
    
    logger.info("Memory monitoring configured", sample_interval=sample_interval)
    return memory_monitor 