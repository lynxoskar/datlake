#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

KIND_CLUSTER_NAME="ducklake-cluster"
KIND_CONTEXT="kind-${KIND_CLUSTER_NAME}"

# Create Kind cluster
echo "Creating Kind cluster: ${KIND_CLUSTER_NAME}"
kind create cluster --name "${KIND_CLUSTER_NAME}" --config "$(dirname "$0")"/kind-cluster.yaml

# Load Docker image into Kind cluster
echo "Loading ducklake-backend:latest image into Kind cluster"
kind load docker-image ducklake-backend:latest --name "${KIND_CLUSTER_NAME}"

# Create storage namespace
echo "Creating storage namespace"
kubectl --context "${KIND_CONTEXT}" create namespace storage || true

# Deploy MinIO using Helm
echo "Deploying MinIO using Helm"
helm repo add minio https://charts.min.io/ || true
helm repo update
helm --kube-context "${KIND_CONTEXT}" install minio minio/minio --namespace storage -f "$(dirname "$0")"/../minio-values.yaml

# Deploy PostgreSQL using Helm
echo "Deploying PostgreSQL using Helm"
helm repo add bitnami https://charts.bitnami.com/bitnami || true
helm repo update
helm --kube-context "${KIND_CONTEXT}" install postgres bitnami/postgresql --namespace storage -f "$(dirname "$0")"/../postgres-values.yaml

# Deploy MinIO credentials secret
echo "Deploying MinIO credentials secret"
kubectl --context "${KIND_CONTEXT}" apply -f "$(dirname "$0")"/../minio-secret.yaml

# Deploy backend application
echo "Deploying backend application"
kubectl --context "${KIND_CONTEXT}" apply -f "$(dirname "$0")"/../backend-deployment.yaml
kubectl --context "${KIND_CONTEXT}" apply -f "$(dirname "$0")"/../backend-service.yaml

echo "DuckLake Kind cluster setup complete!"
