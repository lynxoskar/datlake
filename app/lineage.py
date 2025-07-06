"""
OpenLineage integration for DuckLake
Handles lineage event creation, queuing, and processing
"""

import asyncio
import orjson
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import asyncpg
from loguru import logger
from openlineage.client import OpenLineageClient
from openlineage.client.run import RunEvent, RunState
from openlineage.client.facet import (
    BaseFacet,
    DatasetFacet,
    JobFacet,
    RunFacet,
    DocumentationJobFacet,
    SchemaDatasetFacet,
    SourceCodeLocationJobFacet,
)
from openlineage.client.uuid import generate_new_uuid
from pydantic import BaseModel, Field

from .config import get_settings

settings = get_settings()


class LineageEvent(BaseModel):
    """OpenLineage event model for API validation"""
    eventType: str = Field(..., description="Event type: START, RUNNING, COMPLETE, FAIL, ABORT")
    eventTime: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run: Dict[str, Any] = Field(..., description="Run information")
    job: Dict[str, Any] = Field(..., description="Job information")
    inputs: List[Dict[str, Any]] = Field(default_factory=list, description="Input datasets")
    outputs: List[Dict[str, Any]] = Field(default_factory=list, description="Output datasets")
    producer: str = Field(default="ducklake-backend", description="Producer URI")
    schemaURL: str = Field(default="https://openlineage.io/spec/1-0-5/OpenLineage.json")


class LineageManager:
    """Manages OpenLineage event creation and processing"""
    
    def __init__(self) -> None:
        self.client = OpenLineageClient(
            url=settings.openlineage_url,
            api_key=settings.openlineage_api_key
        )
        self.producer_uri = "ducklake-backend"
        self.namespace = "ducklake"
        self.db_pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self) -> None:
        """Initialize database connection pool"""
        self.db_pool = await asyncpg.create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            min_size=2,
            max_size=10
        )
    
    async def close(self) -> None:
        """Close database connection pool"""
        if self.db_pool:
            await self.db_pool.close()
    
    async def create_job_start_event(
        self,
        job_name: str,
        run_id: UUID,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LineageEvent:
        """Create a START event for a job run"""
        event = LineageEvent(
            eventType="START",
            run={
                "runId": str(run_id),
                "facets": {}
            },
            job={
                "namespace": self.namespace,
                "name": job_name,
                "facets": {
                    "documentation": {
                        "description": f"DuckLake job: {job_name}",
                        "_producer": self.producer_uri,
                        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DocumentationJobFacet.json"
                    }
                }
            },
            producer=self.producer_uri
        )
        
        if metadata:
            event.run["facets"]["metadata"] = metadata
            
        return event
    
    async def create_job_complete_event(
        self,
        job_name: str,
        run_id: UUID,
        inputs: List[Dict[str, Any]] = None,
        outputs: List[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LineageEvent:
        """Create a COMPLETE event for a job run"""
        event = LineageEvent(
            eventType="COMPLETE",
            run={
                "runId": str(run_id),
                "facets": {}
            },
            job={
                "namespace": self.namespace,
                "name": job_name,
                "facets": {
                    "documentation": {
                        "description": f"DuckLake job: {job_name}",
                        "_producer": self.producer_uri,
                        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DocumentationJobFacet.json"
                    }
                }
            },
            inputs=inputs or [],
            outputs=outputs or [],
            producer=self.producer_uri
        )
        
        if metadata:
            event.run["facets"]["metadata"] = metadata
            
        return event
    
    async def create_dataset_facet(
        self,
        namespace: str,
        name: str,
        uri: str,
        schema_fields: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Create a dataset facet"""
        dataset = {
            "namespace": namespace,
            "name": name,
            "facets": {
                "dataSource": {
                    "name": uri,
                    "uri": uri,
                    "_producer": self.producer_uri,
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DatasourceDatasetFacet.json"
                }
            }
        }
        
        if schema_fields:
            dataset["facets"]["schema"] = {
                "fields": schema_fields,
                "_producer": self.producer_uri,
                "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/SchemaDatasetFacet.json"
            }
        
        return dataset
    
    async def enqueue_event(self, event: LineageEvent) -> bool:
        """Enqueue a lineage event for processing"""
        try:
            async with self.db_pool.acquire() as conn:
                # Convert event to JSON for queuing
                event_json = event.model_dump_json()
                
                # Enqueue using PGMQ
                await conn.execute(
                    "SELECT pgmq.send('lineage_events', $1)",
                    event_json
                )
                return True
        except Exception as e:
            logger.error("Failed to enqueue lineage event", error=str(e))
            return False
    
    async def process_event(self, event: LineageEvent) -> bool:
        """Process a lineage event and store in database"""
        try:
            async with self.db_pool.acquire() as conn:
                # Start transaction
                async with conn.transaction():
                    # Ensure job exists
                    job_id = await self._ensure_job_exists(
                        conn,
                        event.job["namespace"],
                        event.job["name"]
                    )
                    
                    # Ensure run exists
                    run_uuid = UUID(event.run["runId"])
                    await self._ensure_run_exists(
                        conn,
                        run_uuid,
                        job_id,
                        event.eventType
                    )
                    
                    # Store event
                    await conn.execute(
                        """
                        INSERT INTO openlineage.run_events 
                        (run_id, event_type, event_time, producer_uri, schema_url, event_data)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        run_uuid,
                        event.eventType,
                        event.eventTime,
                        event.producer,
                        event.schemaURL,
                        orjson.dumps(event.model_dump()).decode('utf-8')
                    )
                    
                    # Process datasets
                    for dataset in event.inputs:
                        await self._process_dataset(conn, run_uuid, dataset, "INPUT")
                    
                    for dataset in event.outputs:
                        await self._process_dataset(conn, run_uuid, dataset, "OUTPUT")
                    
                    # Update run state if complete
                    if event.eventType in ["COMPLETE", "FAIL", "ABORT"]:
                        await conn.execute(
                            """
                            UPDATE openlineage.runs 
                            SET state = $1, ended_at = $2
                            WHERE run_id = $3
                            """,
                            event.eventType,
                            event.eventTime,
                            run_uuid
                        )
                
                return True
        except Exception as e:
            logger.error("Failed to process lineage event", error=str(e))
            return False
    
    async def _ensure_job_exists(self, conn: asyncpg.Connection, namespace: str, name: str) -> int:
        """Ensure job exists in database and return job_id"""
        # Try to get existing job
        row = await conn.fetchrow(
            "SELECT id FROM openlineage.jobs WHERE namespace = $1 AND name = $2",
            namespace, name
        )
        
        if row:
            return row["id"]
        
        # Create new job
        row = await conn.fetchrow(
            """
            INSERT INTO openlineage.jobs (namespace, name, metadata)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            namespace, name, orjson.dumps({}).decode('utf-8')
        )
        
        return row["id"]
    
    async def _ensure_run_exists(self, conn: asyncpg.Connection, run_id: UUID, job_id: int, event_type: str) -> None:
        """Ensure run exists in database"""
        # Check if run exists
        row = await conn.fetchrow(
            "SELECT id FROM openlineage.runs WHERE run_id = $1",
            run_id
        )
        
        if not row:
            # Create new run
            await conn.execute(
                """
                INSERT INTO openlineage.runs (run_id, job_id, state, producer_uri)
                VALUES ($1, $2, $3, $4)
                """,
                run_id, job_id, event_type, self.producer_uri
            )
    
    async def _process_dataset(self, conn: asyncpg.Connection, run_id: UUID, dataset: Dict[str, Any], direction: str) -> None:
        """Process a dataset and create lineage relationships"""
        # Ensure dataset exists
        dataset_id = await self._ensure_dataset_exists(
            conn,
            dataset["namespace"],
            dataset["name"],
            dataset.get("facets", {}).get("dataSource", {}).get("uri", "")
        )
        
        # Create lineage relationship
        await conn.execute(
            """
            INSERT INTO openlineage.lineage_graph (run_id, dataset_id, direction, metadata)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT DO NOTHING
            """,
            run_id, dataset_id, direction, orjson.dumps(dataset.get("facets", {})).decode('utf-8')
        )
    
    async def _ensure_dataset_exists(self, conn: asyncpg.Connection, namespace: str, name: str, uri: str) -> int:
        """Ensure dataset exists in database and return dataset_id"""
        # Try to get existing dataset
        row = await conn.fetchrow(
            "SELECT id FROM openlineage.datasets WHERE namespace = $1 AND name = $2",
            namespace, name
        )
        
        if row:
            return row["id"]
        
        # Create new dataset
        row = await conn.fetchrow(
            """
            INSERT INTO openlineage.datasets (namespace, name, source_uri, metadata)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            namespace, name, uri, orjson.dumps({}).decode('utf-8')
        )
        
        return row["id"]
    
    async def get_job_runs(self, job_name: str) -> List[Dict[str, Any]]:
        """Get all runs for a job"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT r.run_id, r.state, r.started_at, r.ended_at, r.metadata
                FROM openlineage.runs r
                JOIN openlineage.jobs j ON r.job_id = j.id
                WHERE j.name = $1 AND j.namespace = $2
                ORDER BY r.started_at DESC
                """,
                job_name, self.namespace
            )
            
            return [dict(row) for row in rows]
    
    async def get_run_lineage(self, run_id: UUID) -> Dict[str, Any]:
        """Get complete lineage for a run"""
        async with self.db_pool.acquire() as conn:
            # Get run info
            run_row = await conn.fetchrow(
                """
                SELECT r.run_id, r.state, r.started_at, r.ended_at, j.name as job_name
                FROM openlineage.runs r
                JOIN openlineage.jobs j ON r.job_id = j.id
                WHERE r.run_id = $1
                """,
                run_id
            )
            
            if not run_row:
                return {}
            
            # Get inputs and outputs
            lineage_rows = await conn.fetch(
                """
                SELECT lg.direction, d.namespace, d.name, d.source_uri
                FROM openlineage.lineage_graph lg
                JOIN openlineage.datasets d ON lg.dataset_id = d.id
                WHERE lg.run_id = $1
                """,
                run_id
            )
            
            inputs = []
            outputs = []
            
            for row in lineage_rows:
                dataset_info = {
                    "namespace": row["namespace"],
                    "name": row["name"],
                    "uri": row["source_uri"]
                }
                
                if row["direction"] == "INPUT":
                    inputs.append(dataset_info)
                else:
                    outputs.append(dataset_info)
            
            return {
                "run_id": str(run_row["run_id"]),
                "job_name": run_row["job_name"],
                "state": run_row["state"],
                "started_at": run_row["started_at"],
                "ended_at": run_row["ended_at"],
                "inputs": inputs,
                "outputs": outputs
            }


# Global lineage manager instance
lineage_manager = LineageManager()