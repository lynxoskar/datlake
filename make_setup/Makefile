KIND_CLUSTER_NAME := ducklake-cluster
KIND_CONTEXT := kind-$(KIND_CLUSTER_NAME)
REGISTRY_HOST := localhost:5000
IMAGE_NAME := ducklake-backend
IMAGE_TAG := latest
REGISTRY_IMAGE := $(REGISTRY_HOST)/$(IMAGE_NAME):$(IMAGE_TAG)

# ===================================================================================
# Helpers
# ===================================================================================

# Check for required tools
CMD_EXISTS = command -v $(1) >/dev/null 2>&1

# ===================================================================================
# Docker Registry Targets
# ===================================================================================

.PHONY: deploy-registry
deploy-registry:
	@echo "Deploying Docker registry to storage namespace"
	@kubectl --context "$(KIND_CONTEXT)" create namespace storage --dry-run=client -o yaml | kubectl --context "$(KIND_CONTEXT)" apply -f -
	@kubectl --context "$(KIND_CONTEXT)" apply -f "../k8s/registry-deployment.yaml"
	@echo "✅ Docker registry deployed."
	
	@echo "Waiting for registry to be ready..."
	@kubectl --context "$(KIND_CONTEXT)" wait --for=condition=available --timeout=300s deployment/docker-registry -n storage
	@echo "✅ Docker registry is ready."

.PHONY: registry-status
registry-status:
	@echo "Checking Docker registry status..."
	@kubectl --context "$(KIND_CONTEXT)" get pods,svc -n storage -l app=docker-registry
	@echo ""
	@echo "Registry API endpoint: http://$(REGISTRY_HOST)/v2/"
	@echo "To test: curl http://$(REGISTRY_HOST)/v2/"

.PHONY: build-and-push
build-and-push:
	@echo "Building Docker image: $(IMAGE_NAME):$(IMAGE_TAG)"
	@cd .. && docker build -t "$(IMAGE_NAME):$(IMAGE_TAG)" -f Dockerfile .
	@echo "✅ Image built successfully."
	
	@echo "Tagging image for registry: $(REGISTRY_IMAGE)"
	@docker tag "$(IMAGE_NAME):$(IMAGE_TAG)" "$(REGISTRY_IMAGE)"
	@echo "✅ Image tagged for registry."
	
	@echo "Pushing image to registry: $(REGISTRY_IMAGE)"
	@docker push "$(REGISTRY_IMAGE)"
	@echo "✅ Image pushed to registry."

.PHONY: pull-from-registry
pull-from-registry:
	@echo "Pulling image from registry: $(REGISTRY_IMAGE)"
	@docker pull "$(REGISTRY_IMAGE)"
	@echo "✅ Image pulled from registry."

.PHONY: list-registry-images
list-registry-images:
	@echo "Images in registry:"
	@curl -s http://$(REGISTRY_HOST)/v2/_catalog | jq -r '.repositories[]' 2>/dev/null || echo "No images found or jq not available"
	@echo ""
	@echo "Tags for $(IMAGE_NAME):"
	@curl -s http://$(REGISTRY_HOST)/v2/$(IMAGE_NAME)/tags/list | jq -r '.tags[]' 2>/dev/null || echo "No tags found or jq not available"

.PHONY: clean-registry
clean-registry:
	@echo "Cleaning up Docker registry deployment"
	@kubectl --context "$(KIND_CONTEXT)" delete -f "../k8s/registry-deployment.yaml" --ignore-not-found=true
	@echo "✅ Docker registry cleaned up."

.PHONY: test-registry
test-registry:
	@echo "Running Docker registry tests..."
	@./test-registry.sh

# ===================================================================================
# Main Deployment Targets (Updated)
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

	@echo "Deploying Docker registry"
	@$(MAKE) deploy-registry
	@echo "✅ Docker registry deployed."

	@echo "Building and pushing ducklake-backend image to registry"
	@$(MAKE) build-and-push
	@echo "✅ Image pushed to registry."

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

	@echo "Updating backend deployment to use registry image"
	@sed 's|image: ducklake-backend:.*|image: $(REGISTRY_IMAGE)|g' "../k8s/backend-deployment.yaml" | kubectl --context "$(KIND_CONTEXT)" apply -f -
	@kubectl --context "$(KIND_CONTEXT)" apply -f "../k8s/backend-service.yaml"
	@echo "✅ Backend application deployed with registry image."

	@echo "Deploying logging stack (Loki/Promtail)"
	@kubectl --context "$(KIND_CONTEXT)" apply -f "../k8s/loki-deployment.yaml"
	@kubectl --context "$(KIND_CONTEXT)" apply -f "../k8s/promtail-deployment.yaml"
	@echo "✅ Logging stack deployed."

	@echo "Setting up port forwarding for log access"
	@kubectl --context "$(KIND_CONTEXT)" port-forward svc/loki 3100:3100 > /dev/null 2>&1 &
	@kubectl --context "$(KIND_CONTEXT)" port-forward svc/ducklake-backend-service 8000:80 > /dev/null 2>&1 &
	@echo "✅ Port forwarding established (Loki: 3100, Backend: 8000)"

	@echo ""
	@echo "🚀 DuckLake Kind cluster setup complete!"
	@echo "📦 Docker Registry: http://$(REGISTRY_HOST)"
	@echo "🔧 Backend API: http://localhost:8000"
	@echo "📊 Loki Logs: http://localhost:3100"
	@echo ""
	@echo "Registry status:"
	@$(MAKE) registry-status

.PHONY: deploy-prod
deploy-prod:
	@if [ -z "$(PROD_CONTEXT)" ]; then echo "Error: PROD_CONTEXT environment variable is not set."; exit 1; fi
	@if [ -z "$(PROD_REGISTRY)" ]; then echo "Error: PROD_REGISTRY environment variable is not set."; exit 1; fi
	
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

	@echo "Deploying backend application with production registry image"
	@sed 's|image: ducklake-backend:.*|image: $(PROD_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)|g' "../k8s/prod/backend-deployment.yaml" | kubectl --context "$(PROD_CONTEXT)" apply -f -
	@kubectl --context "$(PROD_CONTEXT)" apply -f "../k8s/prod/backend-service.yaml"
	@echo "✅ Backend application deployed with production registry image."

	@echo "Deploying logging stack (Loki/Promtail)"
	@kubectl --context "$(PROD_CONTEXT)" apply -f "../k8s/loki-deployment.yaml"
	@kubectl --context "$(PROD_CONTEXT)" apply -f "../k8s/promtail-deployment.yaml"
	@echo "✅ Logging stack deployed."

	@echo "🚀 DuckLake production deployment complete!"

# ===================================================================================
# Utility Targets
# ===================================================================================

.PHONY: status
status:
	@echo "=== Cluster Status ==="
	@kubectl --context "$(KIND_CONTEXT)" get nodes
	@echo ""
	@echo "=== Storage Namespace ==="
	@kubectl --context "$(KIND_CONTEXT)" get pods,svc -n storage
	@echo ""
	@echo "=== Default Namespace ==="
	@kubectl --context "$(KIND_CONTEXT)" get pods,svc
	@echo ""
	@echo "=== Registry Status ==="
	@$(MAKE) registry-status

.PHONY: logs
logs:
	@echo "Recent logs from backend pods:"
	@kubectl --context "$(KIND_CONTEXT)" logs -l app=ducklake-backend --tail=50

.PHONY: clean
clean:
	@echo "Cleaning up deployments..."
	@kubectl --context "$(KIND_CONTEXT)" delete -f "../k8s/backend-deployment.yaml" --ignore-not-found=true
	@kubectl --context "$(KIND_CONTEXT)" delete -f "../k8s/backend-service.yaml" --ignore-not-found=true
	@$(MAKE) clean-registry
	@echo "✅ Deployments cleaned up."

.PHONY: destroy-kind
destroy-kind:
	@echo "Destroying Kind cluster: $(KIND_CLUSTER_NAME)"
	@kind delete cluster --name "$(KIND_CLUSTER_NAME)"
	@echo "✅ Kind cluster destroyed."

.PHONY: help
help:
	@echo "DuckLake Infrastructure Management"
	@echo "=================================="
	@echo ""
	@echo "Main Targets:"
	@echo "  deploy-kind       Deploy complete local environment with registry"
	@echo "  deploy-prod       Deploy to production environment"
	@echo "  status            Show cluster and service status"
	@echo "  destroy-kind      Destroy local Kind cluster"
	@echo ""
	@echo "Registry Targets:"
	@echo "  deploy-registry   Deploy Docker registry only"
	@echo "  build-and-push    Build and push image to registry"
	@echo "  pull-from-registry Pull image from registry"
	@echo "  list-registry-images List images in registry"
	@echo "  registry-status   Show registry status"
	@echo "  test-registry     Run registry functionality tests"
	@echo "  clean-registry    Remove registry deployment"
	@echo ""
	@echo "Utility Targets:"
	@echo "  logs              Show recent backend logs"
	@echo "  clean             Clean up deployments (keep cluster)"
	@echo "  help              Show this help message"
	@echo ""
	@echo "Variables:"
	@echo "  IMAGE_TAG         Docker image tag (default: latest)"
	@echo "  PROD_CONTEXT      Production k8s context"
	@echo "  PROD_REGISTRY     Production registry host"