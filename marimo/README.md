# Marimo Deployment for Kubernetes

This directory contains the configuration and deployment files for running Marimo notebooks in a Kubernetes environment.

## Overview

Marimo is a reactive notebook for Python that runs in the browser. This deployment allows you to run your Marimo notebooks in a containerized environment with Kubernetes for scalability and management.

## Files

- `test_data_generator.py` - The main Marimo notebook for generating test data
- `Dockerfile` - Container definition for Marimo
- `deploy.sh` - Automated deployment script
- `README.md` - This documentation

## Prerequisites

- Docker installed and running
- Kubernetes cluster access
- kubectl configured
- NGINX Ingress Controller installed in your cluster
- Access to a container registry (Docker Hub, ECR, GCR, etc.)

## Quick Start

### 1. Update Configuration

Edit the deployment script variables:

```bash
export REGISTRY="your-registry"          # Your container registry
export TAG="v1.0.0"                     # Image tag
export NAMESPACE="default"               # Kubernetes namespace
export DOMAIN="marimo.your-domain.com"  # Your domain for access
```

### 2. Deploy to Kubernetes

```bash
# Make sure you're in the project root
cd /path/to/datlake

# Run the deployment script
./marimo/deploy.sh
```

### 3. Access Your Notebook

Once deployed, access your Marimo notebook at:
- **URL**: `http://your-domain.com` (or the domain you configured)
- **Local testing**: Use port-forwarding if you don't have ingress set up

```bash
kubectl port-forward service/marimo-service 2718:2718
# Then access at http://localhost:2718
```

## Manual Deployment

If you prefer to deploy manually:

### 1. Build and Push Image

```bash
# Build the Docker image
docker build -f marimo/Dockerfile -t your-registry/datlake-marimo:latest .

# Push to registry
docker push your-registry/datlake-marimo:latest
```

### 2. Update Kubernetes Manifests

Edit `k8s/marimo-deployment.yaml` and update:
- `image: your-registry/datlake-marimo:latest`
- Any environment variables as needed

Edit `k8s/marimo-ingress.yaml` and update:
- `host: marimo.your-domain.com`

### 3. Apply Manifests

```bash
kubectl apply -f k8s/marimo-deployment.yaml
kubectl apply -f k8s/marimo-service.yaml
kubectl apply -f k8s/marimo-ingress.yaml
```

## Local Development

For local development, you can run Marimo directly:

```bash
# Install dependencies
uv sync

# Run the notebook
.venv/bin/marimo run marimo/test_data_generator.py
```

## Configuration

### Environment Variables

The deployment supports these environment variables:

- `MARIMO_HOST` - Host to bind to (default: 0.0.0.0)
- `MARIMO_PORT` - Port to bind to (default: 2718)
- `BACKEND_URL` - URL of the backend API (default: http://backend-service:8000)
- `PYTHONUNBUFFERED` - Python buffering (default: 1)

### Backend Integration

The Marimo notebook connects to your DuckLake backend API for:
- Uploading generated data to MinIO
- Interacting with datasets
- Managing data lake operations

The backend URL is automatically configured for Kubernetes service discovery.

## Troubleshooting

### Common Issues

1. **Pod not starting**
   ```bash
   kubectl describe pod -l app=marimo
   kubectl logs -f deployment/marimo-deployment
   ```

2. **Image pull errors**
   - Verify your registry credentials
   - Check image name and tag
   - Ensure the image exists in your registry

3. **Ingress not working**
   - Verify NGINX Ingress Controller is installed
   - Check DNS configuration
   - Verify ingress annotations

4. **Backend connection issues**
   - Ensure backend service is running
   - Check service discovery configuration
   - Verify network policies

### Health Checks

The deployment includes health checks:
- **Liveness probe**: Checks if the container is running
- **Readiness probe**: Checks if the service is ready to accept traffic

### Monitoring

Check deployment status:
```bash
kubectl get pods -l app=marimo
kubectl get svc -l app=marimo
kubectl get ingress -l app=marimo
```

View logs:
```bash
kubectl logs -f deployment/marimo-deployment
```

## Security

The deployment includes security best practices:
- Non-root user execution
- Resource limits
- Security contexts
- Network policies (if configured)

## Scaling

To scale the deployment:
```bash
kubectl scale deployment marimo-deployment --replicas=3
```

Note: Marimo maintains session state, so scaling may affect user experience.

## Customization

### Adding New Notebooks

1. Add your `.py` file to the `marimo/` directory
2. Update the Dockerfile CMD to point to your new notebook
3. Rebuild and redeploy

### Custom Dependencies

Add dependencies to `pyproject.toml` and rebuild the image.

### Resource Limits

Adjust resource limits in `k8s/marimo-deployment.yaml`:
```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "500m"
```

## Support

For issues with:
- Marimo: Check the [Marimo documentation](https://marimo.io)
- Kubernetes: Check cluster logs and configuration
- DuckLake integration: Check backend service status 