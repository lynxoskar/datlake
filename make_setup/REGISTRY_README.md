# Docker Registry Setup for DuckLake

This document provides comprehensive information about the Docker registry integration in the DuckLake project.

## Overview

The Docker registry is a private container registry that stores and distributes Docker images within the Kubernetes cluster. It provides:

- **Centralized Image Storage**: All DuckLake images are stored in a single, accessible location
- **Development Workflow**: Seamless integration with local development and CI/CD pipelines
- **Version Management**: Support for image tagging and versioning
- **API Access**: Full Docker Registry HTTP API v2 for programmatic access

## Quick Start

### 1. Deploy Complete Environment

```bash
# Deploy everything including registry
make deploy-kind
```

### 2. Registry-Only Deployment

```bash
# Deploy just the registry
make deploy-registry
```

### 3. Build and Push Images

```bash
# Build and push DuckLake backend image
make build-and-push
```

### 4. Test Registry Functionality

```bash
# Run comprehensive registry tests
make test-registry
```

## Registry Configuration

### Access Points

- **Internal (within cluster)**: `docker-registry.storage.svc.cluster.local:5000`
- **External (development)**: `localhost:5000`
- **API Endpoint**: `http://localhost:5000/v2/`

### Storage Configuration

- **Persistent Volume**: 10Gi storage for image data
- **Storage Class**: Uses default Kubernetes storage class
- **Backend**: Filesystem-based storage (production can use S3)

### Security Features

- **Non-root execution**: Runs as user ID 1000
- **Read-only root filesystem**: Enhanced security
- **Dropped capabilities**: Minimal required privileges
- **CORS enabled**: Web client integration support

## Available Commands

### Main Registry Commands

| Command | Description |
|---------|-------------|
| `make deploy-registry` | Deploy Docker registry only |
| `make build-and-push` | Build and push image to registry |
| `make pull-from-registry` | Pull image from registry |
| `make list-registry-images` | List images in registry |
| `make registry-status` | Show registry status |
| `make test-registry` | Run registry functionality tests |
| `make clean-registry` | Remove registry deployment |

### Full Environment Commands

| Command | Description |
|---------|-------------|
| `make deploy-kind` | Deploy complete environment with registry |
| `make status` | Show all services including registry |
| `make destroy-kind` | Remove entire environment |

## Registry API Usage

### 1. Health Check

```bash
curl http://localhost:5000/v2/
```

### 2. List Repositories

```bash
curl http://localhost:5000/v2/_catalog
```

### 3. List Image Tags

```bash
curl http://localhost:5000/v2/ducklake-backend/tags/list
```

### 4. Image Manifest

```bash
curl -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
     http://localhost:5000/v2/ducklake-backend/manifests/latest
```

### 5. Delete Image (if enabled)

```bash
curl -X DELETE http://localhost:5000/v2/ducklake-backend/manifests/sha256:...
```

## Docker Client Usage

### 1. Build and Tag Image

```bash
docker build -t ducklake-backend:latest .
docker tag ducklake-backend:latest localhost:5000/ducklake-backend:latest
```

### 2. Push to Registry

```bash
docker push localhost:5000/ducklake-backend:latest
```

### 3. Pull from Registry

```bash
docker pull localhost:5000/ducklake-backend:latest
```

### 4. Run Image from Registry

```bash
docker run localhost:5000/ducklake-backend:latest
```

## Production Configuration

### Environment Variables

For production deployments, set these environment variables:

```bash
export PROD_CONTEXT="your-production-k8s-context"
export PROD_REGISTRY="your-production-registry.com"
export IMAGE_TAG="v1.0.0"
```

### Production Registry Features

- **TLS Termination**: HTTPS for secure communication
- **Authentication**: Basic auth or token-based authentication
- **Backup Strategy**: Regular backup of registry data
- **Monitoring**: Prometheus metrics integration
- **Scaling**: Multiple registry replicas with shared storage

## Troubleshooting

### Common Issues

#### 1. Registry Not Accessible

**Symptom**: `curl http://localhost:5000/v2/` fails

**Solutions**:
```bash
# Check registry pod status
kubectl get pods -n storage -l app=docker-registry

# Check registry service
kubectl get svc -n storage docker-registry-nodeport

# Check port forwarding
kubectl port-forward -n storage svc/docker-registry-nodeport 5000:5000
```

#### 2. Image Push Fails

**Symptom**: `docker push` returns authentication or connection errors

**Solutions**:
```bash
# Check Docker daemon configuration
docker info

# For insecure registry (development only)
# Add to Docker daemon configuration:
{
  "insecure-registries": ["localhost:5000"]
}

# Restart Docker daemon
sudo systemctl restart docker
```

#### 3. Registry Storage Full

**Symptom**: Push operations fail with storage errors

**Solutions**:
```bash
# Check storage usage
kubectl exec -n storage deployment/docker-registry -- df -h /var/lib/registry

# Clean up old images
make list-registry-images
# Manually delete unused images via API

# Increase storage size (edit registry-deployment.yaml)
kubectl patch pvc registry-storage -n storage -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'
```

#### 4. Registry Pod CrashLoopBackOff

**Symptom**: Registry pod keeps restarting

**Solutions**:
```bash
# Check pod logs
kubectl logs -n storage deployment/docker-registry

# Check pod events
kubectl describe pod -n storage -l app=docker-registry

# Check persistent volume
kubectl get pv,pvc -n storage
```

### Monitoring and Debugging

#### 1. Registry Logs

```bash
# Real-time logs
kubectl logs -f -n storage deployment/docker-registry

# Recent logs
kubectl logs -n storage deployment/docker-registry --tail=100
```

#### 2. Registry Metrics

```bash
# Pod resource usage
kubectl top pod -n storage -l app=docker-registry

# Storage usage
kubectl exec -n storage deployment/docker-registry -- df -h /var/lib/registry
```

#### 3. Network Connectivity

```bash
# Test from within cluster
kubectl run --rm -i --tty --image=alpine:latest test-registry --restart=Never -- sh
# Inside pod: wget -qO- http://docker-registry.storage.svc.cluster.local:5000/v2/

# Test external connectivity
curl -v http://localhost:5000/v2/
```

## Test Suite Details

The `test-registry.sh` script performs comprehensive testing:

### Test Categories

1. **Health Check**: Verifies registry API is responding
2. **Catalog API**: Tests repository listing functionality
3. **Tags API**: Tests image tag listing functionality
4. **Storage Check**: Verifies persistent storage accessibility
5. **Performance**: Measures API response times
6. **Image Operations**: Full push/pull cycle testing

### Running Tests

```bash
# Run all tests
make test-registry

# Run specific test manually
./make_setup/test-registry.sh

# Run with verbose output
VERBOSE=1 ./make_setup/test-registry.sh
```

### Test Results

- **Pass/Fail Status**: Each test reports success or failure
- **Performance Metrics**: Response time measurements
- **Storage Information**: Usage statistics and health
- **Image Operations**: Complete push/pull validation

## Architecture Integration

### Service Dependencies

```
Developer → Registry → Backend Pods
    ↓         ↓          ↓
  Build   Storage   Application
```

### Kubernetes Resources

- **Deployment**: `docker-registry` (1 replica)
- **Service**: `docker-registry` (ClusterIP)
- **Service**: `docker-registry-nodeport` (NodePort 30500)
- **PVC**: `registry-storage` (10Gi)
- **ConfigMap**: `registry-config` (registry configuration)

### Network Configuration

- **Namespace**: `storage`
- **Port**: 5000 (registry API)
- **NodePort**: 30500 (external access)
- **Service Discovery**: DNS-based service discovery

## Best Practices

### Development

1. **Use Latest Tags**: Always tag images with meaningful versions
2. **Clean Up**: Regularly remove unused images to save storage
3. **Test Locally**: Use `make test-registry` before pushing changes
4. **Monitor Storage**: Check registry storage usage regularly

### Production

1. **Use Specific Tags**: Never use `latest` tag in production
2. **Implement Authentication**: Secure registry access
3. **Enable TLS**: Use HTTPS for all registry communication
4. **Backup Strategy**: Regular backups of registry data
5. **Monitoring**: Implement comprehensive monitoring and alerting

### Security

1. **Network Policies**: Restrict registry access to authorized pods
2. **Image Scanning**: Scan images for vulnerabilities
3. **Access Control**: Implement role-based access control
4. **Audit Logging**: Enable comprehensive audit logging

## Future Enhancements

### Planned Features

1. **Authentication**: Token-based authentication system
2. **TLS Support**: HTTPS endpoint configuration
3. **Image Scanning**: Vulnerability scanning integration
4. **Backup Automation**: Automated backup and restore
5. **Monitoring Dashboard**: Grafana dashboard for registry metrics
6. **Multi-Registry**: Support for multiple registry instances

### Integration Roadmap

1. **CI/CD Pipeline**: GitHub Actions integration
2. **Helm Chart**: Helm chart for registry deployment
3. **Prometheus Metrics**: Detailed metrics collection
4. **Grafana Dashboard**: Visual monitoring interface
5. **Alerting**: Automated alerts for registry issues

## Support

For issues or questions about the registry setup:

1. Check the troubleshooting section above
2. Run `make test-registry` to diagnose issues
3. Check registry logs: `kubectl logs -n storage deployment/docker-registry`
4. Review the systemplan.md for architecture details

The registry is a critical component of the DuckLake infrastructure, providing reliable and secure image storage for all deployment scenarios. 