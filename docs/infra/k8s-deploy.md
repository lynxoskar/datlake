# 🚀 DuckLake Kubernetes Deployment

This directory contains Kubernetes configurations for deploying the DuckLake backend with comprehensive SSE zombie detection and real-time event streaming.

## 📋 Prerequisites

### Required Tools
- **Docker** (for building images)
- **kubectl** (configured to access your cluster)
- **Kubernetes cluster** (local or cloud)

### Optional Tools
- **nginx-ingress-controller** (for external access)
- **cert-manager** (for automatic TLS certificates)
- **Prometheus** (for metrics collection)

### Cluster Requirements
- **Kubernetes 1.19+**
- **2+ CPU cores** and **4GB+ RAM** available
- **Ingress controller** (nginx recommended)
- **Persistent volumes** (if using persistent storage)

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Internet      │    │  Kubernetes     │    │   Backend       │
│                 │────│  Ingress        │────│   Service       │
│   (HTTPS/HTTP)  │    │  (nginx)        │    │   (ClusterIP)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                               ┌─────────────────┐
                                               │   Backend Pods  │
                                               │   (3 replicas)  │
                                               │                 │
                                               │  ┌─SSE Manager  │
                                               │  ├─Queue Worker │
                                               │  ├─API Endpoints│
                                               │  └─Health Checks│
                                               └─────────────────┘
                                                        │
                        ┌─────────────────┬─────────────────┬─────────────────┐
                        │                 │                 │                 │
                ┌───────▼───────┐ ┌───────▼───────┐ ┌───────▼───────┐
                │  PostgreSQL   │ │     MinIO     │ │   External    │
                │   (Catalog)   │ │   (Storage)   │ │   Services    │
                └───────────────┘ └───────────────┘ └───────────────┘
```

## 🚀 Quick Start

### 1. **Build and Deploy (All-in-One)**
```bash
cd k8s
chmod +x build-and-deploy.sh
./build-and-deploy.sh local all
```

### 2. **Check Deployment Status**
```bash
./build-and-deploy.sh local status
```

### 3. **Access the API**
- **Local Development**: http://localhost:30000
- **With Ingress**: http://ducklake-api.local
- **Health Check**: http://localhost:30000/health
- **SSE Test Page**: http://localhost:30000/sse_test.html

## 📝 Detailed Deployment Steps

### Step 1: Prepare Environment
```bash
# Set environment variables (optional)
export DOCKER_TAG="v1.0.2"
export K8S_NAMESPACE="datlake-backend"
export DOCKER_REGISTRY="your-registry.com"

# Create namespace
kubectl create namespace datlake-backend
```

### Step 2: Deploy Secrets
```bash
# Deploy PostgreSQL credentials
kubectl apply -f postgres-credentials.yaml

# Deploy MinIO credentials  
kubectl apply -f minio-secret.yaml
```

### Step 3: Build Docker Image
```bash
# Build image locally
./build-and-deploy.sh local build

# Or with registry
DOCKER_REGISTRY="your-registry.com" ./build-and-deploy.sh prod build
```

### Step 4: Deploy Backend
```bash
# Deploy to local environment
./build-and-deploy.sh local deploy

# Deploy to production
./build-and-deploy.sh prod deploy
```

## 🔧 Configuration

### Environment-Specific Deployments

#### **Local Development**
- Uses `NodePort` service (port 30000)
- No TLS encryption
- Relaxed CORS policies
- Debug logging enabled

#### **Production**
- Uses `ClusterIP` with Ingress
- TLS encryption with cert-manager
- Strict CORS policies
- Production logging levels
- Rate limiting enabled

### **Image Configuration**
The deployment uses different image sources:

```bash
# Local development (built locally)
image: ducklake-backend:v1.0.2

# Production (with registry)
image: your-registry.com/ducklake-backend:v1.0.2
```

### **Environment Variables**
Key configuration options:

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Deployment environment | `production` |
| `DB_POSTGRES_HOST` | PostgreSQL hostname | `postgres-service.database.svc.cluster.local` |
| `STORAGE_MINIO_ENDPOINT` | MinIO endpoint | `minio-service.storage.svc.cluster.local:9000` |
| `SSE_HEARTBEAT_INTERVAL` | SSE heartbeat interval | `30` |
| `SSE_ZOMBIE_CHECK_INTERVAL` | Zombie detection interval | `60` |

## 🔍 Monitoring and Debugging

### **Check Pod Status**
```bash
kubectl get pods -l app=ducklake-backend -n default
kubectl describe pod <pod-name> -n default
```

### **View Logs**
```bash
# All pods
kubectl logs -l app=ducklake-backend -n default

# Specific pod
kubectl logs <pod-name> -n default

# Follow logs
kubectl logs -f -l app=ducklake-backend -n default
```

### **Port Forward for Local Access**
```bash
kubectl port-forward service/ducklake-backend-service 8000:80 -n default
```

### **Health Checks**
```bash
# Direct health check
curl http://localhost:30000/health

# Through ingress
curl http://ducklake-api.local/health
```

### **SSE Testing**
```bash
# Test SSE connection
curl -N -H "Accept: text/event-stream" http://localhost:30000/events/stream

# Zombie detection stats
curl http://localhost:30000/events/zombies
```

## 🚨 Troubleshooting

### **Common Issues**

#### **ImagePullBackOff**
```bash
# Check image exists
docker images | grep ducklake-backend

# Fix: Build image
./build-and-deploy.sh local build
```

#### **CrashLoopBackOff**
```bash
# Check logs
kubectl logs -l app=ducklake-backend -n default

# Common causes:
# - Missing environment variables
# - Database connection issues
# - Invalid configuration
```

#### **Service Not Accessible**
```bash
# Check service
kubectl get svc ducklake-backend-service -n default

# Check endpoints
kubectl get endpoints ducklake-backend-service -n default

# For ingress issues
kubectl get ingress -n default
kubectl describe ingress ducklake-backend-ingress -n default
```

#### **SSE Connection Issues**
```bash
# Check nginx ingress annotations
kubectl describe ingress ducklake-backend-ingress -n default

# Verify SSE-specific settings:
# - proxy-buffering: off
# - proxy-read-timeout: 3600
# - proxy-send-timeout: 3600
```

### **Resource Issues**
```bash
# Check resource usage
kubectl top pods -l app=ducklake-backend -n default

# Check node resources
kubectl top nodes

# Adjust resources in deployment if needed
```

## 🔐 Security Considerations

### **Production Security**
- **Non-root containers**: Runs as user 1000
- **Read-only filesystem**: Where possible
- **Security contexts**: Drops all capabilities
- **Network policies**: Recommended for production
- **TLS encryption**: Enabled in production ingress
- **Secret management**: Uses Kubernetes secrets

### **CORS Configuration**
- **Development**: Permissive (`*`)
- **Production**: Restricted to specific domains

### **Rate Limiting**
Production ingress includes:
- **Rate limit**: 100 requests/minute
- **Burst**: 50 requests

## 📊 Monitoring

### **Prometheus Metrics**
The backend exposes metrics at `/metrics`:
```bash
curl http://localhost:30000/metrics
```

### **Health Endpoints**
- `/health` - Basic health check
- `/metrics/memory` - Memory usage
- `/metrics/performance` - Performance stats
- `/events/stats` - SSE connection stats
- `/events/zombies` - Zombie detection stats

## 🔄 Scaling

### **Horizontal Scaling**
```bash
# Scale to 5 replicas
kubectl scale deployment ducklake-backend --replicas=5 -n default

# Auto-scaling (optional)
kubectl autoscale deployment ducklake-backend --cpu-percent=70 --min=3 --max=10 -n default
```

### **Resource Scaling**
Edit `backend-deployment.yaml`:
```yaml
resources:
  requests:
    memory: "1Gi"    # Increase for higher load
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "2000m"
```

## 🛠️ Customization

### **For Different Environments**
1. Copy configuration files to new directory (e.g., `k8s/staging/`)
2. Modify environment-specific values
3. Deploy using: `./build-and-deploy.sh staging all`

### **Custom Domains**
Update ingress configuration:
```yaml
# In backend-ingress.yaml
spec:
  rules:
  - host: api.your-domain.com  # Your custom domain
```

### **SSL Certificates**
For production with cert-manager:
```yaml
# In prod/backend-ingress.yaml
metadata:
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - api.your-domain.com
    secretName: your-tls-secret
```

## 📞 Support

### **Useful Commands**
```bash
# Quick deployment
./build-and-deploy.sh local all

# Status check
./build-and-deploy.sh local status

# Clean deployment
kubectl delete -f backend-deployment.yaml
kubectl delete -f backend-service.yaml

# Force image update
kubectl rollout restart deployment/ducklake-backend -n default
```

### **Log Collection**
```bash
# Collect all logs
kubectl logs -l app=ducklake-backend -n default --since=1h > backend-logs.txt

# Export configuration
kubectl get deployment ducklake-backend -o yaml -n default > current-deployment.yaml
``` 