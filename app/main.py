from fastapi import FastAPI, UploadFile, File, HTTPException, Response
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import boto3
from botocore.exceptions import ClientError
import io
import os
import orjson
import uuid
from datetime import datetime
from uuid import UUID
from loguru import logger

from .lineage import lineage_manager
from .queue_worker import queue_worker
from .routers.lineage import router as lineage_router
from .instrumentation import memory_monitor, performance_monitor, setup_memory_monitoring, setup_performance_monitoring
from .instrumentation.performance import PerformanceMiddleware

# Configure loguru for structured logging
logger.configure(
    handlers=[
        {
            "sink": "sys.stdout",
            "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
            "serialize": True,  # JSON output
            "level": "INFO"
        }
    ]
)

def log_event(level: str, message: str, **kwargs: Any) -> None:
    """Log structured events using loguru with orjson serialization"""
    log_data = {
        "service": "ducklake-backend",
        "message": message,
        **kwargs
    }
    
    if level.upper() == "DEBUG":
        logger.debug(message, **log_data)
    elif level.upper() == "INFO":
        logger.info(message, **log_data)
    elif level.upper() == "WARNING":
        logger.warning(message, **log_data)
    elif level.upper() == "ERROR":
        logger.error(message, **log_data)
    else:
        logger.info(message, **log_data)

app = FastAPI(title="DuckLake API", description="Data lake with OpenLineage integration", version="1.0.2")

# Setup instrumentation
setup_memory_monitoring()
setup_performance_monitoring()

# Add performance monitoring middleware
app.add_middleware(PerformanceMiddleware, performance_monitor=performance_monitor)

# Include lineage router
app.include_router(lineage_router)

# Log application startup
log_event("INFO", "FastAPI application starting", version="1.0.2")


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    log_event("INFO", "Initializing services...")
    try:
        await lineage_manager.initialize()
        await queue_worker.initialize()
        await queue_worker.start()
        log_event("INFO", "Services initialized successfully")
    except Exception as e:
        log_event("ERROR", "Failed to initialize services", error=str(e))
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    log_event("INFO", "Shutting down services...")
    try:
        await queue_worker.stop()
        await lineage_manager.close()
        log_event("INFO", "Services shut down successfully")
    except Exception as e:
        log_event("ERROR", "Error during shutdown", error=str(e))

# Initialize DuckDB in-memory database
con = duckdb.connect(database=':memory:', read_only=False)

# Initialize MinIO client
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")

s3_client = boto3.client(
    's3',
    endpoint_url=f"http://{MINIO_ENDPOINT}",
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    config=boto3.session.Config(signature_version='s3v4')
)

# Models for DuckDB operations
class Table(BaseModel):
    name: str
    schema: Dict[str, str] # e.g., {"col1": "INTEGER", "col2": "VARCHAR"}

class TableData(BaseModel):
    rows: List[Dict[str, Any]]

class Query(BaseModel):
    query: str


# Job and Run models
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

@app.get("/")
def read_root() -> Dict[str, str]:
    """Root endpoint for API health check."""
    request_id = str(uuid.uuid4())
    log_event("INFO", "Root endpoint accessed", request_id=request_id, endpoint="/")
    return {"Hello": "World", "request_id": request_id}

@app.get("/health")
def health_check() -> Dict[str, Any]:
    """Comprehensive health check including database and memory status."""
    request_id = str(uuid.uuid4())
    try:
        # Test DuckDB connection
        con.execute("SELECT 1").fetchone()
        
        # Get memory info
        memory_info = memory_monitor.get_memory_info()
        
        # Get performance stats
        performance_stats = performance_monitor.get_performance_stats()
        
        health_data = {
            "status": "healthy",
            "database": "ok",
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
        raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")


@app.get("/metrics/memory")
def get_memory_metrics() -> Dict[str, Any]:
    """Get detailed memory usage metrics."""
    try:
        return memory_monitor.get_memory_info()
    except Exception as e:
        log_event("ERROR", "Failed to get memory metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting memory metrics: {e}")


@app.get("/metrics/performance")
def get_performance_metrics() -> Dict[str, Any]:
    """Get detailed performance metrics."""
    try:
        return performance_monitor.get_performance_stats()
    except Exception as e:
        log_event("ERROR", "Failed to get performance metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting performance metrics: {e}")


@app.post("/metrics/gc")
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

# DuckDB table operations
@app.post("/tables")
def create_table(table: Table) -> Dict[str, str]:
    """Create a new DuckDB table with specified schema."""
    request_id = str(uuid.uuid4())
    log_event("INFO", "Creating table", request_id=request_id, table_name=table.name, schema=table.schema)
    try:
        columns_sql = ", ".join([f"{col_name} {col_type}" for col_name, col_type in table.schema.items()])
        create_table_sql = f"CREATE TABLE {table.name} ({columns_sql})"
        con.execute(create_table_sql)
        log_event("INFO", "Table created successfully", request_id=request_id, table_name=table.name)
        return {"message": f"Table '{table.name}' created successfully.", "request_id": request_id}
    except Exception as e:
        log_event("ERROR", "Failed to create table", request_id=request_id, table_name=table.name, error=str(e))
        raise HTTPException(status_code=400, detail=f"Error creating table: {e}")

# DuckDB query operations
@app.put("/tables/{table_name}")
def append_to_table(table_name: str, data: TableData) -> Dict[str, str]:
    """Append data to DuckDB table using direct PyArrow transfer for optimal performance."""
    try:
        with performance_monitor.track_operation(f"duckdb_append_{table_name}") as tracker:
            # Convert list of dicts to PyArrow Table for zero-copy transfer
            arrow_table = pa.Table.from_pylist(data.rows)
            tracker.add_metric("rows", len(data.rows))
            tracker.add_metric("table_name", table_name)
            
            # Track memory allocation for Arrow table
            estimated_size = arrow_table.nbytes if hasattr(arrow_table, 'nbytes') else len(data.rows) * 100
            memory_monitor.track_allocation("arrow_table", estimated_size)
            
            # Use DuckDB's native Arrow support for zero-copy append
            with performance_monitor.db_monitor.track_query("INSERT", f"INSERT INTO {table_name}"):
                con.register("temp_data", arrow_table)
                con.execute(f"INSERT INTO {table_name} SELECT * FROM temp_data")
                con.unregister("temp_data")
        
        return {"message": f"Data appended to table '{table_name}' successfully."}
    except Exception as e:
        log_event("ERROR", "Failed to append data to table", table_name=table_name, error=str(e))
        raise HTTPException(status_code=400, detail=f"Error appending data: {e}")

@app.delete("/tables/{table_name}")
def delete_table(table_name: str):
    try:
        con.execute(f"DROP TABLE {table_name}")
        return {"message": f"Table '{table_name}' deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error deleting table: {e}")

@app.get("/tables/{table_name}")
def get_table(table_name: str):
    try:
        # Get table schema using DuckDB's information_schema
        schema_query = f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}'"
        schema_result = con.execute(schema_query).fetch_arrow_table()
        schema = {row["column_name"]: row["data_type"] for row in schema_result.to_pylist()}
        return {"name": table_name, "schema": schema}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found or error retrieving schema: {e}")

@app.post("/tables/{table_name}/query")
def query_table(table_name: str, query: Query):
    try:
        result_arrow_table = con.execute(query.query).fetch_arrow_table()
        return {"result": result_arrow_table.to_pylist()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error executing query: {e}")



# MinIO dataset operations
@app.post("/datasets/{bucket_name}")
def create_bucket(bucket_name: str):
    try:
        s3_client.create_bucket(Bucket=bucket_name)
        return {"message": f"Bucket '{bucket_name}' created successfully."}
    except ClientError as e:
        raise HTTPException(status_code=400, detail=f"Error creating bucket: {e}")

@app.put("/datasets/{bucket_name}/{object_name}")
def upload_object(bucket_name: str, object_name: str, file: UploadFile = File(...)):
    try:
        with performance_monitor.minio_monitor.track_operation("upload"):
            # Track file size
            file_size = file.size if hasattr(file, 'size') else 0
            memory_monitor.track_allocation("minio_upload", file_size or 1024)
            
            s3_client.upload_fileobj(file.file, bucket_name, object_name)
            
            log_event("INFO", "Object uploaded successfully", 
                     bucket=bucket_name, object=object_name, size_bytes=file_size)
        
        return {"message": f"Object '{object_name}' uploaded to bucket '{bucket_name}' successfully."}
    except ClientError as e:
        log_event("ERROR", "Failed to upload object", 
                 bucket=bucket_name, object=object_name, error=str(e))
        raise HTTPException(status_code=400, detail=f"Error uploading object: {e}")

@app.get("/datasets/{bucket_name}/{object_name}")
def download_object(bucket_name: str, object_name: str):
    try:
        with performance_monitor.minio_monitor.track_operation("download"):
            response = s3_client.get_object(Bucket=bucket_name, Key=object_name)
            content = response['Body'].read()
            
            # Track downloaded data size
            memory_monitor.track_allocation("minio_download", len(content))
            
            log_event("INFO", "Object downloaded successfully", 
                     bucket=bucket_name, object=object_name, size_bytes=len(content))
            
            return Response(content=content, media_type=response['ContentType'])
    except ClientError as e:
        log_event("ERROR", "Failed to download object", 
                 bucket=bucket_name, object=object_name, error=str(e))
        raise HTTPException(status_code=404, detail=f"Error downloading object: {e}")

@app.delete("/datasets/{bucket_name}/{object_name}")
def delete_object(bucket_name: str, object_name: str):
    try:
        s3_client.delete_object(Bucket=bucket_name, Key=object_name)
        return {"message": f"Object '{object_name}' from bucket '{bucket_name}' deleted successfully."}
    except ClientError as e:
        raise HTTPException(status_code=400, detail=f"Error deleting object: {e}")

@app.get("/datasets/{bucket_name}")
def list_objects(bucket_name: str):
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        objects = [obj['Key'] for obj in response.get('Contents', [])]
        return {"bucket": bucket_name, "objects": objects}
    except ClientError as e:
        raise HTTPException(status_code=400, detail=f"Error listing objects in bucket: {e}")


# Job and Run operations with OpenLineage integration
@app.post("/jobs")
async def create_job(job: Job):
    """Create a new job definition"""
    request_id = str(uuid.uuid4())
    log_event("INFO", "Creating job", request_id=request_id, job_name=job.name)
    try:
        # Job creation doesn't generate lineage events, just log it
        log_event("INFO", "Job created successfully", request_id=request_id, job_name=job.name)
        return {"message": f"Job '{job.name}' created successfully.", "request_id": request_id}
    except Exception as e:
        log_event("ERROR", "Failed to create job", request_id=request_id, job_name=job.name, error=str(e))
        raise HTTPException(status_code=400, detail=f"Error creating job: {e}")


@app.post("/jobs/{job_name}/runs")
async def start_job_run(job_name: str, job_run: JobRun):
    """Start a new job run with OpenLineage tracking"""
    run_id = uuid.uuid4()
    request_id = str(uuid.uuid4())
    
    log_event("INFO", "Starting job run", 
              request_id=request_id, job_name=job_name, run_id=str(run_id))
    
    try:
        # Create OpenLineage START event
        start_event = await lineage_manager.create_job_start_event(
            job_name=job_name,
            run_id=run_id,
            metadata=job_run.metadata
        )
        
        # Enqueue the lineage event
        await lineage_manager.enqueue_event(start_event)
        
        log_event("INFO", "Job run started successfully", 
                  request_id=request_id, job_name=job_name, run_id=str(run_id))
        
        return {
            "message": f"Job run started for '{job_name}'",
            "run_id": str(run_id),
            "request_id": request_id
        }
    except Exception as e:
        log_event("ERROR", "Failed to start job run", 
                  request_id=request_id, job_name=job_name, error=str(e))
        raise HTTPException(status_code=400, detail=f"Error starting job run: {e}")


@app.put("/jobs/{job_name}/runs/{run_id}/complete")
async def complete_job_run(job_name: str, run_id: UUID, completion: JobRunComplete):
    """Complete a job run with OpenLineage tracking"""
    request_id = str(uuid.uuid4())
    
    log_event("INFO", "Completing job run", 
              request_id=request_id, job_name=job_name, run_id=str(run_id))
    
    try:
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
        
        log_event("INFO", "Job run completed successfully", 
                  request_id=request_id, job_name=job_name, run_id=str(run_id), 
                  success=completion.success)
        
        return {
            "message": f"Job run {'completed' if completion.success else 'failed'} for '{job_name}'",
            "run_id": str(run_id),
            "request_id": request_id
        }
    except Exception as e:
        log_event("ERROR", "Failed to complete job run", 
                  request_id=request_id, job_name=job_name, run_id=str(run_id), error=str(e))
        raise HTTPException(status_code=400, detail=f"Error completing job run: {e}")


@app.get("/jobs")
async def list_jobs():
    """List all jobs"""
    request_id = str(uuid.uuid4())
    try:
        # This would typically come from database, for now return empty
        log_event("INFO", "Listing jobs", request_id=request_id)
        return {"jobs": [], "request_id": request_id}
    except Exception as e:
        log_event("ERROR", "Failed to list jobs", request_id=request_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error listing jobs: {e}")


@app.get("/jobs/{job_name}")
async def get_job(job_name: str):
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


@app.get("/jobs/{job_name}/runs/{run_id}")
async def get_job_run(job_name: str, run_id: UUID):
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
