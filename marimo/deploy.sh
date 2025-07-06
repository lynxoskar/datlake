#!/bin/bash

# Marimo Deployment Script for Kubernetes
# This script builds and deploys the Marimo notebook to Kubernetes

set -e

# Configuration
REGISTRY=${REGISTRY:-"your-registry"}
IMAGE_NAME="${REGISTRY}/datlake-marimo"
TAG=${TAG:-"latest"}
NAMESPACE=${NAMESPACE:-"default"}
DOMAIN=${DOMAIN:-"marimo.your-domain.com"}

echo "🚀 Deploying Marimo to Kubernetes"
echo "Registry: $REGISTRY"
echo "Image: $IMAGE_NAME:$TAG"
echo "Namespace: $NAMESPACE"
echo "Domain: $DOMAIN"

# Step 1: Build the Docker image
echo "📦 Building Docker image..."
docker build -f marimo/Dockerfile -t "$IMAGE_NAME:$TAG" .

# Step 2: Push to registry (if not local)
if [ "$REGISTRY" != "local" ]; then
    echo "🔄 Pushing image to registry..."
    docker push "$IMAGE_NAME:$TAG"
fi

# Step 3: Update the deployment with the correct image
echo "🔧 Updating deployment manifests..."
sed -i.bak "s|your-registry/datlake-marimo:latest|$IMAGE_NAME:$TAG|g" k8s/marimo-deployment.yaml
sed -i.bak "s|marimo.your-domain.com|$DOMAIN|g" k8s/marimo-ingress.yaml

# Step 4: Apply Kubernetes manifests
echo "🎯 Applying Kubernetes manifests..."
kubectl apply -f k8s/marimo-deployment.yaml -n "$NAMESPACE"
kubectl apply -f k8s/marimo-service.yaml -n "$NAMESPACE"
kubectl apply -f k8s/marimo-ingress.yaml -n "$NAMESPACE"

# Step 5: Wait for deployment to be ready
echo "⏳ Waiting for deployment to be ready..."
kubectl rollout status deployment/marimo-deployment -n "$NAMESPACE"

# Step 6: Show deployment status
echo "📊 Deployment Status:"
kubectl get pods -l app=marimo -n "$NAMESPACE"
kubectl get svc -l app=marimo -n "$NAMESPACE"
kubectl get ingress -l app=marimo -n "$NAMESPACE"

echo "✅ Marimo deployment completed!"
echo "🌐 Access your Marimo notebook at: http://$DOMAIN"
echo "📝 To check logs: kubectl logs -f deployment/marimo-deployment -n $NAMESPACE"

# Restore original files
mv k8s/marimo-deployment.yaml.bak k8s/marimo-deployment.yaml
mv k8s/marimo-ingress.yaml.bak k8s/marimo-ingress.yaml

echo "🔄 Original manifests restored" 