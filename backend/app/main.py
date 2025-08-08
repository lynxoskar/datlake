from fastapi import FastAPI, UploadFile, File, HTTPException, Response, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union
from contextlib import asynccontextmanager
import duckdb  # used indirectly via ducklake_conn setup
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
import pyarrow.ipc as ipc
from fastapi.responses import StreamingResponse
from enum import Enum

from .lineage import lineage_manager
from .queue_worker import queue_worker
from .routers.lineage import router as lineage_router
from .routers.admin import router as admin_router
from .routers.jobs_events import router as jobs_events_router
from .routers.tables_datasets import router as tables_datasets_router
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    log_event("INFO", "Initializing services...")
    try:
        # Initialize SSE manager first
        from .sse_manager import sse_manager
        await sse_manager.start()
        
        await lineage_manager.initialize()
        await queue_worker.initialize()
        await queue_worker.start()
        log_event("INFO", "Services initialized successfully")
    except Exception as e:
        log_event("ERROR", "Failed to initialize services", error=str(e))
        raise
    
    yield
    
    # Shutdown
    log_event("INFO", "Shutting down services...")
    try:
        await queue_worker.stop()
        await lineage_manager.close()
        
        # Stop SSE manager last
        from .sse_manager import sse_manager
        await sse_manager.stop()
        
        log_event("INFO", "Services shut down successfully")
    except Exception as e:
        log_event("ERROR", "Error during shutdown", error=str(e))


def custom_openapi():
    """Custom OpenAPI schema with Synthwave theme."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="🌊 DuckLake API",
        version="1.0.2",
        description="""
        # 🚀 DuckLake Data Platform
        
        A **high-performance data lake** with OpenLineage integration, built on DuckDB and PostgreSQL.
        
        ## 🎯 Key Features
        
        - **DuckLake Integration**: PostgreSQL-backed catalog with S3/MinIO data storage
        - **Real-time Processing**: Apache Arrow and Parquet for zero-copy operations
        - **OpenLineage**: Complete data lineage tracking
        - **Server-Sent Events**: Real-time updates and monitoring
        - **Multi-format Support**: JSON, Arrow, Parquet, CSV
        
        ## 🔧 API Organization
        
        The API is organized into logical groups:
        
        - **Admin**: System health, metrics, configuration
        - **Jobs & Events**: Job management, SSE streams, lineage tracking
        - **Tables & Datasets**: DuckLake tables, MinIO objects, query execution
        
        ## 🎨 Synthwave Theme
        
        This API documentation uses a **retro synthwave** theme matching the DuckLake frontend.
        """,
        routes=app.routes,
    )
    
    # Add custom theme info
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app = FastAPI(
    title="🌊 DuckLake API", 
    description="Data lake with OpenLineage integration", 
    version="1.0.2",
    lifespan=lifespan,
    docs_url=None,  # Disable default docs
    redoc_url=None  # Disable default redoc
)

app.openapi = custom_openapi

# Custom documentation endpoints with Synthwave theme
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom Swagger UI with Synthwave theme."""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - API Documentation",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
        swagger_ui_parameters={
            "deepLinking": True,
            "displayOperationId": True,
            "defaultModelsExpandDepth": 2,
            "defaultModelExpandDepth": 2,
            "syntaxHighlight.theme": "arta",
            "layout": "BaseLayout",
            "theme": "dark"
        },
        init_oauth=None,
        swagger_ui_init_oauth=None,
        custom_css="""
        /* Synthwave theme for Swagger UI */
        :root {
            --synthwave-deep: #0a0a0f;
            --synthwave-dark: #1a0b2e;
            --synthwave-darker: #16213e;
            --synthwave-purple: #240046;
            --synthwave-indigo: #3c096c;
            --synthwave-pink: #ff006e;
            --synthwave-cyan: #00f5ff;
            --synthwave-green: #39ff14;
            --synthwave-orange: #ff9500;
            --synthwave-yellow: #ffff00;
            --synthwave-violet: #7209b7;
            --synthwave-blue: #560bad;
            --synthwave-teal: #277da1;
        }
        
        /* Dark theme base */
        body {
            background: linear-gradient(135deg, var(--synthwave-dark) 0%, var(--synthwave-purple) 50%, var(--synthwave-darker) 100%);
            color: var(--synthwave-cyan);
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
        }
        
        /* Swagger UI container */
        .swagger-ui .topbar {
            background: var(--synthwave-dark);
            border-bottom: 2px solid var(--synthwave-cyan);
        }
        
        .swagger-ui .topbar .topbar-wrapper {
            color: var(--synthwave-cyan);
        }
        
        .swagger-ui .topbar .topbar-wrapper .link {
            color: var(--synthwave-pink);
        }
        
        /* Main content */
        .swagger-ui .swagger-container {
            background: rgba(26, 11, 46, 0.9);
            backdrop-filter: blur(10px);
        }
        
        .swagger-ui .info {
            background: rgba(36, 0, 70, 0.8);
            border: 1px solid var(--synthwave-cyan);
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 0 20px rgba(0, 245, 255, 0.3);
        }
        
        .swagger-ui .info .title {
            color: var(--synthwave-cyan);
            text-shadow: 0 0 10px var(--synthwave-cyan);
            font-family: 'Orbitron', sans-serif;
            font-weight: 900;
        }
        
        .swagger-ui .info .description {
            color: var(--synthwave-cyan);
        }
        
        .swagger-ui .info .description h1,
        .swagger-ui .info .description h2,
        .swagger-ui .info .description h3 {
            color: var(--synthwave-pink);
            text-shadow: 0 0 10px var(--synthwave-pink);
        }
        
        /* Operation sections */
        .swagger-ui .opblock-tag {
            background: rgba(36, 0, 70, 0.9);
            border: 1px solid var(--synthwave-cyan);
            border-radius: 8px;
            margin: 10px 0;
            box-shadow: 0 0 10px rgba(0, 245, 255, 0.2);
        }
        
        .swagger-ui .opblock-tag:hover {
            box-shadow: 0 0 20px rgba(0, 245, 255, 0.4);
        }
        
        .swagger-ui .opblock-tag .opblock-tag-body {
            color: var(--synthwave-cyan);
            text-shadow: 0 0 5px var(--synthwave-cyan);
        }
        
        /* Operation items */
        .swagger-ui .opblock {
            background: rgba(60, 9, 108, 0.8);
            border: 1px solid var(--synthwave-violet);
            border-radius: 6px;
            margin: 5px 0;
        }
        
        .swagger-ui .opblock:hover {
            border-color: var(--synthwave-pink);
            box-shadow: 0 0 15px rgba(255, 0, 110, 0.3);
        }
        
        .swagger-ui .opblock .opblock-summary {
            color: var(--synthwave-cyan);
        }
        
        .swagger-ui .opblock .opblock-summary-method {
            background: var(--synthwave-pink);
            color: var(--synthwave-dark);
            font-weight: bold;
            text-shadow: none;
        }
        
        .swagger-ui .opblock.get .opblock-summary-method {
            background: var(--synthwave-green);
        }
        
        .swagger-ui .opblock.post .opblock-summary-method {
            background: var(--synthwave-pink);
        }
        
        .swagger-ui .opblock.put .opblock-summary-method {
            background: var(--synthwave-orange);
        }
        
        .swagger-ui .opblock.delete .opblock-summary-method {
            background: var(--synthwave-yellow);
            color: var(--synthwave-dark);
        }
        
        /* Parameters and responses */
        .swagger-ui .parameters-container {
            background: rgba(26, 11, 46, 0.9);
            border-radius: 6px;
        }
        
        .swagger-ui .parameter__name {
            color: var(--synthwave-pink);
            font-weight: bold;
        }
        
        .swagger-ui .parameter__type {
            color: var(--synthwave-green);
        }
        
        .swagger-ui .response-container {
            background: rgba(26, 11, 46, 0.9);
            border-radius: 6px;
        }
        
        /* Code blocks */
        .swagger-ui .highlight-code {
            background: var(--synthwave-deep);
            color: var(--synthwave-green);
            border: 1px solid var(--synthwave-cyan);
            font-family: 'JetBrains Mono', monospace;
        }
        
        /* Buttons */
        .swagger-ui .btn {
            background: var(--synthwave-pink);
            color: var(--synthwave-dark);
            border: none;
            border-radius: 4px;
            font-family: 'Orbitron', sans-serif;
            font-weight: 700;
            text-transform: uppercase;
            transition: all 0.3s ease;
        }
        
        .swagger-ui .btn:hover {
            background: var(--synthwave-cyan);
            box-shadow: 0 0 15px rgba(0, 245, 255, 0.5);
        }
        
        .swagger-ui .btn.execute {
            background: var(--synthwave-green);
        }
        
        .swagger-ui .btn.execute:hover {
            background: var(--synthwave-pink);
        }
        
        /* Inputs */
        .swagger-ui input,
        .swagger-ui textarea,
        .swagger-ui select {
            background: rgba(36, 0, 70, 0.8);
            border: 1px solid var(--synthwave-cyan);
            color: var(--synthwave-cyan);
            border-radius: 4px;
        }
        
        .swagger-ui input:focus,
        .swagger-ui textarea:focus,
        .swagger-ui select:focus {
            border-color: var(--synthwave-pink);
            box-shadow: 0 0 10px rgba(255, 0, 110, 0.3);
        }
        
        /* Scrollbars */
        .swagger-ui ::-webkit-scrollbar {
            width: 8px;
        }
        
        .swagger-ui ::-webkit-scrollbar-track {
            background: rgba(36, 0, 70, 0.3);
        }
        
        .swagger-ui ::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, var(--synthwave-pink), var(--synthwave-cyan));
            border-radius: 4px;
        }
        
        .swagger-ui ::-webkit-scrollbar-thumb:hover {
            box-shadow: 0 0 10px rgba(0, 245, 255, 0.5);
        }
        
        /* Animations */
        @keyframes pulse-neon {
            0%, 100% { text-shadow: 0 0 5px currentColor; }
            50% { text-shadow: 0 0 20px currentColor; }
        }
        
        .swagger-ui .info .title {
            animation: pulse-neon 3s ease-in-out infinite;
        }
        
        /* Selection */
        .swagger-ui ::selection {
            background: rgba(0, 245, 255, 0.3);
            color: #ffffff;
        }
        """
    )

# Setup instrumentation
setup_memory_monitoring()
setup_performance_monitoring()

# Add performance monitoring middleware
app.add_middleware(PerformanceMiddleware, performance_monitor=performance_monitor)

# Include all routers with proper organization
app.include_router(admin_router)
app.include_router(jobs_events_router)
app.include_router(tables_datasets_router)
app.include_router(lineage_router)

# Add root endpoint
@app.get("/", tags=["Root"])
def read_root() -> Dict[str, str]:
    """Root endpoint with API information."""
    request_id = str(uuid.uuid4())
    log_event("INFO", "Root endpoint accessed", request_id=request_id, endpoint="/")
    return {
        "message": "🌊 Welcome to DuckLake API",
        "version": "1.0.2",
        "description": "High-performance data lake with OpenLineage integration",
        "docs": "/docs",
        "health": "/admin/health",
        "request_id": request_id
    }

# Log application startup
log_event("INFO", "FastAPI application starting", version="1.0.2")

# Initialize DuckLake connection (DuckDB + DuckLake + Postgres catalog)
from .ducklake_conn import con, setup_ducklake

# Get application settings
from .config import get_settings
settings = get_settings()


def setup_ducklake_connection_legacy():
    """Setup DuckLake with proper secrets management and S3 configuration."""
    try:
        # 1. Create PostgreSQL secret for catalog database
        postgres_secret_sql = f"""
        CREATE OR REPLACE SECRET postgres_catalog (
            TYPE POSTGRES,
            HOST '{settings.database.postgres_host}',
            PORT {settings.database.postgres_port},
            DATABASE '{settings.database.postgres_db}',
            USER '{settings.database.postgres_user}',
            PASSWORD '{settings.database.postgres_password.get_secret_value()}'
        );
        """
        con.execute(postgres_secret_sql)
        log_event("INFO", "PostgreSQL secret created for DuckLake catalog")
        
        # 2. Create S3 secret for MinIO data storage
        s3_secret_sql = f"""
        CREATE OR REPLACE SECRET s3_storage (
            TYPE S3,
            ENDPOINT '{'https' if settings.storage.minio_secure else 'http'}://{settings.storage.minio_endpoint}',
            ACCESS_KEY_ID '{settings.storage.minio_access_key}',
            SECRET_ACCESS_KEY '{settings.storage.minio_secret_key.get_secret_value()}',
            REGION '{settings.storage.minio_region}',
            USE_SSL {'true' if settings.storage.minio_secure else 'false'}
        );
        """
        con.execute(s3_secret_sql)
        log_event("INFO", "S3 secret created for DuckLake data storage")
        
        # 3. Create DuckLake secret combining both
        s3_data_path = f"s3://{settings.storage.default_bucket}/ducklake-data/"
        ducklake_secret_sql = f"""
        CREATE OR REPLACE SECRET ducklake_main (
            TYPE DUCKLAKE,
            METADATA_PATH '',
            DATA_PATH '{s3_data_path}',
            METADATA_PARAMETERS MAP {{
                'TYPE': 'postgres',
                'SECRET': 'postgres_catalog'
            }}
        );
        """
        con.execute(ducklake_secret_sql)
        log_event("INFO", "DuckLake secret created", data_path=s3_data_path)
        
        # 4. Attach DuckLake using the secret with additional parameters
        attach_params = []
        if settings.database.ducklake_metadata_schema != "main":
            attach_params.append(f"METADATA_SCHEMA '{settings.database.ducklake_metadata_schema}'")
        if settings.database.ducklake_metadata_catalog != "ducklake_metadata":
            attach_params.append(f"METADATA_CATALOG '{settings.database.ducklake_metadata_catalog}'")
        if settings.database.ducklake_encrypted:
            attach_params.append("ENCRYPTED true")
        if settings.database.ducklake_data_inlining_row_limit > 0:
            attach_params.append(f"DATA_INLINING_ROW_LIMIT {settings.database.ducklake_data_inlining_row_limit}")
        if settings.database.ducklake_snapshot_version:
            attach_params.append(f"SNAPSHOT_VERSION '{settings.database.ducklake_snapshot_version}'")
        if settings.database.ducklake_snapshot_time:
            attach_params.append(f"SNAPSHOT_TIME '{settings.database.ducklake_snapshot_time}'")
        if settings.database.ducklake_read_only:
            attach_params.append("READ_ONLY")
        
        attach_sql = "ATTACH 'ducklake:ducklake_main' AS ducklake"
        if attach_params:
            attach_sql += f" ({', '.join(attach_params)})"
        attach_sql += ";"
        
        con.execute(attach_sql)
        con.execute("USE ducklake;")
        
        log_event("INFO", "DuckLake attached successfully with secrets",
                  postgres_host=settings.database.postgres_host,
                  postgres_db=settings.database.postgres_db,
                  data_path=s3_data_path,
                  minio_endpoint=settings.storage.minio_endpoint,
                  parameters=attach_params)
        
        return True
        
    except Exception as e:
        log_event("ERROR", "Failed to setup DuckLake connection", error=str(e))
        return False

def setup_ducklake_fallback():
    """Setup fallback DuckLake connection for development."""
    try:
        # Use local DuckDB file as catalog for development
        fallback_catalog = "ducklake_dev.db"
        fallback_data_path = "ducklake_dev.files"
        
        # Create simple DuckLake secret for development
        fallback_secret_sql = f"""
        CREATE OR REPLACE SECRET ducklake_fallback (
            TYPE DUCKLAKE,
            METADATA_PATH '{fallback_catalog}',
            DATA_PATH '{fallback_data_path}'
        );
        """
        con.execute(fallback_secret_sql)
        
        # Attach using fallback
        con.execute("ATTACH 'ducklake:ducklake_fallback' AS ducklake;")
        con.execute("USE ducklake;")
        
        log_event("WARNING", "DuckLake fallback connection established",
                  catalog=fallback_catalog,
                  data_path=fallback_data_path)
        return True
        
    except Exception as e:
        log_event("ERROR", "Failed to setup DuckLake fallback", error=str(e))
        return False

def validate_ducklake_connection():
    """Validate DuckLake connection is working properly."""
    try:
        # Test basic DuckLake functionality
        con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'ducklake'").fetchone()
        
        # Test S3 connectivity if using S3 backend
        if not settings.is_development():
            try:
                # Try to list objects in the bucket to verify S3 connectivity
                con.execute(f"SELECT * FROM glob('s3://{settings.storage.default_bucket}/ducklake-data/*') LIMIT 1;")
                log_event("INFO", "S3 connectivity verified")
            except Exception as s3_error:
                log_event("WARNING", "S3 connectivity issue", error=str(s3_error))
        
        return True
    except Exception as e:
        log_event("ERROR", "DuckLake connection validation failed", error=str(e))
        return False

# Setup DuckLake connection with proper error handling
ducklake_connected = False

status = setup_ducklake()
if status.get("connected"):
    ducklake_connected = True
    log_event("INFO", "DuckLake connection established and validated")
else:
    if settings.is_development():
        log_event("WARNING", "Attempting fallback connection for development")
        if setup_ducklake_fallback() and validate_ducklake_connection():
            ducklake_connected = True
            log_event("INFO", "DuckLake fallback connection established and validated")
        else:
            log_event("ERROR", f"All DuckLake connection attempts failed in development: {status.get('error')}")
    else:
        log_event("CRITICAL", f"DuckLake connection failed in production: {status.get('error')}")
        raise RuntimeError("Failed to establish DuckLake connection in production environment")

# Store connection status for health checks
_ducklake_connection_status = {
    "connected": ducklake_connected,
    "timestamp": datetime.now().isoformat(),
    "environment": settings.environment.value
}

# Initialize MinIO client using centralized configuration
s3_client = boto3.client(
    's3',
    endpoint_url=f"{'https' if settings.storage.minio_secure else 'http'}://{settings.storage.minio_endpoint}",
    aws_access_key_id=settings.storage.minio_access_key,
    aws_secret_access_key=settings.storage.minio_secret_key.get_secret_value(),
    region_name=settings.storage.minio_region,
    config=boto3.session.Config(signature_version='s3v4')
)



@app.get("/")
def read_root() -> Dict[str, str]:
    """Root endpoint for API health check."""
    request_id = str(uuid.uuid4())
    log_event("INFO", "Root endpoint accessed", request_id=request_id, endpoint="/")
    return {"Hello": "World", "request_id": request_id}







# Server-Sent Events (SSE) endpoints



# DuckLake table operations
@app.post("/tables")
def create_table(table: Table) -> Dict[str, str]:
    """Create a new DuckLake table with specified schema."""
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

# DuckDB query operations
@app.put("/tables/{table_name}")
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

@app.delete("/tables/{table_name}")
def delete_table(table_name: str) -> Dict[str, str]:
    """Delete a DuckLake table."""
    try:
        con.execute(f"DROP TABLE ducklake.{table_name}")
        return {"message": f"DuckLake table '{table_name}' deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error deleting table: {e}")

@app.get("/tables/{table_name}")
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

@app.get("/tables")
def list_tables() -> Dict[str, Union[List[str], str]]:
    """List all DuckLake tables."""
    try:
        # Get all tables from DuckLake schema
        tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'ducklake'"
        tables_result = con.execute(tables_query).fetch_arrow_table()
        tables = [row["table_name"] for row in tables_result.to_pylist()]
        return {"tables": tables, "type": "ducklake"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing DuckLake tables: {e}")

@app.post("/tables/{table_name}/query")
def query_table(table_name: str, query: Query, request: Request):
    """Execute a query with content negotiation based on Accept header."""
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
    import io
    
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

# MinIO dataset operations
@app.post("/datasets/{bucket_name}")
def create_bucket(bucket_name: str) -> Dict[str, str]:
    """Create a new MinIO bucket."""
    try:
        s3_client.create_bucket(Bucket=bucket_name)
        return {"message": f"Bucket '{bucket_name}' created successfully."}
    except ClientError as e:
        raise HTTPException(status_code=400, detail=f"Error creating bucket: {e}")

@app.put("/datasets/{bucket_name}/{object_name}")
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

@app.get("/datasets/{bucket_name}/{object_name}")
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

@app.delete("/datasets/{bucket_name}/{object_name}")
def delete_object(bucket_name: str, object_name: str) -> Dict[str, str]:
    """Delete an object from a MinIO bucket."""
    try:
        s3_client.delete_object(Bucket=bucket_name, Key=object_name)
        return {"message": f"Object '{object_name}' from bucket '{bucket_name}' deleted successfully."}
    except ClientError as e:
        raise HTTPException(status_code=400, detail=f"Error deleting object: {e}")

@app.get("/datasets/{bucket_name}")
def list_objects(bucket_name: str) -> Dict[str, Union[str, List[str]]]:
    """List objects in a MinIO bucket."""
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        objects = [obj['Key'] for obj in response.get('Contents', [])]
        return {"bucket": bucket_name, "objects": objects}
    except ClientError as e:
        raise HTTPException(status_code=400, detail=f"Error listing objects in bucket: {e}")


# Job and Run operations with OpenLineage integration
@app.post("/jobs")
async def create_job(job: Job) -> Dict[str, str]:
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
async def start_job_run(job_name: str, job_run: JobRun) -> Dict[str, str]:
    """Start a new job run with OpenLineage tracking"""
    run_id = uuid.uuid4()
    request_id = str(uuid.uuid4())
    
    log_event("INFO", "Starting job run", 
              request_id=request_id, job_name=job_name, run_id=str(run_id))
    
    try:
        # Broadcast job start via SSE
        from .sse_manager import sse_manager
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
        from .sse_manager import sse_manager
        await sse_manager.broadcast_job_status(
            job_name=job_name,
            run_id=str(run_id),
            status="failed",
            progress=0
        )
        
        log_event("ERROR", "Failed to start job run", 
                  request_id=request_id, job_name=job_name, error=str(e))
        raise HTTPException(status_code=400, detail=f"Error starting job run: {e}")


@app.put("/jobs/{job_name}/runs/{run_id}/complete")
async def complete_job_run(job_name: str, run_id: UUID, completion: JobRunComplete) -> Dict[str, str]:
    """Complete a job run with OpenLineage tracking"""
    request_id = str(uuid.uuid4())
    
    log_event("INFO", "Completing job run", 
              request_id=request_id, job_name=job_name, run_id=str(run_id))
    
    try:
        # Broadcast job completion progress via SSE
        from .sse_manager import sse_manager
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
        from .sse_manager import sse_manager
        await sse_manager.broadcast_job_status(
            job_name=job_name,
            run_id=str(run_id),
            status="failed",
            progress=None
        )
        
        log_event("ERROR", "Failed to complete job run", 
                  request_id=request_id, job_name=job_name, run_id=str(run_id), error=str(e))
        raise HTTPException(status_code=400, detail=f"Error completing job run: {e}")


@app.get("/jobs")
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


@app.get("/jobs/{job_name}")
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


@app.get("/jobs/{job_name}/runs/{run_id}")
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
