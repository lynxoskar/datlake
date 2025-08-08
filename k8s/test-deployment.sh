#!/bin/bash

# DuckLake Kubernetes Deployment Test Script
# Validates configuration files and deployment readiness

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

test_file_exists() {
    local file="$1"
    local description="$2"
    
    if [ -f "$file" ]; then
        success "$description: $file exists"
        ((TESTS_PASSED++))
        return 0
    else
        error "$description: $file missing"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_yaml_syntax() {
    local file="$1"
    local description="$2"
    
    if ! command -v kubectl &> /dev/null; then
        warning "kubectl not available, skipping YAML syntax check for $file"
        return 0
    fi
    
    if kubectl apply --dry-run=client -f "$file" &> /dev/null; then
        success "$description: YAML syntax valid"
        ((TESTS_PASSED++))
        return 0
    else
        error "$description: YAML syntax invalid"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_docker_context() {
    log "Testing Docker build context..."
    
    # Check if Dockerfile exists
    if [ -f "../Dockerfile" ]; then
        success "Dockerfile found in project root"
        ((TESTS_PASSED++))
    else
        error "Dockerfile missing in project root"
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Check if backend app directory exists
    if [ -d "../backend/app" ]; then
        success "Backend app directory exists"
        ((TESTS_PASSED++))
    else
        error "Backend app directory missing"
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Check if pyproject.toml exists
    if [ -f "../pyproject.toml" ]; then
        success "pyproject.toml found"
        ((TESTS_PASSED++))
    else
        error "pyproject.toml missing"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_prerequisites() {
    log "Testing prerequisites..."
    
    # Check Docker
    if command -v docker &> /dev/null; then
        success "Docker is available"
        ((TESTS_PASSED++))
    else
        error "Docker is not installed or not in PATH"
        ((TESTS_FAILED++))
    fi
    
    # Check kubectl
    if command -v kubectl &> /dev/null; then
        success "kubectl is available"
        ((TESTS_PASSED++))
        
        # Test cluster connectivity
        if kubectl cluster-info &> /dev/null; then
            success "Kubernetes cluster is accessible"
            ((TESTS_PASSED++))
        else
            warning "Cannot connect to Kubernetes cluster"
            warning "This is OK if testing without an active cluster"
        fi
    else
        warning "kubectl is not installed or not in PATH"
        warning "Required for actual deployment"
    fi
}

test_configuration_files() {
    log "Testing Kubernetes configuration files..."
    
    # Core deployment files
    test_file_exists "backend-deployment.yaml" "Backend deployment"
    test_file_exists "backend-service.yaml" "Backend service"
    test_file_exists "backend-ingress.yaml" "Backend ingress"
    test_file_exists "postgres-credentials.yaml" "PostgreSQL credentials"
    test_file_exists "minio-secret.yaml" "MinIO secret"
    
    # Production files
    test_file_exists "prod/backend-ingress.yaml" "Production ingress"
    
    # Scripts
    test_file_exists "build-and-deploy.sh" "Build and deploy script"
    
    # Check script is executable
    if [ -x "build-and-deploy.sh" ]; then
        success "Build script is executable"
        ((TESTS_PASSED++))
    else
        error "Build script is not executable"
        ((TESTS_FAILED++))
    fi
}

test_yaml_syntax_all() {
    log "Testing YAML syntax..."
    
    # Only test if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        warning "kubectl not available, skipping YAML syntax tests"
        return 0
    fi
    
    test_yaml_syntax "backend-deployment.yaml" "Backend deployment YAML"
    test_yaml_syntax "backend-service.yaml" "Backend service YAML"
    test_yaml_syntax "backend-ingress.yaml" "Backend ingress YAML"
    test_yaml_syntax "postgres-credentials.yaml" "PostgreSQL credentials YAML"
    test_yaml_syntax "minio-secret.yaml" "MinIO secret YAML"
    
    if [ -f "prod/backend-ingress.yaml" ]; then
        test_yaml_syntax "prod/backend-ingress.yaml" "Production ingress YAML"
    fi
}

test_image_configuration() {
    log "Testing image configuration..."
    
    # Check if deployment has correct image reference
    if grep -q "image: ducklake-backend:" backend-deployment.yaml; then
        success "Backend deployment has correct image reference"
        ((TESTS_PASSED++))
    else
        error "Backend deployment missing or incorrect image reference"
        ((TESTS_FAILED++))
    fi
    
    # Check if image tag is consistent
    local image_tag=$(grep "image: ducklake-backend:" backend-deployment.yaml | head -1 | sed 's/.*ducklake-backend://' | sed 's/[[:space:]]*$//')
    if [ -n "$image_tag" ]; then
        success "Image tag found: $image_tag"
        ((TESTS_PASSED++))
    else
        error "Could not extract image tag"
        ((TESTS_FAILED++))
    fi
}

test_environment_variables() {
    log "Testing environment variable configuration..."
    
    # Check for essential environment variables
    local required_envs=(
        "ENVIRONMENT"
        "DB_POSTGRES_HOST"
        "DB_POSTGRES_USER"
        "DB_POSTGRES_PASSWORD"
        "STORAGE_MINIO_ENDPOINT"
        "STORAGE_MINIO_ACCESS_KEY"
        "STORAGE_MINIO_SECRET_KEY"
    )
    
    for env_var in "${required_envs[@]}"; do
        if grep -q "name: $env_var" backend-deployment.yaml; then
            success "Environment variable $env_var is configured"
            ((TESTS_PASSED++))
        else
            error "Environment variable $env_var is missing"
            ((TESTS_FAILED++))
        fi
    done
}

test_sse_configuration() {
    log "Testing SSE-specific configuration..."
    
    # Check for SSE environment variables
    local sse_envs=(
        "SSE_HEARTBEAT_INTERVAL"
        "SSE_PING_INTERVAL"
        "SSE_ZOMBIE_CHECK_INTERVAL"
    )
    
    for env_var in "${sse_envs[@]}"; do
        if grep -q "name: $env_var" backend-deployment.yaml; then
            success "SSE environment variable $env_var is configured"
            ((TESTS_PASSED++))
        else
            warning "SSE environment variable $env_var is missing (using defaults)"
        fi
    done
    
    # Check ingress SSE annotations
    if grep -q "proxy-buffering.*off" backend-ingress.yaml; then
        success "Ingress has SSE proxy-buffering disabled"
        ((TESTS_PASSED++))
    else
        error "Ingress missing SSE proxy-buffering configuration"
        ((TESTS_FAILED++))
    fi
    
    if grep -q "proxy-read-timeout.*3600" backend-ingress.yaml; then
        success "Ingress has SSE proxy-read-timeout configured"
        ((TESTS_PASSED++))
    else
        error "Ingress missing SSE proxy-read-timeout configuration"
        ((TESTS_FAILED++))
    fi
}

test_resource_configuration() {
    log "Testing resource configuration..."
    
    # Check if resources are defined
    if grep -q "resources:" backend-deployment.yaml; then
        success "Resource limits are defined"
        ((TESTS_PASSED++))
    else
        error "Resource limits are missing"
        ((TESTS_FAILED++))
    fi
    
    # Check if memory limits are appropriate
    if grep -A 10 "resources:" backend-deployment.yaml | grep -q "memory.*[5-9][0-9][0-9]Mi\|[0-9]Gi"; then
        success "Memory limits appear appropriate for SSE workload"
        ((TESTS_PASSED++))
    else
        warning "Memory limits may be too low for SSE and queue processing"
    fi
}

# Main test execution
main() {
    echo "🧪 DuckLake Kubernetes Deployment Test Suite"
    echo "=============================================="
    echo
    
    # Change to k8s directory
    cd "$(dirname "$0")"
    
    # Run all tests
    test_prerequisites
    test_docker_context
    test_configuration_files
    test_yaml_syntax_all
    test_image_configuration
    test_environment_variables
    test_sse_configuration
    test_resource_configuration
    
    # Summary
    echo
    echo "=============================================="
    echo "Test Summary:"
    success "Tests passed: $TESTS_PASSED"
    if [ $TESTS_FAILED -gt 0 ]; then
        error "Tests failed: $TESTS_FAILED"
    else
        echo -e "${GREEN}All tests passed!${NC}"
    fi
    echo
    
    # Recommendations
    if [ $TESTS_FAILED -gt 0 ]; then
        echo "🔧 Recommendations:"
        echo "1. Fix the failed tests above"
        echo "2. Run this test again to verify fixes"
        echo "3. Use './build-and-deploy.sh local build' to test Docker build"
        echo "4. Use './build-and-deploy.sh local all' for full deployment"
        echo
        exit 1
    else
        echo "🚀 Ready for deployment!"
        echo "Run: ./build-and-deploy.sh local all"
        echo
        exit 0
    fi
}

# Run tests
main "$@" 