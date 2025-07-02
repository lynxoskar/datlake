# DuckLake Project Plan

## 1. Project Vision

To create a modern, containerized data lakehouse system named "DuckLake" running on Kubernetes. The system will provide a unified REST API for managing both structured data in DuckDB and unstructured data in MinIO. It will feature data lineage tracking with OpenLineage, a web-based data browser, and a Python-based environment for testing and data manipulation.

## 2. Core Technologies

*   **Orchestration:** Kubernetes (K8s)
*   **Storage:** MinIO (S3-compatible object storage)
*   **Analytical Engine:** DuckDB
*   **Metadata/Supporting DB:** PostgreSQL
*   **Backend:** Python with FastAPI, Loguru, uv
*   **CLI:** Typer, Rich
*   **Frontend:** To be determined (likely a modern JavaScript framework like React or Vue)
*   **Data Science/Testing:** Marimo notebook
*   **Data Lineage:** OpenLineage

## 3. Project Components

This project is divided into four main components, each with its own detailed system plan:

1.  **[Infrastructure](./infra/systemplan.md):** The foundational Kubernetes setup for all services.
2.  **[Backend](./backend/systemplan.md):** The core REST API and business logic for interacting with data.
3.  **[Frontend](./frontend/systemplan.md):** The web interface for data exploration and management.
4.  **[Testing](./testing/systemplan.md):** The strategy and tools for ensuring system quality and generating test data.

## 4. Key Documentation Links

*   **DuckDB:** [https://duckdb.org/docs/](https://duckdb.org/docs/)
*   **DuckDB S3 Filesystem (for MinIO integration):** [https://duckdb.org/docs/extensions/httpfs.html](https://duckdb.org/docs/extensions/httpfs.html)
*   **MinIO:** [https://min.io/docs/minio/kubernetes/upstream/index.html](https://min.io/docs/minio/kubernetes/upstream/index.html)
*   **PostgreSQL on K8s:** [https://www.postgresql.org/docs/](https://www.postgresql.org/docs/) (General), Bitnami Helm chart for specifics.
*   **FastAPI:** [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
*   **OpenLineage:** [https://openlineage.io/docs/](https://openlineage.io/docs/)
*   **Marimo:** [https://marimo.io/](https://marimo.io/)
