"""
Background worker for processing OpenLineage events from PGMQ
"""

import asyncio
import time
import orjson
from typing import Any, Dict, Optional

import asyncpg
from loguru import logger
from .config import get_settings
from .lineage import LineageEvent, lineage_manager

settings = get_settings()


class QueueWorker:
    """Background worker for processing queued OpenLineage events"""
    
    def __init__(self) -> None:
        self.db_pool: Optional[asyncpg.Pool] = None
        self.running = False
        self.tasks = []
        self.sse_manager = None  # Will be set during initialization
    
    async def initialize(self) -> None:
        """Initialize database connection pool"""
        self.db_pool = await asyncpg.create_pool(
            host=settings.database.postgres_host,
            port=settings.database.postgres_port,
            database=settings.database.postgres_db,
            user=settings.database.postgres_user,
            password=settings.database.postgres_password.get_secret_value(),
            min_size=max(1, settings.database.postgres_min_connections // 2),  # Use fewer connections for worker
            max_size=max(5, settings.database.postgres_max_connections // 2),
            command_timeout=settings.database.postgres_command_timeout,
            server_settings={'application_name': 'ducklake-worker'}
        )
        
        # Initialize lineage manager
        await lineage_manager.initialize()
        
        # Initialize SSE manager reference (will be set by main.py)
        try:
            from .sse_manager import sse_manager
            self.sse_manager = sse_manager
        except ImportError:
            logger.warning("SSE manager not available")
    
    async def start(self) -> None:
        """Start the background worker"""
        if self.running:
            return
        
        self.running = True
        logger.info("Starting queue worker...")
        
        # Start processing tasks
        self.tasks = [
            asyncio.create_task(self._process_lineage_events()),
            asyncio.create_task(self._process_notifications()),
            asyncio.create_task(self._broadcast_queue_metrics()),
        ]
        
        logger.info("Queue worker started")
    
    async def stop(self) -> None:
        """Stop the background worker"""
        if not self.running:
            return
        
        logger.info("Stopping queue worker...")
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Close database pool
        if self.db_pool:
            await self.db_pool.close()
        
        # Close lineage manager
        await lineage_manager.close()
        
        logger.info("Queue worker stopped")
    
    async def _process_lineage_events(self) -> None:
        """Process OpenLineage events from the queue"""
        while self.running:
            try:
                async with self.db_pool.acquire() as conn:
                    # Read messages from queue
                    rows = await conn.fetch(
                        "SELECT msg_id, message FROM pgmq.read('lineage_events', $1, $2)",
                        settings.queue.queue_batch_size,
                        settings.queue.queue_poll_interval
                    )
                    
                    for row in rows:
                        msg_id = row['msg_id']
                        message_data = row['message']
                        
                        try:
                            # Parse the lineage event
                            event_dict = orjson.loads(message_data) if isinstance(message_data, str) else message_data
                            event = LineageEvent(**event_dict)
                            
                            # Broadcast event start via SSE
                            if self.sse_manager:
                                await self.sse_manager.broadcast_lineage_event(
                                    event_type=event.eventType,
                                    run_id=event.run['runId'],
                                    job_name=event.job['name'],
                                    status="processing",
                                    metadata={
                                        "msg_id": msg_id,
                                        "namespace": event.job.get('namespace', 'default')
                                    }
                                )
                            
                            # Process the event with performance tracking
                            start_time = time.time()
                            success = await lineage_manager.process_event(event)
                            processing_duration = time.time() - start_time
                            
                            # Track lineage processing performance
                            from .instrumentation.performance import performance_monitor
                            performance_monitor.track_lineage_event(
                                event.eventType, 
                                processing_duration, 
                                success
                            )
                            
                            if success:
                                # Delete message from queue
                                await conn.execute(
                                    "SELECT pgmq.delete('lineage_events', $1)",
                                    msg_id
                                )
                                
                                # Broadcast successful processing via SSE
                                if self.sse_manager:
                                    await self.sse_manager.broadcast_lineage_event(
                                        event_type=event.eventType,
                                        run_id=event.run['runId'],
                                        job_name=event.job['name'],
                                        status="completed",
                                        metadata={
                                            "msg_id": msg_id,
                                            "processing_duration": processing_duration,
                                            "namespace": event.job.get('namespace', 'default')
                                        }
                                    )
                                
                                logger.debug(f"Processed lineage event: {event.eventType} for run {event.run['runId']}")
                            else:
                                # Move to dead letter queue
                                await self._move_to_dlq(conn, msg_id, message_data, "Processing failed")
                                
                                # Broadcast failure via SSE
                                if self.sse_manager:
                                    await self.sse_manager.broadcast_lineage_event(
                                        event_type=event.eventType,
                                        run_id=event.run['runId'],
                                        job_name=event.job['name'],
                                        status="failed",
                                        metadata={
                                            "msg_id": msg_id,
                                            "error": "Processing failed"
                                        }
                                    )
                                
                        except Exception as e:
                            logger.error(f"Error processing message {msg_id}: {e}")
                            # Move to dead letter queue
                            await self._move_to_dlq(conn, msg_id, message_data, str(e))
                            
                            # Broadcast error via SSE
                            if self.sse_manager:
                                await self.sse_manager.broadcast_error(
                                    error_type="lineage_processing_error",
                                    message=f"Failed to process lineage event: {str(e)}",
                                    details={
                                        "msg_id": msg_id,
                                        "error": str(e)
                                    }
                                )
                    
                    if not rows:
                        # No messages, wait before next poll
                        await asyncio.sleep(1)
                        
            except Exception as e:
                logger.error(f"Error in lineage event processing: {e}")
                if self.sse_manager:
                    await self.sse_manager.broadcast_error(
                        error_type="queue_processing_error",
                        message=f"Queue processing error: {str(e)}",
                        details={"component": "lineage_events"}
                    )
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _process_notifications(self) -> None:
        """Process real-time notifications"""
        while self.running:
            try:
                async with self.db_pool.acquire() as conn:
                    # Read notification messages
                    rows = await conn.fetch(
                        "SELECT msg_id, message FROM pgmq.read('lineage_notifications', $1, $2)",
                        settings.queue.queue_batch_size,
                        1  # Shorter poll interval for notifications
                    )
                    
                    for row in rows:
                        msg_id = row['msg_id']
                        message_data = row['message']
                        
                        try:
                            # Process notification and broadcast via SSE
                            await self._handle_notification(message_data)
                            
                            # Delete message from queue
                            await conn.execute(
                                "SELECT pgmq.delete('lineage_notifications', $1)",
                                msg_id
                            )
                            
                        except Exception as e:
                            logger.error(f"Error processing notification {msg_id}: {e}")
                            # Delete failed notifications (they're not critical)
                            await conn.execute(
                                "SELECT pgmq.delete('lineage_notifications', $1)",
                                msg_id
                            )
                    
                    if not rows:
                        # No messages, wait before next poll
                        await asyncio.sleep(2)
                        
            except Exception as e:
                logger.error(f"Error in notification processing: {e}")
                await asyncio.sleep(5)
    
    async def _broadcast_queue_metrics(self) -> None:
        """Periodically broadcast queue metrics via SSE"""
        while self.running:
            try:
                # Get queue statistics
                queue_stats = await self.get_queue_stats()
                
                # Broadcast queue metrics via SSE
                if self.sse_manager and queue_stats:
                    await self.sse_manager.broadcast_queue_status(queue_stats)
                
                # Wait before next broadcast
                await asyncio.sleep(30)  # Broadcast every 30 seconds
                
            except Exception as e:
                logger.error(f"Error broadcasting queue metrics: {e}")
                await asyncio.sleep(30)
    
    async def _move_to_dlq(self, conn: asyncpg.Connection, msg_id: int, message_data: Any, error: str) -> None:
        """Move a failed message to dead letter queue"""
        try:
            # Create DLQ message with error info
            dlq_message = {
                "original_message": message_data,
                "error": error,
                "timestamp": "now()",
                "msg_id": msg_id
            }
            
            # Send to dead letter queue
            await conn.execute(
                "SELECT pgmq.send('lineage_events_dlq', $1)",
                orjson.dumps(dlq_message).decode('utf-8')
            )
            
            # Delete from original queue
            await conn.execute(
                "SELECT pgmq.delete('lineage_events', $1)",
                msg_id
            )
            
            logger.warning(f"Moved message {msg_id} to DLQ: {error}")
            
        except Exception as e:
            logger.error(f"Failed to move message {msg_id} to DLQ: {e}")
    
    async def _handle_notification(self, message_data: Any) -> None:
        """Handle real-time notification and broadcast via SSE"""
        try:
            # Parse notification data
            if isinstance(message_data, str):
                notification = orjson.loads(message_data)
            else:
                notification = message_data
            
            # Broadcast notification via SSE
            if self.sse_manager:
                notification_type = notification.get('type', 'general')
                
                if notification_type == 'job_status':
                    await self.sse_manager.broadcast_job_status(
                        job_name=notification.get('job_name', 'unknown'),
                        run_id=notification.get('run_id', 'unknown'),
                        status=notification.get('status', 'unknown'),
                        progress=notification.get('progress')
                    )
                elif notification_type == 'system_metric':
                    await self.sse_manager.broadcast_system_metric(
                        metric_type=notification.get('metric_type', 'unknown'),
                        value=notification.get('value'),
                        metadata=notification.get('metadata', {})
                    )
                else:
                    # Generic notification
                    await self.sse_manager.broadcast_event(
                        event_type="notification",
                        data=notification
                    )
            
            logger.debug(f"Processed notification: {notification}")
            
        except Exception as e:
            logger.error(f"Error handling notification: {e}")
            if self.sse_manager:
                await self.sse_manager.broadcast_error(
                    error_type="notification_processing_error",
                    message=f"Failed to process notification: {str(e)}",
                    details={"notification_data": str(message_data)}
                )
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        try:
            async with self.db_pool.acquire() as conn:
                # Get message counts for all queues
                stats = {}
                
                queues = ['lineage_events', 'lineage_events_dlq', 'lineage_notifications']
                for queue_name in queues:
                    try:
                        row = await conn.fetchrow(
                            "SELECT queue_length FROM pgmq.metrics($1)",
                            queue_name
                        )
                        stats[queue_name] = row['queue_length'] if row else 0
                    except Exception:
                        stats[queue_name] = 0
                
                # Add total messages
                stats['total_messages'] = sum(stats.values())
                stats['timestamp'] = time.time()
                
                return stats
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {}


# Global worker instance
queue_worker = QueueWorker()