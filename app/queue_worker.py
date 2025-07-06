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
    
    async def initialize(self) -> None:
        """Initialize database connection pool"""
        self.db_pool = await asyncpg.create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            min_size=1,
            max_size=5
        )
        
        # Initialize lineage manager
        await lineage_manager.initialize()
    
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
                        settings.queue_batch_size,
                        settings.queue_poll_interval
                    )
                    
                    for row in rows:
                        msg_id = row['msg_id']
                        message_data = row['message']
                        
                        try:
                            # Parse the lineage event
                            event_dict = orjson.loads(message_data) if isinstance(message_data, str) else message_data
                            event = LineageEvent(**event_dict)
                            
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
                                logger.debug(f"Processed lineage event: {event.eventType} for run {event.run['runId']}")
                            else:
                                # Move to dead letter queue
                                await self._move_to_dlq(conn, msg_id, message_data, "Processing failed")
                                
                        except Exception as e:
                            logger.error(f"Error processing message {msg_id}: {e}")
                            # Move to dead letter queue
                            await self._move_to_dlq(conn, msg_id, message_data, str(e))
                    
                    if not rows:
                        # No messages, wait before next poll
                        await asyncio.sleep(1)
                        
            except Exception as e:
                logger.error(f"Error in lineage event processing: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _process_notifications(self) -> None:
        """Process real-time notifications"""
        while self.running:
            try:
                async with self.db_pool.acquire() as conn:
                    # Read notification messages
                    rows = await conn.fetch(
                        "SELECT msg_id, message FROM pgmq.read('lineage_notifications', $1, $2)",
                        settings.queue_batch_size,
                        1  # Shorter poll interval for notifications
                    )
                    
                    for row in rows:
                        msg_id = row['msg_id']
                        message_data = row['message']
                        
                        try:
                            # Process notification (could trigger SSE events, webhooks, etc.)
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
        """Handle real-time notification"""
        # This could be extended to:
        # - Send SSE events to connected clients
        # - Trigger webhooks
        # - Update caches
        # - Send alerts
        
        logger.debug(f"Processed notification: {message_data}")
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        try:
            async with self.db_pool.acquire() as conn:
                # Get message counts for all queues
                stats = {}
                
                queues = ['lineage_events', 'lineage_events_dlq', 'lineage_notifications']
                for queue_name in queues:
                    row = await conn.fetchrow(
                        "SELECT queue_length FROM pgmq.metrics($1)",
                        queue_name
                    )
                    stats[queue_name] = row['queue_length'] if row else 0
                
                return stats
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {}


# Global worker instance
queue_worker = QueueWorker()