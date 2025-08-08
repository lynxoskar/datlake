from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional, Union
from uuid import UUID
import uuid

from ..sse_manager import sse_manager, EventType, SSEEvent
from ..lineage import lineage_manager
from ..main import log_event # Assuming log_event is accessible

router = APIRouter(
    prefix="/events",
    tags=["🚀 Jobs & Events"],
    responses={404: {"description": "Not found"}},
)

# Job and Run models (re-defined here for clarity, or import from a shared models file)
class Job(BaseModel):
    name: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class JobRun(BaseModel):
    job_name: str
    metadata: Optional[Dict[str, Any]] = None


class JobRunComplete(BaseModel):
    success: bool = True
    metadata: Optional[Dict[str, Any]] = None


@router.get("/stream", response_class=StreamingResponse, summary="📡 Stream Real-time Events")
async def stream_events(
    request: Request,
    events: Optional[str] = None  # Comma-separated list of event types
) -> StreamingResponse:
    """
    Stream real-time events via Server-Sent Events (SSE).
    
    **Parameters:**
    - **events**: Optional comma-separated list of event types to filter
    
    **Returns:**
    - Server-Sent Events stream with real-time updates
    """
    try:
        subscriptions = []
        if events:
            event_names = [e.strip() for e in events.split(',')]
            for event_name in event_names:
                try:
                    subscriptions.append(EventType(event_name))
                except ValueError:
                    log_event("WARNING", f"Invalid event type requested: {event_name}")
        
        client_id = await sse_manager.connect_client(request, subscriptions)
        
        log_event("INFO", f"SSE client connected: {client_id}", 
                  subscriptions=subscriptions or "default")
        
        return StreamingResponse(
            sse_manager.stream_events(client_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )
    except Exception as e:
        log_event("ERROR", "Failed to establish SSE connection", error=str(e))
        raise HTTPException(status_code=500, detail=f"SSE connection failed: {e}")


@router.get("/lineage")
async def stream_lineage_events(request: Request) -> StreamingResponse:
    """Stream only lineage events via SSE."""
    try:
        client_id = await sse_manager.connect_client(
            request, 
            [EventType.LINEAGE_EVENT, EventType.ERROR]
        )
        
        return StreamingResponse(
            sse_manager.stream_events(client_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    except Exception as e:
        log_event("ERROR", "Failed to establish lineage SSE connection", error=str(e))
        raise HTTPException(status_code=500, detail=f"Lineage SSE connection failed: {e}")


@router.get("/jobs")
async def stream_job_events(request: Request) -> StreamingResponse:
    """Stream only job status events via SSE."""
    try:
        client_id = await sse_manager.connect_client(
            request, 
            [EventType.JOB_STATUS, EventType.ERROR]
        )
        
        return StreamingResponse(
            sse_manager.stream_events(client_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    except Exception as e:
        log_event("ERROR", "Failed to establish job SSE connection", error=str(e))
        raise HTTPException(status_code=500, detail=f"Job SSE connection failed: {e}")


@router.get("/metrics")
async def stream_metric_events(request: Request) -> StreamingResponse:
    """Stream system metrics and queue status via SSE."""
    try:
        client_id = await sse_manager.connect_client(
            request, 
            [EventType.SYSTEM_METRIC, EventType.QUEUE_STATUS, EventType.ERROR]
        )
        
        return StreamingResponse(
            sse_manager.stream_events(client_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    except Exception as e:
        log_event("ERROR", "Failed to establish metrics SSE connection", error=str(e))
        raise HTTPException(status_code=500, detail=f"Metrics SSE connection failed: {e}")


@router.get("/stats")
def get_sse_stats() -> Dict[str, Any]:
    """Get SSE connection statistics."""
    try:
        return sse_manager.get_stats()
    except Exception as e:
        log_event("ERROR", "Failed to get SSE stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting SSE stats: {e}")


@router.post("/broadcast")
async def broadcast_custom_event(
    event_type: str,
    data: Dict[str, Any],
    target_clients: Optional[List[str]] = None
) -> Dict[str, str]:
    """Broadcast a custom event to SSE clients (for testing/admin purposes)."""
    try:
        # Validate event type
        try:
            event_type_enum = EventType(event_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid event type: {event_type}")
        
        # Create and broadcast event
        event = SSEEvent(
            event_type=event_type_enum,
            data=data
        )
        
        await sse_manager.broadcast_event(event, target_clients)
        
        log_event("INFO", f"Custom event broadcasted: {event_type}", 
                  event_id=event.event_id, target_clients=target_clients)
        
        return {"message": "Event broadcasted successfully", "event_id": event.event_id}
    except Exception as e:
        log_event("ERROR", "Failed to broadcast custom event", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error broadcasting event: {e}")


@router.delete("/clients/{client_id}")
async def disconnect_sse_client(client_id: str) -> Dict[str, str]:
    """Disconnect a specific SSE client."""
    try:
        await sse_manager.disconnect_client(client_id)
        return {"message": f"Client {client_id} disconnected successfully"}
    except Exception as e:
        log_event("ERROR", f"Failed to disconnect SSE client {client_id}", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error disconnecting client: {e}")


@router.get("/zombies")
def get_zombie_stats() -> Dict[str, Any]:
    """Get detailed zombie detection statistics."""
    try:
        return sse_manager.get_zombie_stats()
    except Exception as e:
        log_event("ERROR", "Failed to get zombie stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting zombie stats: {e}")


@router.post("/pong")
async def handle_pong(client_id: str, ping_id: str) -> Dict[str, str]:
    """Handle pong response from SSE client."""
    try:
        await sse_manager.handle_pong(client_id, ping_id)
        return {"message": "Pong received successfully"}
    except Exception as e:
        log_event("ERROR", f"Failed to handle pong from client {client_id}", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error handling pong: {e}")


@router.post("/zombies/cleanup")
async def cleanup_zombie_clients() -> Dict[str, Any]:
    """Force cleanup of zombie clients."""
    try:
        # Get current zombie clients
        zombie_stats = sse_manager.get_zombie_stats()
        zombie_count = zombie_stats["current_zombies"]
        
        # Force disconnect all zombie clients
        zombies_removed = 0
        for client_id, client in list(sse_manager.clients.items()):
            if client.is_zombie:
                await sse_manager.disconnect_client(client_id)
                zombies_removed += 1
        
        log_event("INFO", f"Zombie cleanup completed, removed {zombies_removed} zombie clients")
        return {
            "message": f"Cleanup completed, removed {zombies_removed} zombie clients",
            "zombies_before": zombie_count,
            "zombies_removed": zombies_removed
        }
    except Exception as e:
        log_event("ERROR", "Failed to cleanup zombie clients", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error cleaning up zombies: {e}")


# Job and Run operations with OpenLineage integration
@router.post("/jobs", summary="⚙️ Create Job Definition")
async def create_job(job: Job) -> Dict[str, str]:
    """
    Create a new job definition.
    
    **Parameters:**
    - **job**: Job definition with name, description, and metadata
    
    **Returns:**
    - Success message with job name
    - Request ID for tracking
    """
    request_id = str(uuid.uuid4())
    log_event("INFO", "Creating job", request_id=request_id, job_name=job.name)
    try:
        # Job creation doesn't generate lineage events, just log it
        log_event("INFO", "Job created successfully", request_id=request_id, job_name=job.name)
        return {"message": f"Job '{job.name}' created successfully.", "request_id": request_id}
    except Exception as e:
        log_event("ERROR", "Failed to create job", request_id=request_id, job_name=job.name, error=str(e))
        raise HTTPException(status_code=400, detail=f"Error creating job: {e}")


@router.post("/jobs/{job_name}/runs")
async def start_job_run(job_name: str, job_run: JobRun) -> Dict[str, str]:
    """Start a new job run with OpenLineage tracking"""
    run_id = uuid.uuid4()
    request_id = str(uuid.uuid4())
    
    log_event("INFO", "Starting job run", 
              request_id=request_id, job_name=job_name, run_id=str(run_id))
    
    try:
        # Broadcast job start via SSE
        await sse_manager.broadcast_job_status(
            job_name=job_name,
            run_id=str(run_id),
            status="starting",
            progress=0
        )
        
        # Create OpenLineage START event
        start_event = await lineage_manager.create_job_start_event(
            job_name=job_name,
            run_id=run_id,
            metadata=job_run.metadata
        )
        
        # Enqueue the lineage event
        await lineage_manager.enqueue_event(start_event)
        
        # Broadcast job started via SSE
        await sse_manager.broadcast_job_status(
            job_name=job_name,
            run_id=str(run_id),
            status="running",
            progress=10
        )
        
        log_event("INFO", "Job run started successfully", 
                  request_id=request_id, job_name=job_name, run_id=str(run_id))
        
        return {
            "message": f"Job run started for '{job_name}'",
            "run_id": str(run_id),
            "request_id": request_id
        }
    except Exception as e:
        # Broadcast job start failure via SSE
        await sse_manager.broadcast_job_status(
            job_name=job_name,
            run_id=str(run_id),
            status="failed",
            progress=0
        )
        
        log_event("ERROR", "Failed to start job run", 
                  request_id=request_id, job_name=job_name, error=str(e))
        raise HTTPException(status_code=400, detail=f"Error starting job run: {e}")


@router.put("/jobs/{job_name}/runs/{run_id}/complete")
async def complete_job_run(job_name: str, run_id: UUID, completion: JobRunComplete) -> Dict[str, str]:
    """Complete a job run with OpenLineage tracking"""
    request_id = str(uuid.uuid4())
    
    log_event("INFO", "Completing job run", 
              request_id=request_id, job_name=job_name, run_id=str(run_id))
    
    try:
        # Broadcast job completion progress via SSE
        await sse_manager.broadcast_job_status(
            job_name=job_name,
            run_id=str(run_id),
            status="completing",
            progress=90
        )
        
        # Create datasets for inputs/outputs based on current state
        inputs = []
        outputs = []
        
        # TODO: This could be enhanced to track actual datasets used during the run
        # For now, we'll track any tables or datasets mentioned in metadata
        if completion.metadata:
            if "inputs" in completion.metadata:
                for input_name in completion.metadata["inputs"]:
                    inputs.append(await lineage_manager.create_dataset_facet(
                        namespace="ducklake",
                        name=input_name,
                        uri=f"ducklake://tables/{input_name}"
                    ))
            
            if "outputs" in completion.metadata:
                for output_name in completion.metadata["outputs"]:
                    outputs.append(await lineage_manager.create_dataset_facet(
                        namespace="ducklake", 
                        name=output_name,
                        uri=f"ducklake://tables/{output_name}"
                    ))
        
        # Create OpenLineage COMPLETE event
        event_type = "COMPLETE" if completion.success else "FAIL"
        complete_event = await lineage_manager.create_job_complete_event(
            job_name=job_name,
            run_id=run_id,
            inputs=inputs,
            outputs=outputs,
            metadata=completion.metadata
        )
        complete_event.eventType = event_type
        
        # Enqueue the lineage event
        await lineage_manager.enqueue_event(complete_event)
        
        # Broadcast final job status via SSE
        final_status = "completed" if completion.success else "failed"
        await sse_manager.broadcast_job_status(
            job_name=job_name,
            run_id=str(run_id),
            status=final_status,
            progress=100 if completion.success else None
        )
        
        log_event("INFO", "Job run completed successfully", 
                  request_id=request_id, job_name=job_name, run_id=str(run_id), 
                  success=completion.success)
        
        return {
            "message": f"Job run {'completed' if completion.success else 'failed'} for '{job_name}'",
            "run_id": str(run_id),
            "request_id": request_id
        }
    except Exception as e:
        # Broadcast job completion failure via SSE
        await sse_manager.broadcast_job_status(
            job_name=job_name,
            run_id=str(run_id),
            status="failed",
            progress=None
        )
        
        log_event("ERROR", "Failed to complete job run", 
                  request_id=request_id, job_name=job_name, run_id=str(run_id), error=str(e))
        raise HTTPException(status_code=400, detail=f"Error completing job run: {e}")


@router.get("/jobs")
async def list_jobs() -> Dict[str, Union[List[Any], str]]:
    """List all jobs"""
    request_id = str(uuid.uuid4())
    try:
        # This would typically come from database, for now return empty
        log_event("INFO", "Listing jobs", request_id=request_id)
        return {"jobs": [], "request_id": request_id}
    except Exception as e:
        log_event("ERROR", "Failed to list jobs", request_id=request_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error listing jobs: {e}")


@router.get("/jobs/{job_name}")
async def get_job(job_name: str) -> Dict[str, Union[str, List[Dict[str, Any]]]]:
    """Get job metadata and status"""
    request_id = str(uuid.uuid4())
    try:
        # Get job runs from lineage manager
        runs = await lineage_manager.get_job_runs(job_name)
        
        log_event("INFO", "Retrieved job info", request_id=request_id, job_name=job_name)
        return {
            "name": job_name,
            "runs": runs,
            "request_id": request_id
        }
    except Exception as e:
        log_event("ERROR", "Failed to get job", request_id=request_id, job_name=job_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting job: {e}")


@router.get("/jobs/{job_name}/runs/{run_id}")
async def get_job_run(job_name: str, run_id: UUID) -> Dict[str, Any]:
    """Get details of a specific job run"""
    request_id = str(uuid.uuid4())
    try:
        # Get run lineage from lineage manager
        lineage = await lineage_manager.get_run_lineage(run_id)
        
        if not lineage:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        
        log_event("INFO", "Retrieved job run info", 
                  request_id=request_id, job_name=job_name, run_id=str(run_id))
        return {**lineage, "request_id": request_id}
    except HTTPException:
        raise
    except Exception as e:
        log_event("ERROR", "Failed to get job run", 
                  request_id=request_id, job_name=job_name, run_id=str(run_id), error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting job run: {e}")