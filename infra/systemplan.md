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

### 2.3. DuckLake Service Environment

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
