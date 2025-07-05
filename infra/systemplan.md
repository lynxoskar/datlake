# Infrastructure System Plan

## 1. Overview

This document outlines the plan for the Kubernetes (k8s) infrastructure required for the DuckLake project. The core components are:
- **MinIO:** S3-compatible object storage for raw datasets and as a backend for DuckDB tables.
- **PostgreSQL:** To store metadata, application state, or potentially complex relational data that supports the system.
- **DuckLake Service Environment:** A Kubernetes deployment to run our custom DuckDB-based service.

We will use Helm for deploying these stateful services to ensure maintainability and proper configuration.

## 2. Component Breakdown

### 2.1. MinIO Cluster

- **Purpose:** Primary storage for all raw data blobs (datasets) and the storage backend for DuckLake tables (via DuckDB's S3 support).
- **Deployment Method:** Use the official MinIO Helm chart. This simplifies setup, scaling, and management.
- **Configuration:**
    - Deploy in a standalone mode for simplicity, or a distributed mode for high availability if required.
    - Expose the MinIO service within the cluster using a `ClusterIP` service. For external access (if needed for direct uploads/downloads), an `Ingress` or `LoadBalancer` can be configured.
    - Secure with default credentials stored in a Kubernetes secret.
- **Action Items:**
    1. Add the MinIO Helm repository.
    2. Create a `minio-values.yaml` to configure persistence (PersistentVolumeClaim), service type, and credentials.
    3. Deploy MinIO using Helm into a dedicated `storage` namespace.

### 2.2. PostgreSQL Database

- **Purpose:** While DuckDB handles the analytical queries, PostgreSQL can be used for storing structured metadata that is not suitable for object storage, such as user information, application-level settings, or OpenLineage metadata if the OpenLineage backend requires it.
- **Deployment Method:** Use a robust PostgreSQL Helm chart, such as the one provided by Bitnami.
- **Configuration:**
    - Deploy as a single-node instance.
    - Configure a PersistentVolumeClaim for data persistence.
    - Store credentials and database configuration in Kubernetes secrets.
    - Expose via a `ClusterIP` service, as it only needs to be accessed by the backend service within the cluster.
- **Action Items:**
    1. Add the Bitnami Helm repository.
    2. Create a `postgres-values.yaml` to configure the user, password, database name, and persistence.
    3. Deploy PostgreSQL using Helm into the `storage` namespace.

### 2.3. Logging Infrastructure (Loki/Promtail)

- **Purpose:** Unified logging solution for collecting, aggregating, and querying logs from all Kubernetes pods and services. Provides centralized log management with structured JSON logging from applications.
- **Deployment Method:** Native Kubernetes manifests with Loki as a single-instance deployment and Promtail as a DaemonSet.
- **Configuration:**
    - **Loki (v2.9.0):** Log aggregation server with HTTP (3100) and gRPC (9096) endpoints
        - BoltDB index with filesystem object store
        - Embedded cache (100MB) for query performance
        - Single replication factor for development/testing
        - Resource limits: 256Mi memory, 200m CPU
    - **Promtail (v2.9.0):** DaemonSet for automatic log collection from all pods
        - Kubernetes service discovery for pod detection
        - CRI pipeline for container log parsing
        - Label mapping: namespace, pod, container, job metadata
        - Resource limits: 128Mi memory, 100m CPU
    - **Application Integration:** Structured JSON logging with service labels and request tracking
    - **Query Tools:** LogCLI available for command-line log analysis
- **Action Items:**
    1. Deploy Loki using existing manifest: `k8s/loki-deployment.yaml`
    2. Deploy Promtail DaemonSet using: `k8s/promtail-deployment.yaml`
    3. **✅ PostgreSQL Log Integration**: Enhanced Promtail configuration for PostgreSQL log parsing
    4. **✅ Log Parsing**: Structured parsing for PostgreSQL logs, PGMQ operations, and autovacuum activity
    5. **✅ Monitoring Tools**: PostgreSQL-specific log queries and real-time monitoring dashboard
    6. Configure persistent storage for production use (replace emptyDir volumes)
    7. Integrate Grafana dashboards for log visualization
    8. Implement log retention policies and S3-compatible storage backend
    9. Add alerting rules for critical log events

### 2.4. DuckLake Service Environment

- **Purpose:** This is the runtime environment for our custom Python backend. It's not for deploying DuckDB itself, but for running our application that *uses* the DuckDB library.
- **Deployment Method:** A standard Kubernetes `Deployment` and `Service`.
- **Configuration:**
    - **Dockerfile:** Create a Dockerfile for the Python backend. It will be based on a Python image, install dependencies using `uv`, and copy the application code.
    - **Deployment:** The Deployment will manage the pods running our backend service. It will mount necessary configurations and secrets.
    - **Service:** A `ClusterIP` service will expose the backend internally to other components, like the frontend.
    - **ConfigMap/Secrets:** Environment variables (e.g., database connections, MinIO endpoints) will be managed via a `ConfigMap` and `Secrets`.
- **Action Items:**
    1. Develop the Dockerfile for the backend application.
    2. Create Kubernetes manifest files (`deployment.yaml`, `service.yaml`, `configmap.yaml`).
    3. The deployment manifest will specify the container image, resource requests/limits, and environment variables.
