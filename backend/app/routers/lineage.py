"""
OpenLineage API endpoints for DuckLake
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ..lineage import LineageEvent, lineage_manager
from ..queue_worker import queue_worker

router = APIRouter(prefix="/api/v1/lineage", tags=["lineage"])


class LineageEventRequest(BaseModel):
    """Request model for lineage events"""
    eventType: str
    run: Dict[str, Any]
    job: Dict[str, Any] 
    inputs: List[Dict[str, Any]] = []
    outputs: List[Dict[str, Any]] = []


class JobRunResponse(BaseModel):
    """Response model for job runs"""
    run_id: str
    state: str
    started_at: datetime
    ended_at: Optional[datetime]
    metadata: Optional[Dict[str, Any]]


class LineageResponse(BaseModel):
    """Response model for lineage data"""
    run_id: str
    job_name: str
    state: str
    started_at: datetime
    ended_at: Optional[datetime]
    inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]


@router.post("/events", response_model=Dict[str, str])
async def ingest_lineage_event(
    event_request: LineageEventRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """
    Ingest an OpenLineage event
    
    Accepts OpenLineage events and queues them for processing.
    Events are validated and then enqueued for asynchronous processing.
    """
    try:
        # Create lineage event from request
        event = LineageEvent(
            eventType=event_request.eventType,
            run=event_request.run,
            job=event_request.job,
            inputs=event_request.inputs,
            outputs=event_request.outputs
        )
        
        # Enqueue event for processing
        success = await lineage_manager.enqueue_event(event)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to enqueue lineage event"
            )
        
        return {
            "status": "accepted",
            "run_id": event.run["runId"],
            "event_type": event.eventType
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid lineage event: {str(e)}"
        )


@router.get("/jobs/{job_name}/runs", response_model=List[JobRunResponse])
async def get_job_runs(job_name: str) -> List[JobRunResponse]:
    """
    Get all runs for a specific job
    
    Returns a list of all job runs with their current state and timing information.
    """
    try:
        runs = await lineage_manager.get_job_runs(job_name)
        return [JobRunResponse(**run) for run in runs]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve job runs: {str(e)}"
        )


@router.get("/runs/{run_id}", response_model=LineageResponse)
async def get_run_lineage(run_id: UUID) -> LineageResponse:
    """
    Get complete lineage information for a specific run
    
    Returns the full lineage graph including inputs, outputs, and metadata.
    """
    try:
        lineage = await lineage_manager.get_run_lineage(run_id)
        
        if not lineage:
            raise HTTPException(
                status_code=404,
                detail=f"Run {run_id} not found"
            )
        
        return LineageResponse(**lineage)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve run lineage: {str(e)}"
        )


@router.get("/jobs", response_model=List[Dict[str, Any]])
async def list_jobs() -> List[Dict[str, Any]]:
    """
    List all jobs with basic metadata
    
    Returns a list of all registered jobs in the lineage system.
    """
    try:
        async with lineage_manager.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT namespace, name, created_at, updated_at, metadata,
                       COUNT(r.id) as total_runs
                FROM openlineage.jobs j
                LEFT JOIN openlineage.runs r ON j.id = r.job_id
                GROUP BY j.id, j.namespace, j.name, j.created_at, j.updated_at, j.metadata
                ORDER BY j.updated_at DESC
                """
            )
            
            return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list jobs: {str(e)}"
        )


@router.get("/datasets", response_model=List[Dict[str, Any]])
async def list_datasets() -> List[Dict[str, Any]]:
    """
    List all datasets with lineage information
    
    Returns a list of all datasets that have been involved in lineage events.
    """
    try:
        async with lineage_manager.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT d.namespace, d.name, d.physical_name, d.source_uri, 
                       d.created_at, d.updated_at,
                       COUNT(DISTINCT lg.run_id) as involved_runs,
                       MAX(CASE WHEN lg.direction = 'INPUT' THEN lg.created_at END) as last_input,
                       MAX(CASE WHEN lg.direction = 'OUTPUT' THEN lg.created_at END) as last_output
                FROM openlineage.datasets d
                LEFT JOIN openlineage.lineage_graph lg ON d.id = lg.dataset_id
                GROUP BY d.id, d.namespace, d.name, d.physical_name, d.source_uri, 
                         d.created_at, d.updated_at
                ORDER BY d.updated_at DESC
                """
            )
            
            return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list datasets: {str(e)}"
        )


@router.get("/datasets/{namespace}/{name}/lineage")
async def get_dataset_lineage(namespace: str, name: str) -> Dict[str, Any]:
    """
    Get lineage information for a specific dataset
    
    Returns all jobs/runs that have used this dataset as input or output.
    """
    try:
        async with lineage_manager.db_pool.acquire() as conn:
            # Get dataset info
            dataset_row = await conn.fetchrow(
                """
                SELECT id, namespace, name, physical_name, source_uri
                FROM openlineage.datasets
                WHERE namespace = $1 AND name = $2
                """,
                namespace, name
            )
            
            if not dataset_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Dataset {namespace}/{name} not found"
                )
            
            # Get lineage relationships
            lineage_rows = await conn.fetch(
                """
                SELECT lg.direction, lg.created_at, r.run_id, r.state, 
                       r.started_at, r.ended_at, j.name as job_name
                FROM openlineage.lineage_graph lg
                JOIN openlineage.runs r ON lg.run_id = r.run_id
                JOIN openlineage.jobs j ON r.job_id = j.id
                WHERE lg.dataset_id = $1
                ORDER BY lg.created_at DESC
                """,
                dataset_row["id"]
            )
            
            inputs = []
            outputs = []
            
            for row in lineage_rows:
                relationship = {
                    "run_id": str(row["run_id"]),
                    "job_name": row["job_name"],
                    "state": row["state"],
                    "started_at": row["started_at"],
                    "ended_at": row["ended_at"],
                    "lineage_created_at": row["created_at"]
                }
                
                if row["direction"] == "INPUT":
                    inputs.append(relationship)
                else:
                    outputs.append(relationship)
            
            return {
                "dataset": dict(dataset_row),
                "consumed_by": inputs,  # Jobs that read this dataset
                "produced_by": outputs  # Jobs that write this dataset
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get dataset lineage: {str(e)}"
        )


@router.get("/stats", response_model=Dict[str, Any])
async def get_lineage_stats() -> Dict[str, Any]:
    """
    Get lineage system statistics
    
    Returns overall statistics about the lineage system including queue status.
    """
    try:
        # Get database stats
        async with lineage_manager.db_pool.acquire() as conn:
            stats_row = await conn.fetchrow(
                """
                SELECT 
                    (SELECT COUNT(*) FROM openlineage.jobs) as total_jobs,
                    (SELECT COUNT(*) FROM openlineage.runs) as total_runs,
                    (SELECT COUNT(*) FROM openlineage.datasets) as total_datasets,
                    (SELECT COUNT(*) FROM openlineage.run_events) as total_events,
                    (SELECT COUNT(*) FROM openlineage.runs WHERE state = 'RUNNING') as active_runs
                """
            )
        
        # Get queue stats
        queue_stats = await queue_worker.get_queue_stats()
        
        return {
            "database": dict(stats_row),
            "queues": queue_stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get lineage stats: {str(e)}"
        )