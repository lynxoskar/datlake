#!/bin/bash

# DuckLake Kubernetes Build and Deploy Script
# Usage: ./build-and-deploy.sh [environment] [action]
# Environment: local, prod
# Action: build, deploy, all

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="datlake"
BACKEND_IMAGE="ducklake-backend"
VERSION=${DOCKER_TAG:-"v1.0.2"}
REGISTRY=${DOCKER_REGISTRY:-""}
NAMESPACE=${K8S_NAMESPACE:-"default"}

# Default values
ENVIRONMENT=${1:-"local"}
ACTION=${2:-"all"}

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if docker is available
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed or not in PATH"
    fi
    
    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        error "kubectl is not installed or not in PATH"
    fi
    
    # Check if kubectl can connect to cluster
    if ! kubectl cluster-info &> /dev/null; then
        error "Cannot connect to Kubernetes cluster. Check your kubeconfig."
    fi
    
    success "Prerequisites check passed"
}

# Build Docker image
build_image() {
    log "Building Docker image for backend..."
    
    # Navigate to project root
    cd "$(dirname "$0")/.."
    
    # Build image with proper tag
    local image_tag="${BACKEND_IMAGE}:${VERSION}"
    if [ -n "$REGISTRY" ]; then
        image_tag="${REGISTRY}/${image_tag}"
    fi
    
    log "Building image: ${image_tag}"
    
    docker build \
        -t "${image_tag}" \
        -f Dockerfile \
        . || error "Failed to build Docker image"
    
    success "Docker image built: ${image_tag}"
    
    # If using a registry, push the image
    if [ -n "$REGISTRY" ]; then
        log "Pushing image to registry..."
        docker push "${image_tag}" || error "Failed to push image to registry"
        success "Image pushed to registry: ${image_tag}"
    fi
}

# Create namespace if it doesn't exist
create_namespace() {
    log "Checking/creating namespace: ${NAMESPACE}"
    
    if ! kubectl get namespace "${NAMESPACE}" &> /dev/null; then
        kubectl create namespace "${NAMESPACE}"
        success "Created namespace: ${NAMESPACE}"
    else
        log "Namespace ${NAMESPACE} already exists"
    fi
}

# Deploy secrets
deploy_secrets() {
    log "Deploying secrets..."
    
    local secrets_dir="k8s"
    if [ "$ENVIRONMENT" = "prod" ]; then
        secrets_dir="k8s/prod"
    fi
    
    # Deploy PostgreSQL credentials
    if [ -f "${secrets_dir}/postgres-credentials.yaml" ]; then
        kubectl apply -n "${NAMESPACE}" -f "${secrets_dir}/postgres-credentials.yaml"
        success "PostgreSQL credentials deployed"
    fi
    
    # Deploy MinIO credentials  
    if [ -f "${secrets_dir}/minio-secret.yaml" ]; then
        kubectl apply -n "${NAMESPACE}" -f "${secrets_dir}/minio-secret.yaml"
        success "MinIO credentials deployed"
    fi
}

# Deploy backend service
deploy_backend() {
    log "Deploying backend service..."
    
    local deploy_dir="k8s"
    if [ "$ENVIRONMENT" = "prod" ]; then
        deploy_dir="k8s/prod"
    fi
    
    # Update image tag in deployment
    local deployment_file="${deploy_dir}/backend-deployment.yaml"
    local service_file="${deploy_dir}/backend-service.yaml"
    
    if [ ! -f "$deployment_file" ]; then
        deployment_file="k8s/backend-deployment.yaml"
    fi
    
    if [ ! -f "$service_file" ]; then
        service_file="k8s/backend-service.yaml"
    fi
    
    # Create temporary deployment file with correct image
    local temp_deployment=$(mktemp)
    local image_tag="${BACKEND_IMAGE}:${VERSION}"
    if [ -n "$REGISTRY" ]; then
        image_tag="${REGISTRY}/${image_tag}"
    fi
    
    sed "s|image: ducklake-backend:.*|image: ${image_tag}|g" "$deployment_file" > "$temp_deployment"
    
    # Apply deployment and service
    kubectl apply -n "${NAMESPACE}" -f "$temp_deployment"
    kubectl apply -n "${NAMESPACE}" -f "$service_file"
    
    # Cleanup temp file
    rm "$temp_deployment"
    
    success "Backend deployment applied"
    
    # Wait for deployment to be ready
    log "Waiting for backend deployment to be ready..."
    kubectl rollout status deployment/ducklake-backend -n "${NAMESPACE}" --timeout=300s
    
    success "Backend deployment is ready"
}

# Deploy ingress (if exists)
deploy_ingress() {
    local ingress_file="k8s/backend-ingress.yaml"
    if [ "$ENVIRONMENT" = "prod" ]; then
        local prod_ingress="k8s/prod/backend-ingress.yaml"
        if [ -f "$prod_ingress" ]; then
            ingress_file="$prod_ingress"
        fi
    fi
    
    if [ -f "$ingress_file" ]; then
        log "Deploying ingress..."
        kubectl apply -n "${NAMESPACE}" -f "$ingress_file"
        success "Ingress deployed"
    else
        warning "No ingress configuration found"
    fi
}

# Get deployment status
get_status() {
    log "Getting deployment status..."
    
    echo
    log "Pods:"
    kubectl get pods -n "${NAMESPACE}" -l app=ducklake-backend
    
    echo
    log "Services:"
    kubectl get services -n "${NAMESPACE}" -l app=ducklake-backend
    
    echo
    log "Ingress:"
    kubectl get ingress -n "${NAMESPACE}" 2>/dev/null || log "No ingress found"
    
    echo
    log "Backend logs (last 10 lines):"
    kubectl logs -n "${NAMESPACE}" -l app=ducklake-backend --tail=10 || warning "Could not fetch logs"
}

# Main deployment function
deploy() {
    log "Deploying to ${ENVIRONMENT} environment..."
    
    create_namespace
    deploy_secrets
    deploy_backend
    deploy_ingress
    get_status
    
    success "Deployment completed successfully!"
    
    # Show access information
    echo
    log "Access Information:"
    if [ "$ENVIRONMENT" = "local" ]; then
        echo "  Backend API: http://localhost:30000"
        echo "  Health Check: http://localhost:30000/health"
        echo "  SSE Test: http://localhost:30000/sse_test.html"
    else
        log "Check ingress configuration for external access"
    fi
}

# Main script logic
main() {
    log "Starting DuckLake K8s deployment..."
    log "Environment: ${ENVIRONMENT}"
    log "Action: ${ACTION}"
    log "Version: ${VERSION}"
    log "Namespace: ${NAMESPACE}"
    
    if [ -n "$REGISTRY" ]; then
        log "Registry: ${REGISTRY}"
    else
        warning "No registry specified, using local images"
    fi
    
    check_prerequisites
    
    case "$ACTION" in
        "build")
            build_image
            ;;
        "deploy")
            deploy
            ;;
        "all")
            build_image
            deploy
            ;;
        "status")
            get_status
            ;;
        *)
            error "Unknown action: $ACTION. Use: build, deploy, all, or status"
            ;;
    esac
    
    success "Script completed successfully!"
}

# Help function
show_help() {
    echo "DuckLake Kubernetes Build and Deploy Script"
    echo
    echo "Usage: $0 [environment] [action]"
    echo
    echo "Environments:"
    echo "  local   - Local development (default)"
    echo "  prod    - Production deployment"
    echo
    echo "Actions:"
    echo "  build   - Build Docker image only"
    echo "  deploy  - Deploy to Kubernetes only"
    echo "  all     - Build and deploy (default)"
    echo "  status  - Show deployment status"
    echo
    echo "Environment Variables:"
    echo "  DOCKER_TAG      - Image tag (default: v1.0.2)"
    echo "  DOCKER_REGISTRY - Docker registry (optional)"
    echo "  K8S_NAMESPACE   - Kubernetes namespace (default: default)"
    echo
    echo "Examples:"
    echo "  $0                          # Build and deploy to local"
    echo "  $0 prod all                 # Build and deploy to production"
    echo "  $0 local build              # Build image for local"
    echo "  DOCKER_REGISTRY=myregistry.com $0 prod deploy"
}

# Handle help request
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    show_help
    exit 0
fi

# Run main function
main "$@" 