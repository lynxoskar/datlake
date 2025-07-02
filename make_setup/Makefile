KIND_CLUSTER_NAME := ducklake-cluster
KIND_CONTEXT := kind-$(KIND_CLUSTER_NAME)

# ===================================================================================
# Helpers
# ===================================================================================

# Check for required tools
CMD_EXISTS = command -v $(1) >/dev/null 2>&1

# ===================================================================================
# Targets
# ===================================================================================

.PHONY: deploy-kind
deploy-kind:
	@if ! $(call CMD_EXISTS,kind); then \
		echo "Error: kind is not installed. Please install kind and try again."; \
		exit 1; \
	fi
	@if ! $(call CMD_EXISTS,kubectl); then \
		echo "Error: kubectl is not installed. Please install kubectl and try again."; \
		exit 1; \
	fi
	@if ! $(call CMD_EXISTS,helm); then \
		echo "Error: helm is not installed. Please install helm and try again."; \
		exit 1; \
	fi
	@echo "✅ All required tools are installed."

	@if ! kind get clusters | grep -q "^$(KIND_CLUSTER_NAME)$$"; then \
		echo "Creating Kind cluster: $(KIND_CLUSTER_NAME)"; \
		kind create cluster --name "$(KIND_CLUSTER_NAME)" --config "../k8s/local/kind-cluster.yaml"; \
		echo "✅ Kind cluster created."; \
	else \
		echo "Found existing Kind cluster: $(KIND_CLUSTER_NAME). Skipping creation."; \
	fi

	@echo "Loading ducklake-backend:latest image into Kind cluster"
	@kind load docker-image ducklake-backend:latest --name "$(KIND_CLUSTER_NAME)"
	@echo "✅ Docker image loaded."

	@echo "Creating storage namespace"
	@kubectl --context "$(KIND_CONTEXT)" create namespace storage --dry-run=client -o yaml | kubectl --context "$(KIND_CONTEXT)" apply -f -
	@echo "✅ Storage namespace ensured."

	@echo "Deploying MinIO using Helm"
	@helm repo add minio https://charts.min.io/ > /dev/null 2>&1 || true
	@helm repo update > /dev/null 2>&1
	@helm --kube-context "$(KIND_CONTEXT)" upgrade --install minio minio/minio --namespace storage -f "../k8s/minio-values.yaml"
	@echo "✅ MinIO deployment is up to date."

	@echo "Deploying PostgreSQL using Helm"
	@helm repo add bitnami https://charts.bitnami.com/bitnami > /dev/null 2>&1 || true
	@helm repo update > /dev/null 2>&1
	@helm --kube-context "$(KIND_CONTEXT)" upgrade --install postgres bitnami/postgresql --namespace storage -f "../k8s/postgres-values.yaml"
	@echo "✅ PostgreSQL deployment is up to date."

	@echo "Deploying MinIO credentials secret"
	@kubectl --context "$(KIND_CONTEXT)" apply -f "../k8s/minio-secret.yaml"
	@echo "✅ MinIO secret applied."

	@echo "Deploying backend application"
	@kubectl --context "$(KIND_CONTEXT)" apply -f "../k8s/backend-deployment.yaml"
	@kubectl --context "$(KIND_CONTEXT)" apply -f "../k8s/backend-service.yaml"
	@echo "✅ Backend application deployed."

	@echo "🚀 DuckLake Kind cluster setup complete!"

.PHONY: deploy-prod
deploy-prod:
	@if [ -z "$(PROD_CONTEXT)" ]; then echo "Error: PROD_CONTEXT environment variable is not set."; exit 1; fi
	@echo "Creating storage namespace"
	@kubectl --context "$(PROD_CONTEXT)" create namespace storage --dry-run=client -o yaml | kubectl --context "$(PROD_CONTEXT)" apply -f -
	@echo "✅ Storage namespace ensured."

	@echo "Deploying MinIO using Helm"
	@helm repo add minio https://charts.min.io/ > /dev/null 2>&1 || true
	@helm repo update > /dev/null 2>&1
	@helm --kube-context "$(PROD_CONTEXT)" upgrade --install minio minio/minio --namespace storage -f "../k8s/prod/minio-values.yaml"
	@echo "✅ MinIO deployment is up to date."

	@echo "Deploying PostgreSQL using Helm"
	@helm repo add bitnami https://charts.bitnami.com/bitnami > /dev/null 2>&1 || true
	@helm repo update > /dev/null 2>&1
	@helm --kube-context "$(PROD_CONTEXT)" upgrade --install postgres bitnami/postgresql --namespace storage -f "../k8s/prod/postgres-values.yaml"
	@echo "✅ PostgreSQL deployment is up to date."

	@echo "Deploying MinIO credentials secret"
	@kubectl --context "$(PROD_CONTEXT)" apply -f "../k8s/prod/minio-secret.yaml"
	@echo "✅ MinIO secret applied."

	@echo "Deploying backend application"
	@kubectl --context "$(PROD_CONTEXT)" apply -f "../k8s/prod/backend-deployment.yaml"
	@kubectl --context "$(PROD_CONTEXT)" apply -f "../k8s/prod/backend-service.yaml"
	@echo "✅ Backend application deployed."

	@echo "🚀 DuckLake production deployment complete!"