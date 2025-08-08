### **Project Plan: Datlake SDK with Local Caching**

The `datlake-sdk` will provide a simplified Python interface for interacting with the Datlake backend, specifically designed to support the "detached" mode of operation. A key feature will be a local cache for immutable data, such as versioned snapshots of tables and versioned datasets, to improve performance and reduce API calls.

#### **Phase 1: Core SDK Functionality**

1.  **API Client:**
    *   Implement a Python client to interact with the Datlake backend API (as defined in `detached_model_plan.md`).
    *   Handle authentication (API keys/JWTs).
    *   Provide methods for:
        *   `get_tables()`: List available tables.
        *   `get_latest_snapshot_uri(table_name)`: Resolve a table name to its latest snapshot URI and metadata.
        *   `register_snapshot(table_name, uri, format, schema)`: Register a new snapshot.

2.  **Error Handling & Retries:**
    *   Implement robust error handling for API calls (network issues, authentication failures, API errors).
    *   Include retry mechanisms with exponential backoff for transient errors.

#### **Phase 2: Local Caching Mechanism**

1.  **Cache Directory Structure:**
    *   Define a clear and consistent local cache directory structure (e.g., `~/.datlake/cache/`).
    *   Organize cached data by table name and snapshot ID to ensure immutability and versioning.

2.  **Cache Invalidation Strategy:**
    *   Since snapshots and datasets are immutable, cache invalidation is straightforward: once an entry is cached, it's valid forever.
    *   The cache will primarily store metadata (URIs, schemas) and potentially small, frequently accessed data samples.

3.  **Caching Logic:**
    *   When `get_latest_snapshot_uri` is called:
        *   Check the local cache first.
        *   If found and valid, return cached data.
        *   If not found or invalid (e.g., cache entry too old, though for immutable data this is less critical), call the Datlake API.
        *   Upon successful API response, store the metadata in the local cache before returning it to the user.
    *   Use a simple key-value store or file-based serialization (e.g., JSON, Pickle) for caching metadata.

4.  **Cache Management:**
    *   Provide utility functions for users to:
        *   Clear the entire cache.
        *   Clear cache entries for a specific table.

#### **Phase 3: Integration with Data Access Libraries**

1.  **DuckDB Integration:**
    *   Ensure the SDK seamlessly provides URIs that can be directly consumed by DuckDB.
    *   Consider helper functions that directly execute DuckDB queries using the resolved URIs.

2.  **Polars/Pandas Integration (Optional but Recommended):**
    *   Provide convenience methods to load data directly into Polars DataFrames or Pandas DataFrames using the resolved URIs and appropriate readers (e.g., `pyarrow`, `fsspec`).

#### **Phase 4: Configuration & Deployment**

1.  **Configuration:**
    *   Allow configuration of the Datlake API endpoint and authentication credentials via environment variables or a configuration file (e.g., `~/.datlake/config.ini`).
    *   Allow configuration of the local cache directory.

2.  **Packaging:**
    *   Package the SDK as a standard Python package (`setup.py` or `pyproject.toml`).
    *   Publish to PyPI for easy installation.

#### **Phase 5: Documentation & Examples**

1.  **API Reference:** Generate comprehensive API documentation for the SDK.
2.  **Usage Examples:** Provide clear code examples for all core functionalities, including caching.
3.  **Tutorials:** Create tutorials demonstrating common workflows (e.g., "Querying a table with DuckDB and the SDK," "Registering a new dataset").

---
