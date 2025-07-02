# Backend System Plan

## 1. Overview

The backend service is the core of the DuckLake system. It will be a Python application built with FastAPI, providing a RESTful API for all data operations. It will interact with MinIO for object storage and DuckDB for analytical queries.

## 2. Core Technologies

- **Framework:** FastAPI
- **Async Support:** Uvicorn
- **Database Connector:** DuckDB Python client
- **Object Storage:** MinIO Python client (boto3)
- **Logging:** Loguru
- **CLI for admin tasks:** Typer, Rich

## 3. API Endpoints

The following is a preliminary list of API endpoints. Each will be documented with OpenAPI thanks to FastAPI.

### 3.1. DuckLake Table Operations

- `POST /tables`: Create a new table.
- `PUT /tables/{table_name}`: Append data to a table.
- `DELETE /tables/{table_name}`: Delete a table.
- `GET /tables/{table_name}`: Get table schema and metadata.
- `POST /tables/{table_name}/query`: Execute a query on a table.

### 3.2. MinIO Dataset Operations

- `POST /datasets/{bucket_name}`: Create a new bucket.
- `PUT /datasets/{bucket_name}/{object_name}`: Upload a file.
- `GET /datasets/{bucket_name}/{object_name}`: Download a file.
- `DELETE /datasets/{bucket_name}/{object_name}`: Delete a file.
- `GET /datasets/{bucket_name}`: List objects in a bucket.

### 3.3. OpenLineage Integration

- The backend will be instrumented with the OpenLineage Python client.
- Lineage events will be emitted for all major data operations (table creation, modification, etc.).
- The OpenLineage endpoint will be configured via environment variables.

## 4. Implementation Details

- **DuckDB Integration:** The backend will use the DuckDB Python library to execute queries. It will be configured to use the S3 filesystem to read and write data from/to MinIO.
- **MinIO Integration:** The `boto3` library will be used for direct communication with the MinIO API for bucket and object operations.
- **Metadata:** The backend will handle mediatype information for objects in MinIO, storing it as metadata on the objects themselves.
- **Error Handling:** Proper error handling and HTTP status codes will be implemented for all API endpoints.
