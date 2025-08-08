from fastapi import APIRouter, HTTPException, UploadFile, File, Response, Request
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
import pyarrow.ipc as ipc
from fastapi.responses import StreamingResponse
from enum import Enum

from ..main import con, s3_client, log_event # Assuming con and s3_client are accessible
from ..instrumentation import performance_monitor, memory_monitor
from ..config import get_settings

router = APIRouter(
    prefix="/data",
    tags=["📊 Tables & Datasets"],
    responses={404: {"description": "Not found"}},
)

settings = get_settings()

# Models for DuckDB operations
class Table(BaseModel):
    name: str
    schema: Dict[str, str] # e.g., {"col1": "INTEGER", "col2": "VARCHAR"}

class TableData(BaseModel):
    rows: List[Dict[str, Any]]

class Query(BaseModel):
    query: str
    stream: bool = False  # Keep streaming as an option

# Job and Run models (simplified for this router, full models in jobs_events.py)
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


# Helper functions for streaming (copied from main.py)
def serialize_arrow_table(table: pa.Table) -> bytes:
    """Serialize Arrow table to IPC format (zero-copy)."""
    sink = pa.BufferOutputStream()
    with ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()

def stream_arrow_table(table: pa.Table):
    """Stream Arrow table in batches."""
    def generate():
        sink = pa.BufferOutputStream()
        with ipc.new_stream(sink, table.schema) as writer:
            for batch in table.to_batches(max_chunksize=10000):
                sink = pa.BufferOutputStream()
                with ipc.new_stream(sink, table.schema) as batch_writer:
                    batch_writer.write_batch(batch)
                yield sink.getvalue().to_pybytes()
    
    return StreamingResponse(
        generate(), 
        media_type="application/vnd.apache.arrow.stream"
    )

def stream_parquet(table: pa.Table):
    """Stream table as Parquet (compressed)."""
    def generate():
        sink = pa.BufferOutputStream()
        pq.write_table(table, sink, compression='snappy')
        yield sink.getvalue().to_pybytes()
    
    return StreamingResponse(
        generate(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=query_result.parquet"}
    )

def stream_json_batches(table: pa.Table):
    """Stream JSON in batches to minimize memory."""
    def generate():
        yield b'{"result": ['
        first = True
        for batch in table.to_batches(max_chunksize=1000):
            batch_data = batch.to_pylist()
            for row in batch_data:
                if not first:
                    yield b','
                yield orjson.dumps(row)
                first = False
        yield b']}'
    
    return StreamingResponse(generate(), media_type="application/json")

def stream_csv(table: pa.Table):
    """Stream table as CSV."""
    import csv
    
    def generate():
        # Get column names
        columns = table.column_names
        
        # Create CSV header
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        yield output.getvalue().encode('utf-8')
        
        # Stream data in batches
        for batch in table.to_batches(max_chunksize=1000):
            output = io.StringIO()
            writer = csv.writer(output)
            batch_data = batch.to_pylist()
            for row_dict in batch_data:
                writer.writerow([row_dict.get(col, '') for col in columns])
            yield output.getvalue().encode('utf-8')
    
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=query_result.csv"}
    )


# DuckLake table operations
@router.post("/tables", summary="🆕 Create DuckLake Table")
def create_table(table: Table) -> Dict[str, str]:
    """
    Create a new DuckLake table with specified schema.
    
    **Parameters:**
    - **table**: Table definition with name and schema
    
    **Returns:**
    - Success message with table name
    - Request ID for tracking
    """
    request_id = str(uuid.uuid4())
    log_event("INFO", "Creating DuckLake table", request_id=request_id, table_name=table.name, schema=table.schema)
    try:
        columns_sql = ", ".join([f"{col_name} {col_type}" for col_name, col_type in table.schema.items()])
        create_table_sql = f"CREATE TABLE ducklake.{table.name} ({columns_sql})"
        con.execute(create_table_sql)
        log_event("INFO", "DuckLake table created successfully", request_id=request_id, table_name=table.name)
        return {"message": f"DuckLake table '{table.name}' created successfully.", "request_id": request_id}
    except Exception as e:
        log_event("ERROR", "Failed to create DuckLake table", request_id=request_id, table_name=table.name, error=str(e))
        raise HTTPException(status_code=400, detail=f"Error creating table: {e}")

@router.put("/tables/{table_name}")
def append_to_table(table_name: str, data: Union[TableData, UploadFile]):
    """Append data with multiple input formats (JSON, Arrow, Parquet)."""
    try:
        if isinstance(data, UploadFile):
            # Handle Arrow/Parquet uploads directly
            content = data.file.read()
            if data.filename.endswith('.arrow'):
                reader = ipc.open_stream(pa.BufferReader(content))
                arrow_table = reader.read_all()
            elif data.filename.endswith('.parquet'):
                arrow_table = pq.read_table(pa.BufferReader(content))
            else:
                raise HTTPException(400, "Unsupported file format")
        else:
            # Convert JSON to Arrow (existing logic)
            arrow_table = pa.Table.from_pylist(data.rows)
        
        # Zero-copy insert into DuckLake table
        with performance_monitor.db_monitor.track_query("INSERT", f"INSERT INTO ducklake.{table_name}"):
            con.register("temp_data", arrow_table)
            con.execute(f"INSERT INTO ducklake.{table_name} SELECT * FROM temp_data")
            con.unregister("temp_data")
        
        return {"message": f"Data appended successfully", "rows": len(arrow_table)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error appending data: {e}")

@router.delete("/tables/{table_name}")
def delete_table(table_name: str) -> Dict[str, str]:
    """Delete a DuckLake table."""
    try:
        con.execute(f"DROP TABLE ducklake.{table_name}")
        return {"message": f"DuckLake table '{table_name}' deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error deleting table: {e}")

@router.get("/tables/{table_name}")
def get_table(table_name: str) -> Dict[str, Union[str, Dict[str, str]]]:
    """Get DuckLake table schema information."""
    try:
        # Get table schema using DuckDB's information_schema for DuckLake tables
        schema_query = f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}' AND table_schema = 'ducklake'"
        schema_result = con.execute(schema_query).fetch_arrow_table()
        schema = {row["column_name"]: row["data_type"] for row in schema_result.to_pylist()}
        return {"name": table_name, "schema": schema, "type": "ducklake"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"DuckLake table '{table_name}' not found or error retrieving schema: {e}")

@router.get("/tables", summary="📋 List DuckLake Tables")
def list_tables() -> Dict[str, Union[List[str], str]]:
    """
    List all DuckLake tables.
    
    **Returns:**
    - List of table names
    - Table type (ducklake)
    """
    try:
        # Get all tables from DuckLake schema
        tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'ducklake'"
        tables_result = con.execute(tables_query).fetch_arrow_table()
        tables = [row["table_name"] for row in tables_result.to_pylist()]
        return {"tables": tables, "type": "ducklake"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing DuckLake tables: {e}")

@router.post("/tables/{table_name}/query", summary="🔍 Query DuckLake Table")
def query_table(table_name: str, query: Query, request: Request):
    """
    Execute a query with content negotiation based on Accept header.
    
    **Parameters:**
    - **table_name**: Name of the table to query
    - **query**: SQL query and streaming options
    - **Accept header**: Content type (json, arrow, parquet, csv)
    
    **Returns:**
    - Query results in requested format
    """
    try:
        # Get Arrow table directly from DuckDB (zero-copy)
        arrow_table = con.execute(query.query).fetch_arrow_table()
        
        # Get Accept header for content negotiation
        accept_header = request.headers.get("accept", "application/json")
        
        # Content negotiation based on Accept header
        if "application/vnd.apache.arrow" in accept_header:
            if query.stream:
                return stream_arrow_table(arrow_table)
            else:
                return Response(
                    content=serialize_arrow_table(arrow_table),
                    media_type="application/vnd.apache.arrow.stream"
                )
        elif "application/parquet" in accept_header or "application/octet-stream" in accept_header:
            return stream_parquet(arrow_table)
        elif "text/csv" in accept_header:
            return stream_csv(arrow_table)
        elif "application/json" in accept_header or "*/*" in accept_header:
            if query.stream:
                return stream_json_batches(arrow_table)
            else:
                # Only convert to Python for JSON (unavoidable copy)
                return {"result": arrow_table.to_pylist()}
        else:
            # Unsupported media type
            raise HTTPException(
                status_code=406, 
                detail=f"Unsupported media type: {accept_header}. Supported: application/json, application/vnd.apache.arrow.stream, application/parquet, text/csv"
            )
                
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error executing query: {e}")


# MinIO dataset operations
@router.post("/datasets/{bucket_name}")
def create_bucket(bucket_name: str) -> Dict[str, str]:
    """Create a new MinIO bucket."""
    try:
        s3_client.create_bucket(Bucket=bucket_name)
        return {"message": f"Bucket '{bucket_name}' created successfully."}
    except ClientError as e:
        raise HTTPException(status_code=400, detail=f"Error creating bucket: {e}")

@router.put("/datasets/{bucket_name}/{object_name}")
def upload_object(bucket_name: str, object_name: str, file: UploadFile = File(...)) -> Dict[str, str]:
    """Upload an object to a MinIO bucket."""
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

@router.get("/datasets/{bucket_name}/{object_name}")
def download_object(bucket_name: str, object_name: str) -> Response:
    """Download an object from a MinIO bucket."""
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

@router.delete("/datasets/{bucket_name}/{object_name}")
def delete_object(bucket_name: str, object_name: str) -> Dict[str, str]:
    """Delete an object from a MinIO bucket."""
    try:
        s3_client.delete_object(Bucket=bucket_name, Key=object_name)
        return {"message": f"Object '{object_name}' from bucket '{bucket_name}' deleted successfully."}
    except ClientError as e:
        raise HTTPException(status_code=400, detail=f"Error deleting object: {e}")

@router.get("/datasets/{bucket_name}")
def list_objects(bucket_name: str) -> Dict[str, Union[str, List[str]]]:
    """List objects in a MinIO bucket."""
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        objects = [obj['Key'] for obj in response.get('Contents', [])]
        return {"bucket": bucket_name, "objects": objects}
    except ClientError as e:
        raise HTTPException(status_code=400, detail=f"Error listing objects in bucket: {e}")


# Detached Mode Endpoints (from detached_model_plan.md)

class DetachedTable(BaseModel):
    name: str
    latest_snapshot_id: str

class DetachedSnapshot(BaseModel):
    table_name: str
    snapshot_id: str
    uri: str
    format: str
    created_at: datetime
    schema: Dict[str, Any]

class RegisterSnapshotRequest(BaseModel):
    table_name: str
    uri: str
    format: str
    schema: Optional[Dict[str, Any]] = None


@router.get("/v1/tables", response_model=List[DetachedTable])
async def list_detached_tables():
    """List all tables the authenticated user is permitted to see (detached mode)."""
    # TODO: Implement RBAC check here
    try:
        # For now, return all tables from DuckLake schema
        tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'ducklake'"
        tables_result = con.execute(tables_query).fetch_arrow_table()
        tables = []
        for row in tables_result.to_pylist():
            # Placeholder for latest_snapshot_id, needs actual implementation
            tables.append({"name": row["table_name"], "latest_snapshot_id": "placeholder-snapshot-id"})
        return tables
    except Exception as e:
        log_event("ERROR", "Failed to list detached tables", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error listing tables: {e}")

@router.get("/v1/tables/{table_name}/snapshots/latest", response_model=DetachedSnapshot)
async def get_latest_detached_snapshot(table_name: str):
    """Retrieve the metadata for the latest snapshot of a specific table (detached mode)."""
    # TODO: Implement RBAC check here (SELECT privileges)
    try:
        # Get table schema using DuckDB's information_schema for DuckLake tables
        schema_query = f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}' AND table_schema = 'ducklake'"
        schema_result = con.execute(schema_query).fetch_arrow_table()
        schema = {row["column_name"]: row["data_type"] for row in schema_result.to_pylist()}

        # Placeholder for URI, snapshot_id, created_at
        # In a real implementation, this would query your metadata store for the latest snapshot
        return {
            "table_name": table_name,
            "snapshot_id": f"snap-{uuid.uuid4()}",
            "uri": f"s3://{settings.storage.default_bucket}/ducklake-data/{table_name}/latest.parquet", # Example URI
            "format": "parquet",
            "created_at": datetime.now(),
            "schema": schema
        }
    except Exception as e:
        log_event("ERROR", "Failed to get latest detached snapshot", table_name=table_name, error=str(e))
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found or error retrieving snapshot: {e}")

@router.post("/v1/jobs/register-snapshot")
async def register_detached_snapshot(request: RegisterSnapshotRequest):
    """Register a new snapshot of data that has been manually uploaded to the object store (detached mode)."""
    # TODO: Implement RBAC check here (INSERT/UPDATE privileges)
    try:
        # This would trigger a job in the backend to process the registration
        # For now, we'll just log and return a dummy job ID
        job_id = str(uuid.uuid4())
        log_event("INFO", "Registering detached snapshot", 
                  table_name=request.table_name, uri=request.uri, format=request.format, 
                  schema=request.schema, job_id=job_id)
        
        # In a real implementation, you would enqueue a message to your queue worker here
        # queue_worker.enqueue_job("register_snapshot", {
        #     "table_name": request.table_name,
        #     "uri": request.uri,
        #     "format": request.format,
        #     "schema": request.schema
        # })

        return {"message": "Snapshot registration job initiated", "job_id": job_id}
    except Exception as e:
        log_event("ERROR", "Failed to register detached snapshot", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error registering snapshot: {e}")
