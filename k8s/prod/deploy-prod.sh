#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

# Ensure you are connected to the correct Kubernetes cluster (e.g., via kubectl config use-context)

if [ -z "${PROD_CONTEXT+x}" ]; then echo "PROD_CONTEXT is unset"; exit 1; fi

# Create storage namespace if it doesn't exist
echo "Creating storage namespace"
kubectl --context "${PROD_CONTEXT}" create namespace storage || true

# Deploy MinIO using Helm (assuming a production-ready Helm chart and values)
echo "Deploying MinIO using Helm"
helm repo add minio https://charts.min.io/ || true
helm repo update
helm --kube-context "${PROD_CONTEXT}" upgrade --install minio minio/minio --namespace storage -f "$(dirname "$0")"/minio-values.yaml

# Deploy PostgreSQL using Helm (assuming a production-ready Helm chart and values)
echo "Deploying PostgreSQL using Helm"
helm repo add bitnami https://charts.bitnami.com/bitnami || true
helm repo update
helm --kube-context "${PROD_CONTEXT}" upgrade --install postgres bitnami/postgresql --namespace storage -f "$(dirname "$0")"/postgres-values.yaml

# Deploy MinIO credentials secret
echo "Deploying MinIO credentials secret"
kubectl --context "${PROD_CONTEXT}" apply -f "$(dirname "$0")"/minio-secret.yaml

# Deploy backend application
echo "Deploying backend application"
kubectl --context "${PROD_CONTEXT}" apply -f "$(dirname "$0")"/backend-deployment.yaml
kubectl --context "${PROD_CONTEXT}" apply -f "$(dirname "$0")"/backend-service.yaml

echo "DuckLake production deployment complete!"
