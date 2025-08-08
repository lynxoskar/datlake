"""
Server-Sent Events (SSE) Manager for real-time event streaming
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import orjson
from loguru import logger
from fastapi import Request
from fastapi.responses import StreamingResponse


class EventType(str, Enum):
    """Types of SSE events"""
    LINEAGE_EVENT = "lineage_event"
    JOB_STATUS = "job_status"
    QUEUE_STATUS = "queue_status"
    SYSTEM_METRIC = "system_metric"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    PING = "ping"  # For zombie detection


@dataclass
class SSEEvent:
    """Server-Sent Event structure"""
    event_type: EventType
    data: Dict[str, Any]
    event_id: Optional[str] = None
    retry: Optional[int] = None
    timestamp: float = field(default_factory=time.time)
    
    def __post_init__(self):
        if self.event_id is None:
            self.event_id = str(uuid.uuid4())
    
    def format_sse(self) -> str:
        """Format event for SSE transmission"""
        lines = []
        
        # Add event ID
        if self.event_id:
            lines.append(f"id: {self.event_id}")
        
        # Add event type
        lines.append(f"event: {self.event_type}")
        
        # Add retry interval
        if self.retry:
            lines.append(f"retry: {self.retry}")
        
        # Add data (JSON serialized)
        event_data = {
            "timestamp": self.timestamp,
            "data": self.data
        }
        lines.append(f"data: {orjson.dumps(event_data).decode('utf-8')}")
        
        # End with double newline
        lines.append("")
        lines.append("")
        
        return "\n".join(lines)


@dataclass
class SSEClient:
    """SSE client connection"""
    client_id: str
    request: Request
    subscriptions: Set[EventType] = field(default_factory=set)
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=100))
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    last_pong: Optional[float] = None
    ping_count: int = 0
    missed_pings: int = 0
    queue_full_count: int = 0
    write_errors: int = 0
    is_zombie: bool = False
    zombie_detected_at: Optional[float] = None
    
    def __post_init__(self):
        if not self.client_id:
            self.client_id = str(uuid.uuid4())
    
    def update_ping(self):
        """Update ping timestamp"""
        self.last_ping = time.time()
        self.ping_count += 1
    
    def update_pong(self):
        """Update pong timestamp (client response)"""
        self.last_pong = time.time()
        self.missed_pings = 0
    
    def mark_zombie(self, reason: str):
        """Mark client as zombie"""
        if not self.is_zombie:
            self.is_zombie = True
            self.zombie_detected_at = time.time()
            logger.warning(f"Client {self.client_id} marked as zombie: {reason}")
    
    def is_connection_healthy(self) -> bool:
        """Check if connection appears healthy"""
        current_time = time.time()
        
        # Check for basic timeout
        if current_time - self.last_ping > 120:  # 2 minutes
            return False
        
        # Check for excessive missed pings
        if self.missed_pings > 3:
            return False
        
        # Check for excessive queue fullness
        if self.queue_full_count > 10:
            return False
        
        # Check for excessive write errors
        if self.write_errors > 5:
            return False
        
        return True


class SSEManager:
    """Manager for Server-Sent Events connections and broadcasting"""
    
    def __init__(self):
        self.clients: Dict[str, SSEClient] = {}
        self.event_history: List[SSEEvent] = []
        self.max_history = 1000
        self.heartbeat_interval = 30  # seconds
        self.ping_interval = 45  # seconds for zombie detection
        self.zombie_check_interval = 60  # seconds
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.zombie_detection_task: Optional[asyncio.Task] = None
        self.running = False
        self.zombie_stats = {
            "total_detected": 0,
            "detection_reasons": {},
            "last_cleanup": None
        }
    
    async def start(self):
        """Start the SSE manager"""
        if self.running:
            return
        
        self.running = True
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self.zombie_detection_task = asyncio.create_task(self._zombie_detection_loop())
        logger.info("SSE Manager started with zombie detection")
    
    async def stop(self):
        """Stop the SSE manager"""
        if not self.running:
            return
        
        self.running = False
        
        # Cancel background tasks
        for task in [self.heartbeat_task, self.zombie_detection_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Disconnect all clients
        for client in list(self.clients.values()):
            await self._disconnect_client(client.client_id)
        
        logger.info("SSE Manager stopped")
    
    async def connect_client(self, request: Request, subscriptions: Optional[List[EventType]] = None) -> str:
        """Connect a new SSE client"""
        client_id = str(uuid.uuid4())
        
        # Default subscriptions
        if subscriptions is None:
            subscriptions = [EventType.LINEAGE_EVENT, EventType.JOB_STATUS, EventType.SYSTEM_METRIC]
        
        client = SSEClient(
            client_id=client_id,
            request=request,
            subscriptions=set(subscriptions)
        )
        
        self.clients[client_id] = client
        
        logger.info(f"SSE client connected: {client_id}, subscriptions: {subscriptions}")
        
        # Send recent events to new client
        await self._send_recent_events(client)
        
        return client_id
    
    async def disconnect_client(self, client_id: str):
        """Disconnect an SSE client"""
        await self._disconnect_client(client_id)
    
    async def _disconnect_client(self, client_id: str):
        """Internal method to disconnect a client"""
        if client_id in self.clients:
            client = self.clients[client_id]
            duration = time.time() - client.connected_at
            
            # Log zombie information if applicable
            if client.is_zombie:
                zombie_duration = time.time() - (client.zombie_detected_at or client.connected_at)
                logger.info(f"Zombie client disconnected: {client_id}, duration: {duration:.1f}s, "
                           f"zombie_duration: {zombie_duration:.1f}s, missed_pings: {client.missed_pings}")
            else:
                logger.info(f"SSE client disconnected: {client_id}, duration: {duration:.1f}s")
            
            del self.clients[client_id]
    
    async def broadcast_event(self, event: SSEEvent, target_clients: Optional[List[str]] = None):
        """Broadcast an event to connected clients"""
        # Add to history
        self.event_history.append(event)
        if len(self.event_history) > self.max_history:
            self.event_history.pop(0)
        
        # Determine target clients
        if target_clients is None:
            targets = [
                client for client in self.clients.values() 
                if event.event_type in client.subscriptions and not client.is_zombie
            ]
        else:
            targets = [
                self.clients[client_id] for client_id in target_clients 
                if client_id in self.clients and event.event_type in client.subscriptions and not self.clients[client_id].is_zombie
            ]
        
        # Send to clients
        failed_clients = []
        for client in targets:
            try:
                await client.queue.put(event)
                client.queue_full_count = 0  # Reset on successful put
            except asyncio.QueueFull:
                client.queue_full_count += 1
                logger.warning(f"Client {client.client_id} queue full (count: {client.queue_full_count})")
                
                # Mark as zombie if queue is consistently full
                if client.queue_full_count > 10:
                    client.mark_zombie("queue_consistently_full")
                    failed_clients.append(client.client_id)
            except Exception as e:
                logger.error(f"Error sending event to client {client.client_id}: {e}")
                failed_clients.append(client.client_id)
        
        # Remove failed clients
        for client_id in failed_clients:
            await self._disconnect_client(client_id)
        
        logger.debug(f"Broadcasted {event.event_type} event to {len(targets)} clients")
    
    async def broadcast_lineage_event(self, event_type: str, run_id: str, job_name: str, status: str, metadata: Dict[str, Any] = None):
        """Broadcast a lineage event"""
        sse_event = SSEEvent(
            event_type=EventType.LINEAGE_EVENT,
            data={
                "event_type": event_type,
                "run_id": run_id,
                "job_name": job_name,
                "status": status,
                "metadata": metadata or {}
            }
        )
        await self.broadcast_event(sse_event)
    
    async def broadcast_job_status(self, job_name: str, run_id: str, status: str, progress: Optional[int] = None):
        """Broadcast job status update"""
        sse_event = SSEEvent(
            event_type=EventType.JOB_STATUS,
            data={
                "job_name": job_name,
                "run_id": run_id,
                "status": status,
                "progress": progress
            }
        )
        await self.broadcast_event(sse_event)
    
    async def broadcast_queue_status(self, queue_stats: Dict[str, Any]):
        """Broadcast queue status"""
        sse_event = SSEEvent(
            event_type=EventType.QUEUE_STATUS,
            data=queue_stats
        )
        await self.broadcast_event(sse_event)
    
    async def broadcast_system_metric(self, metric_type: str, value: Any, metadata: Dict[str, Any] = None):
        """Broadcast system metric"""
        sse_event = SSEEvent(
            event_type=EventType.SYSTEM_METRIC,
            data={
                "metric_type": metric_type,
                "value": value,
                "metadata": metadata or {}
            }
        )
        await self.broadcast_event(sse_event)
    
    async def broadcast_error(self, error_type: str, message: str, details: Dict[str, Any] = None):
        """Broadcast error event"""
        sse_event = SSEEvent(
            event_type=EventType.ERROR,
            data={
                "error_type": error_type,
                "message": message,
                "details": details or {}
            }
        )
        await self.broadcast_event(sse_event)
    
    async def stream_events(self, client_id: str):
        """Stream events to a specific client"""
        if client_id not in self.clients:
            return
        
        client = self.clients[client_id]
        
        try:
            while self.running and client_id in self.clients and not client.is_zombie:
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(client.queue.get(), timeout=30.0)
                    
                    # Try to yield the event (this can detect broken connections)
                    try:
                        yield event.format_sse()
                        client.update_ping()
                        client.write_errors = 0  # Reset on successful write
                    except Exception as write_error:
                        client.write_errors += 1
                        logger.warning(f"Write error for client {client_id}: {write_error}")
                        
                        # Mark as zombie after multiple write errors
                        if client.write_errors > 3:
                            client.mark_zombie("write_errors")
                            break
                        
                except asyncio.TimeoutError:
                    # Send heartbeat/ping
                    if client.ping_count % 2 == 0:  # Alternate between heartbeat and ping
                        heartbeat = SSEEvent(
                            event_type=EventType.HEARTBEAT,
                            data={"timestamp": time.time()}
                        )
                        try:
                            yield heartbeat.format_sse()
                            client.update_ping()
                        except Exception as write_error:
                            client.write_errors += 1
                            logger.warning(f"Heartbeat write error for client {client_id}: {write_error}")
                    else:
                        # Send ping for zombie detection
                        ping_event = SSEEvent(
                            event_type=EventType.PING,
                            data={
                                "timestamp": time.time(),
                                "ping_id": str(uuid.uuid4()),
                                "expected_pong": True
                            }
                        )
                        try:
                            yield ping_event.format_sse()
                            client.update_ping()
                            client.missed_pings += 1
                        except Exception as write_error:
                            client.write_errors += 1
                            logger.warning(f"Ping write error for client {client_id}: {write_error}")
                    
                except Exception as e:
                    logger.error(f"Error streaming to client {client_id}: {e}")
                    client.mark_zombie("stream_error")
                    break
        except Exception as e:
            logger.error(f"Fatal error in stream for client {client_id}: {e}")
        finally:
            await self._disconnect_client(client_id)
    
    async def handle_pong(self, client_id: str, ping_id: str):
        """Handle pong response from client"""
        if client_id in self.clients:
            client = self.clients[client_id]
            client.update_pong()
            logger.debug(f"Received pong from client {client_id}, ping_id: {ping_id}")
    
    async def _send_recent_events(self, client: SSEClient):
        """Send recent events to a newly connected client"""
        recent_events = [
            event for event in self.event_history[-50:]  # Last 50 events
            if event.event_type in client.subscriptions
        ]
        
        for event in recent_events:
            try:
                await client.queue.put(event)
            except asyncio.QueueFull:
                break  # Skip if queue is full
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats and clean up stale connections"""
        while self.running:
            try:
                current_time = time.time()
                stale_clients = []
                
                for client_id, client in self.clients.items():
                    # Check for basic timeout
                    if current_time - client.last_ping > 120:  # 2 minutes timeout
                        stale_clients.append(client_id)
                        client.mark_zombie("timeout")
                
                # Remove stale clients
                for client_id in stale_clients:
                    await self._disconnect_client(client_id)
                
                await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(5)
    
    async def _zombie_detection_loop(self):
        """Advanced zombie detection loop"""
        while self.running:
            try:
                current_time = time.time()
                zombie_clients = []
                
                for client_id, client in self.clients.items():
                    if client.is_zombie:
                        continue
                    
                    # Check connection health
                    if not client.is_connection_healthy():
                        zombie_clients.append((client_id, "health_check_failed"))
                        continue
                    
                    # Check for missed pings
                    if client.missed_pings > 3:
                        zombie_clients.append((client_id, "missed_pings"))
                        continue
                    
                    # Check for pong timeout (if we ever sent a ping)
                    if (client.last_pong is None and 
                        client.ping_count > 0 and 
                        current_time - client.connected_at > 90):
                        zombie_clients.append((client_id, "no_pong_response"))
                        continue
                
                # Mark and potentially disconnect zombie clients
                for client_id, reason in zombie_clients:
                    if client_id in self.clients:
                        client = self.clients[client_id]
                        client.mark_zombie(reason)
                        
                        # Update zombie stats
                        self.zombie_stats["total_detected"] += 1
                        self.zombie_stats["detection_reasons"][reason] = (
                            self.zombie_stats["detection_reasons"].get(reason, 0) + 1
                        )
                        
                        # Disconnect zombie after grace period
                        zombie_duration = current_time - (client.zombie_detected_at or current_time)
                        if zombie_duration > 60:  # 1 minute grace period
                            await self._disconnect_client(client_id)
                
                self.zombie_stats["last_cleanup"] = current_time
                await asyncio.sleep(self.zombie_check_interval)
                
            except Exception as e:
                logger.error(f"Error in zombie detection loop: {e}")
                await asyncio.sleep(30)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get SSE manager statistics"""
        healthy_clients = [c for c in self.clients.values() if not c.is_zombie]
        zombie_clients = [c for c in self.clients.values() if c.is_zombie]
        
        return {
            "connected_clients": len(self.clients),
            "healthy_clients": len(healthy_clients),
            "zombie_clients": len(zombie_clients),
            "event_history_size": len(self.event_history),
            "zombie_detection": self.zombie_stats,
            "clients": [
                {
                    "client_id": client.client_id,
                    "subscriptions": list(client.subscriptions),
                    "queue_size": client.queue.qsize(),
                    "connected_duration": time.time() - client.connected_at,
                    "last_ping": client.last_ping,
                    "last_pong": client.last_pong,
                    "ping_count": client.ping_count,
                    "missed_pings": client.missed_pings,
                    "queue_full_count": client.queue_full_count,
                    "write_errors": client.write_errors,
                    "is_zombie": client.is_zombie,
                    "zombie_detected_at": client.zombie_detected_at,
                    "connection_healthy": client.is_connection_healthy()
                }
                for client in self.clients.values()
            ]
        }
    
    def get_zombie_stats(self) -> Dict[str, Any]:
        """Get detailed zombie detection statistics"""
        zombie_clients = [c for c in self.clients.values() if c.is_zombie]
        
        return {
            "current_zombies": len(zombie_clients),
            "total_detected": self.zombie_stats["total_detected"],
            "detection_reasons": self.zombie_stats["detection_reasons"],
            "last_cleanup": self.zombie_stats["last_cleanup"],
            "zombie_details": [
                {
                    "client_id": client.client_id,
                    "zombie_detected_at": client.zombie_detected_at,
                    "zombie_duration": time.time() - (client.zombie_detected_at or time.time()),
                    "missed_pings": client.missed_pings,
                    "queue_full_count": client.queue_full_count,
                    "write_errors": client.write_errors,
                    "connection_healthy": client.is_connection_healthy()
                }
                for client in zombie_clients
            ]
        }


# Global SSE manager instance
sse_manager = SSEManager() 