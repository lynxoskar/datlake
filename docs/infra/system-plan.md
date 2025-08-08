# Infrastructure System Plan

## 1. Overview

This document outlines the plan for the Kubernetes (k8s) infrastructure required for the DuckLake project. The core components are:
- **Docker Registry:** Private container registry for storing and distributing Docker images within the cluster.
- **MinIO:** S3-compatible object storage for raw datasets and as a backend for DuckDB tables.
- **PostgreSQL:** To store metadata, application state, or potentially complex relational data that supports the system.
- **DuckLake Service Environment:** A Kubernetes deployment to run our custom DuckDB-based service.

We will use Helm for deploying these stateful services to ensure maintainability and proper configuration.

## 2. Component Breakdown

### 2.1. Docker Registry

- **Purpose:** Private container registry for storing and distributing DuckLake Docker images within the Kubernetes cluster. Provides a centralized location for image management and enables proper CI/CD workflows.
- **Deployment Method:** Native Kubernetes deployment using the official Docker Registry v2 image.
- **Configuration:**
    - **Storage:** Uses PersistentVolumeClaim (10Gi) for image storage with filesystem backend
    - **Security:** Runs as non-root user (1000:1000) with dropped capabilities and read-only root filesystem
    - **Health Checks:** Liveness and readiness probes on `/v2/` endpoint
    - **Access:** ClusterIP service for internal access, NodePort (30500) for external development access
    - **API:** Full Docker Registry HTTP API v2 with CORS enabled for web client integration
    - **Features:** Image deletion enabled, comprehensive logging, and storage health monitoring
- **Resource Allocation:**
    - **Requests:** 128Mi memory, 100m CPU
    - **Limits:** 512Mi memory, 500m CPU
    - **Storage:** 10Gi persistent volume
- **Endpoints:**
    - **Internal:** `docker-registry.storage.svc.cluster.local:5000`
    - **External (dev):** `localhost:5000` (via NodePort)
    - **API Root:** `/v2/` (registry health and catalog)
- **Action Items:**
    1. ✅ **Registry Deployment**: Created `k8s/registry-deployment.yaml` with production-ready configuration
    2. ✅ **KIND Integration**: Updated `kind-cluster.yaml` for port forwarding (30500 → 5000)
    3. ✅ **Makefile Integration**: Added registry targets to `make_setup/Makefile`
    4. ✅ **Image Management**: Automated build-and-push workflow for DuckLake images
    5. **Image Cleanup**: Implement periodic cleanup of old/unused images
    6. **TLS Security**: Add TLS termination for production deployments
    7. **Authentication**: Implement authentication for production use
    8. **Backup Strategy**: Plan for registry data backup and disaster recovery

### 2.2. MinIO Cluster

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

### 2.3. PostgreSQL Database

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

### 2.4. Logging Infrastructure (Loki/Promtail)

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

### 2.5. DuckLake Service Environment

- **Purpose:** This is the runtime environment for our custom Python backend. It's not for deploying DuckDB itself, but for running our application that *uses* the DuckDB library.
- **Deployment Method:** A standard Kubernetes `Deployment` and `Service`.
- **Configuration:**
    - **Dockerfile:** Create a Dockerfile for the Python backend. It will be based on a Python image, install dependencies using `uv`, and copy the application code.
    - **Deployment:** The Deployment will manage the pods running our backend service. It will mount necessary configurations and secrets.
    - **Service:** A `ClusterIP` service will expose the backend internally to other components, like the frontend.
    - **ConfigMap/Secrets:** Environment variables (e.g., database connections, MinIO endpoints) will be managed via a `ConfigMap` and `Secrets`.
    - **Image Management:** Images stored in the private Docker registry and pulled during deployment.
- **Action Items:**
    1. ✅ **Dockerfile Development**: Multi-stage Dockerfile for the backend application.
    2. ✅ **Kubernetes Manifests**: Created deployment, service, and configuration files.
    3. ✅ **Registry Integration**: Updated deployment to use images from private registry.
    4. ✅ **SSE Support**: Added comprehensive Server-Sent Events with zombie detection.
    5. Implement health checks and monitoring endpoints.
    6. Add horizontal pod autoscaling based on CPU/memory usage.

## 3. Infrastructure Management

### 3.1. Development Workflow

The `make_setup/Makefile` provides a comprehensive development workflow:

```bash
# Complete environment setup
make deploy-kind

# Registry operations
make build-and-push        # Build and push images
make list-registry-images  # View stored images
make registry-status       # Check registry health

# Infrastructure management
make status               # View all services
make logs                # View backend logs
make clean               # Clean deployments
make destroy-kind        # Remove everything
```

### 3.2. Production Deployment

For production environments:

```bash
# Set production context and registry
export PROD_CONTEXT="production-cluster"
export PROD_REGISTRY="your-registry.com"

# Deploy to production
make deploy-prod
```

### 3.3. Registry Integration

The Docker registry is fully integrated with the deployment pipeline:

- **Automatic Build**: Images built from latest code during deployment
- **Version Management**: Support for image tagging and versioning
- **Local Development**: Registry accessible at `localhost:5000`
- **API Access**: Full Docker Registry API for image management
- **Cleanup**: Automated cleanup of old images and registry maintenance

### 3.4. Service Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Developer     │    │  Docker         │    │   Backend       │
│   Workstation   │────│  Registry       │────│   Pods          │
│                 │    │  :5000          │    │  (3 replicas)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                        ┌─────────────────┬─────────────────┬─────────────────┐
                        │                 │                 │                 │
                ┌───────▼───────┐ ┌───────▼───────┐ ┌───────▼───────┐
                │  PostgreSQL   │ │     MinIO     │ │     Loki      │
                │   (Metadata)  │ │   (Storage)   │ │   (Logs)      │
                └───────────────┘ └───────────────┘ └───────────────┘
```

## 4. Security Considerations

### 4.1. Registry Security

- **Network Isolation**: Registry deployed in `storage` namespace with network policies
- **Authentication**: Basic authentication planned for production deployments
- **TLS Encryption**: HTTPS termination for external access in production
- **Access Control**: Role-based access control for image push/pull operations
- **Vulnerability Scanning**: Integration with image scanning tools for security assessment

### 4.2. Storage Security

- **Data Encryption**: At-rest encryption for persistent volumes
- **Access Credentials**: Secure secret management for database and storage credentials
- **Network Segmentation**: Isolated network policies between services
- **Backup Security**: Encrypted backups with proper key management

## 5. Monitoring and Observability

### 5.1. Registry Monitoring

- **Health Endpoints**: Registry API health checks and metrics
- **Storage Monitoring**: Persistent volume usage and performance metrics
- **Access Logging**: Comprehensive logging of image push/pull operations
- **Performance Metrics**: Response times and throughput monitoring

### 5.2. Infrastructure Monitoring

- **Resource Utilization**: CPU, memory, and storage usage across all components
- **Service Health**: Health checks and availability monitoring
- **Log Aggregation**: Centralized logging with Loki for all services
- **Alerting**: Automated alerts for service failures and resource exhaustion

This comprehensive infrastructure plan provides a solid foundation for the DuckLake project with proper container image management, scalable storage solutions, and robust monitoring capabilities.
