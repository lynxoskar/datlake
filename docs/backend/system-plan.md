# Backend System Plan

## 1. Overview

The backend service is the core of the DuckLake system. It will be a Python application built with FastAPI, providing a RESTful API for all data operations. It will interact with MinIO for object storage and DuckDB for analytical queries using the modern columnar data stack.

## 2. Environment Setup

### 2.1. Development Environment
- **Python Version:** 3.13+ (required for modern performance features)
- **Package Manager:** uv (NOT pip/poetry/conda)
- **Virtual Environment:** `uv venv --python 3.13`
- **Dependency Management:** `uv lock --upgrade && uv sync --all-extras`
- **Environment Variables:** .env file with python-decouple for configuration
- **Shell Integration:** .envrc file with `source .venv/bin/activate` for direnv

### 2.2. Setup Script
```bash
#!/bin/bash
# setup.sh - Automated setup for Ubuntu 25
uv venv --python 3.13
source .venv/bin/activate
uv sync --all-extras
echo "source .venv/bin/activate" > .envrc
```

## 3. Core Technologies

### 3.1. Web Framework & Server
- **Framework:** FastAPI with full OpenAPI documentation
- **Server:** Uvicorn with uvloop for high performance
- **Async Support:** Full async/await throughout the application
- **Response Models:** SQLModel for all API responses

### 3.2. Modern Data Stack
- **DataFrame Operations:** Polars 0.21+ (NOT Pandas - 10-100x performance gains)
- **SQL Analytics:** DuckDB 0.10+ with native S3 filesystem support
- **Data Interchange:** PyArrow 16+ for zero-copy operations
- **Streaming:** Polars streaming for datasets larger than memory

### 3.3. Database & Storage
- **Database:** DuckDB with S3 filesystem for MinIO integration
- **Object Storage:** MinIO via boto3
- **Caching:** Redis for performance optimization
- **Migrations:** Alembic for schema management

### 3.4. Development & Operations
- **Configuration:** python-decouple for .env-based settings
- **Logging:** Rich for beautiful console output and detailed logging
- **CLI:** Typer for admin tasks with Rich integration
- **Linting:** Ruff for code formatting and linting (zero warnings policy)
- **Type Checking:** mypy for static type analysis
- **Testing:** Real end-to-end integration tests (no mocks, real data)

## 4. API Endpoints

The following is a comprehensive list of API endpoints. All endpoints are fully documented with OpenAPI and use SQLModel response models.

### 4.1. DuckLake Table Operations

- `GET /tables`: List all tables with metadata.
- `GET /tables/events`: Server-side events stream for table changes (creation, deletion, schema updates).
- `POST /tables`: Create a new table with schema validation.
- `PUT /tables/{table_name}`: Append data to a table (supports `application/x-parquet` and `application/vnd.apache.arrow.stream` content types).
- `DELETE /tables/{table_name}`: Delete a table with cascade options.
- `GET /tables/{table_name}`: Get table schema and metadata.
- `GET /tables/{table_name}/data`: Export table data with zero-copy streaming (supports `application/x-parquet` and `application/vnd.apache.arrow.stream` via Accept header).
- `GET /tables/{table_name}/events`: Server-side events stream for table data appends and modifications.
- `POST /tables/{table_name}/query`: Execute SQL queries with result format selection via Accept header.

### 4.2. MinIO Dataset Operations

- `GET /datasets`: List all datasets (buckets) with metadata.
- `GET /datasets/events`: Server-side events stream for dataset changes (bucket creation, deletion).
- `POST /datasets/{bucket_name}`: Create a new bucket with validation.
- `PUT /datasets/{bucket_name}/{object_name}`: Upload a file with metadata handling.
- `GET /datasets/{bucket_name}/{object_name}`: Download a file with streaming support.
- `DELETE /datasets/{bucket_name}/{object_name}`: Delete a file.
- `GET /datasets/{bucket_name}`: List objects in a bucket with pagination.
- `GET /datasets/{bucket_name}/events`: Server-side events stream for object changes (upload, deletion) within a bucket.

### 4.3. Unit of Work Operations

- `GET /jobs`: List all unit of work jobs with status.
- `POST /jobs`: Create a new unit of work job definition.
- `GET /jobs/{job_name}`: Get job metadata and current status.
- `POST /jobs/{job_name}/runs`: Start a new run of a job (unit of work execution).
- `GET /jobs/{job_name}/runs/{run_id}`: Get details of a specific job run.
- `GET /jobs/{job_name}/runs/{run_id}/datasets`: Get all datasets (inputs/outputs) associated with this run.
- `GET /jobs/{job_name}/runs/{run_id}/tables`: Get all tables (inputs/outputs) associated with this run.
- `PUT /jobs/{job_name}/runs/{run_id}/complete`: Mark a job run as complete.
- `GET /jobs/events`: Server-side events stream for job and run changes.
- `GET /jobs/{job_name}/runs/{run_id}/events`: Server-side events stream for specific run progress.

### 4.4. OpenLineage Integration

- Full OpenLineage instrumentation with the Python client
- Lineage events emitted for all major data operations, grouped by job runs
- Each unit of work generates START, RUNNING, and COMPLETE OpenLineage events
- Input/output datasets and tables tracked within job run context
- OpenLineage endpoint configured via environment variables

## 5. Implementation Details

### 5.1. Modern Data Stack Integration

#### Zero-Copy Data Pipeline
```python
class DataPipeline:
    """Unified interface for zero-copy data operations across the stack."""
    
    def __init__(self, duckdb_path: str = ":memory:"):
        self.duckdb_conn = duckdb.connect(duckdb_path)
        # Optimize for performance
        self.duckdb_conn.execute("SET threads TO 8")
        self.duckdb_conn.execute("SET memory_limit = '8GB'")
        
    def polars_to_duckdb(self, df: pl.DataFrame, table_name: str) -> None:
        """Zero-copy transfer from Polars to DuckDB via Arrow."""
        arrow_table = df.to_arrow()
        self.duckdb_conn.register(table_name, arrow_table)
        
    def duckdb_to_polars(self, query: str) -> pl.DataFrame:
        """Execute SQL and return as Polars DataFrame with zero-copy."""
        arrow_result = self.duckdb_conn.execute(query).arrow()
        return pl.from_arrow(arrow_result)
```

#### Efficient Arrow Streaming
```python
@app.get("/tables/{table_name}/data")
async def export_table_data(
    table_name: str,
    accept: str = Header(default="application/vnd.apache.arrow.stream")
):
    """Stream table data with zero-copy Arrow IPC format."""
    def generate_arrow_stream():
        # Query DuckDB and get Arrow result directly
        result = duckdb_conn.execute(f"SELECT * FROM {table_name}").arrow()
        
        # Stream Arrow IPC format (schema included automatically)
        sink = pa.BufferOutputStream()
        with pa.ipc.new_stream(sink, result.schema) as writer:
            for batch in result.to_batches():
                writer.write_batch(batch)
        return sink.getvalue().to_pybytes()
    
    return StreamingResponse(
        generate_arrow_stream(),
        media_type="application/vnd.apache.arrow.stream"
    )
```

### 5.2. Performance Optimization

- **Lazy Evaluation:** Use Polars scan operations for query optimization
- **Memory Management:** Chunked processing for large datasets with memory monitoring
- **String Caching:** Enable Polars string cache for categorical data performance
- **Streaming Operations:** Process datasets larger than memory using Polars streaming
- **Zero-Copy Transfers:** Direct Arrow data movement between Polars ↔ DuckDB ↔ PyArrow

### 5.3. FastAPI Best Practices

- **Async Everything:** All network activity (httpx), file access (aiofiles), database operations
- **Response Models:** SQLModel for all API responses with full type safety
- **Error Handling:** Comprehensive error handling with proper HTTP status codes
- **Rate Limiting:** Semaphores and exponential backoff for external API calls
- **Validation:** Pydantic models for request/response validation

### 5.4. Configuration Management

```python
from decouple import Config as DecoupleConfig, RepositoryEnv

decouple_config = DecoupleConfig(RepositoryEnv(".env"))
DATABASE_URL = decouple_config("DATABASE_URL")
MINIO_ENDPOINT = decouple_config("MINIO_ENDPOINT")
OPENLINEAGE_ENDPOINT = decouple_config("OPENLINEAGE_ENDPOINT")
```

### 5.5. CLI and Console Interface

```python
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()

@app.command()
def list_tables():
    """List all tables with rich formatting."""
    table = Table(title="DuckLake Tables")
    table.add_column("Name", style="cyan")
    table.add_column("Rows", style="magenta")
    table.add_column("Size", style="green")
    
    # Add table data with rich formatting
    console.print(table)
```

### 5.6. Testing Strategy

- **Real Integration Tests:** No mocks, use real DuckDB, MinIO, and data
- **Rich Logging:** Detailed test output with Rich console formatting
- **End-to-End Scenarios:** Test complete workflows including OpenLineage events
- **Performance Testing:** Validate zero-copy operations and streaming performance

### 5.7. Server-Side Events Implementation

```python
@app.get("/tables/events")
async def table_events():
    """Stream table change events using FastAPI StreamingResponse."""
    
    async def event_generator():
        while True:
            # Get latest table changes
            event = await get_table_change_event()
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

## 6. Development Workflow

### 6.1. Quality Standards
- **Zero Ruff Warnings:** All code must pass ruff linting with zero warnings
- **Zero mypy Errors:** Full type checking compliance
- **Real Data Testing:** Integration tests with actual data and API calls
- **Rich Console Output:** All CLI tools use Rich for beautiful, informative output

### 6.2. Project Structure
```
backend/
├── pyproject.toml          # uv-based dependency management
├── .env                    # Configuration via python-decouple
├── .envrc                  # direnv integration
├── setup.sh               # Automated setup script
├── ducklake/
│   ├── api/               # FastAPI routes and models
│   ├── core/              # Core business logic
│   ├── data/              # Data pipeline components
│   ├── models/            # SQLModel definitions
│   └── cli/               # Typer CLI commands
└── tests/                 # Real integration tests
```

### 6.3. Dependencies (pyproject.toml)
```toml
[project]
dependencies = [
    "fastapi>=0.120.0",
    "uvicorn[standard]>=0.35.0",
    "polars[all]>=0.21.0",      # Modern DataFrame operations
    "duckdb>=0.10.0",           # SQL analytics engine
    "pyarrow>=16.0.0",          # Zero-copy data interchange
    "sqlmodel>=0.0.15",         # Type-safe database models
    "python-decouple>=3.8",     # Environment configuration
    "redis[hiredis]>=5.3.0",    # Caching layer
    "rich>=13.7.0",             # Beautiful console output
    "typer>=0.15.0",            # CLI framework
    "httpx[http2]>=0.25.0",     # Async HTTP client
    "aiofiles>=23.2.0",         # Async file operations
    "openlineage-python>=1.0.0", # Data lineage tracking
    "boto3>=1.34.0",            # MinIO/S3 client
    "ruff>=0.9.0",              # Linting and formatting
    "mypy>=1.7.0",              # Type checking
]
```

## 7. Deployment & Production

### 7.1. Production Configuration
- **Uvicorn with uvloop** for high-performance serving
- **NGINX reverse proxy** for load balancing and SSL termination
- **Redis clustering** for scalable caching
- **Monitoring** with proper logging and metrics
- **Fail-fast approach** for core dependencies (DuckDB, MinIO, Redis)

### 7.2. Performance Targets
- **Sub-second response times** for metadata operations
- **High-throughput streaming** for large dataset exports
- **Memory efficiency** through zero-copy operations
- **Horizontal scaling** via stateless API design

This updated system plan incorporates the modern data stack best practices and FastAPI guidelines, ensuring high performance, maintainability, and production readiness.
