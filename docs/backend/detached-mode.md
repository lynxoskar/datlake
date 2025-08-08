### **Project Plan: Datlake Detached Mode**

The goal is to allow two primary detached workflows:
1.  **Direct Data Ingestion:** Users/processes can write data directly to the object store (S3/Minio) and then register that data as a new table or snapshot in the Datlake system.
2.  **Direct Data Querying:** Users/clients (e.g., a local DuckDB instance) can query the Datlake API to resolve a table name into a physical data URI for direct consumption, respecting the platform's RBAC.

Here is a phased implementation plan:

#### **Phase 1: API Design & Specification**

First, we must define the API endpoints that will enable these workflows. These new endpoints should be versioned (e.g., `/api/v1/...`) and clearly separated from the existing application logic, perhaps in a new router file: `app/routers/detached.py`.

**Proposed Endpoints:**

1.  **`GET /api/v1/tables`**
    *   **Purpose:** List all tables the authenticated user is permitted to see.
    *   **Response:**
        ```json
        [
          {"name": "sales_q1", "latest_snapshot_id": "snap-123xyz"},
          {"name": "customer_data", "latest_snapshot_id": "snap-abc789"}
        ]
        ```

2.  **`GET /api/v1/tables/{table_name}/snapshots/latest`**
    *   **Purpose:** Retrieve the metadata for the latest snapshot of a specific table. This is the primary endpoint for the "direct query" workflow.
    *   **RBAC:** This endpoint must verify that the user has `SELECT` privileges on the requested table before returning data.
    *   **Response (Success):**
        ```json
        {
          "table_name": "sales_q1",
          "snapshot_id": "snap-123xyz",
          "uri": "s3://datlake-bucket/data/sales/q1_2025.parquet",
          "format": "parquet",
          "created_at": "2025-07-08T10:00:00Z",
          "schema": { "...": "..." }
        }
        ```
    *   **Response (Forbidden):** `403 Forbidden`

3.  **`POST /api/v1/jobs/register-snapshot`**
    *   **Purpose:** Register a new snapshot of data that has been manually uploaded to the object store. This is the core of the "direct ingestion" workflow.
    *   **RBAC:** This endpoint must verify the user has `INSERT` or `UPDATE` privileges for the given table.
    *   **Request Body:**
        ```json
        {
          "table_name": "sales_q2",
          "uri": "s3://datlake-bucket/data/sales/q2_2025.parquet",
          "format": "parquet",
          "schema": { "...": "..." } // Optional, can be inferred
        }
        ```
    *   **Action:** The backend would create a new job, validate the URI, and upon success, create the new table/snapshot metadata, linking it to the physical data.
    *   **Response:** The ID of the asynchronous job created to process the registration.

#### **Phase 2: Backend Implementation**

With the API defined, we can implement the backend logic.

1.  **Authentication:**
    *   Introduce a robust authentication scheme for the API, such as API keys or JWTs, for users and service accounts. These keys will be associated with roles in the RBAC system.

2.  **Router and Logic:**
    *   Create `app/routers/detached.py` to house the new endpoints.
    *   Implement the Pydantic models for the request/response bodies.
    *   The business logic within these endpoints will interface with your existing database models for tables, snapshots, and jobs.
    *   The key is the RBAC check: for every request, the handler must query the PostgreSQL permissions to authorize the action for the authenticated user.

3.  **Job Worker Enhancement:**
    *   The `register-snapshot` job handler will need to be created or updated. It should be resilient and perform the following steps:
        a. Validate the existence and accessibility of the provided data URI.
        b. (Optional) Infer the schema from the Parquet file if not provided.
        c. Create the corresponding metadata entries in the PostgreSQL database.
        d. Update the job status to `completed` or `failed`.

#### **Phase 3: Client-Side Tooling (SDK/CLI)**

To make this new mode useful, we should provide simple tools for users.

1.  **Python SDK:**
    *   A small Python package (`datlake-sdk`) that provides simple functions to wrap the API calls.
    *   **Example Usage:**
        ```python
        import duckdb
        from datlake_sdk import DatalakeClient

        # API key would be handled by env variables or config
        client = DatalakeClient()

        # Resolve a table name to a URI
        uri = client.get_table_uri("sales_q1")

        # Query directly with DuckDB
        results = duckdb.query(f"SELECT * FROM '{uri}'").to_df()
        print(results.head())
        ```

2.  **CLI Tool:**
    *   A command-line interface (`datalake-cli`) for quick, scriptable interactions.
    *   **Example Usage:**
        ```bash
        # Get a URI for use in a script
        export TABLE_URI=$(datalake-cli get-uri sales_q1)
        duckdb -c "COPY (SELECT * FROM '$TABLE_URI') TO 'local_copy.csv' (HEADER, DELIMITER ',');"

        # Register a new dataset
        datalake-cli register-snapshot --table-name new_data --uri s3://my-bucket/uploads/new.parquet
        ```

#### **Phase 4: Documentation & Rollout**

1.  **Update Documentation:** Create a new section in your project's `docs/` for "Detached Mode".
2.  **Tutorials:** Write clear, step-by-step tutorials for both primary workflows.
3.  **API Reference:** Automatically generate and publish the API documentation for the new endpoints.
