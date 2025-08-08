#!/bin/bash

# Test script for Docker registry functionality
# Tests registry health, image operations, and API endpoints

set -e

REGISTRY_HOST="localhost:5000"
IMAGE_NAME="ducklake-backend"
IMAGE_TAG="latest"
TEST_IMAGE="$REGISTRY_HOST/$IMAGE_NAME:$IMAGE_TAG"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Test 1: Registry Health Check
test_registry_health() {
    log_info "Testing registry health..."
    
    if curl -s -f "http://$REGISTRY_HOST/v2/" > /dev/null; then
        log_success "Registry is healthy and responding"
        return 0
    else
        log_error "Registry health check failed"
        return 1
    fi
}

# Test 2: Registry API Catalog
test_registry_catalog() {
    log_info "Testing registry catalog API..."
    
    local catalog_response
    catalog_response=$(curl -s "http://$REGISTRY_HOST/v2/_catalog" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        log_success "Registry catalog API is working"
        echo "Catalog response: $catalog_response"
        return 0
    else
        log_error "Registry catalog API failed"
        return 1
    fi
}

# Test 3: Image Operations
test_image_operations() {
    log_info "Testing image operations..."
    
    # Build a simple test image
    log_info "Building test image..."
    cat > /tmp/test_dockerfile << 'EOF'
FROM alpine:latest
RUN echo "Test image for registry" > /test.txt
CMD ["cat", "/test.txt"]
EOF
    
    if docker build -t "$TEST_IMAGE" -f /tmp/test_dockerfile /tmp/; then
        log_success "Test image built successfully"
    else
        log_error "Failed to build test image"
        return 1
    fi
    
    # Push image to registry
    log_info "Pushing test image to registry..."
    if docker push "$TEST_IMAGE"; then
        log_success "Test image pushed successfully"
    else
        log_error "Failed to push test image"
        return 1
    fi
    
    # Remove local image
    log_info "Removing local test image..."
    docker rmi "$TEST_IMAGE" || true
    
    # Pull image from registry
    log_info "Pulling test image from registry..."
    if docker pull "$TEST_IMAGE"; then
        log_success "Test image pulled successfully"
    else
        log_error "Failed to pull test image"
        return 1
    fi
    
    # Test running the image
    log_info "Testing pulled image..."
    if docker run --rm "$TEST_IMAGE" | grep -q "Test image for registry"; then
        log_success "Pulled image works correctly"
    else
        log_error "Pulled image test failed"
        return 1
    fi
    
    # Cleanup
    docker rmi "$TEST_IMAGE" || true
    rm -f /tmp/test_dockerfile
    
    return 0
}

# Test 4: Registry Tags API
test_registry_tags() {
    log_info "Testing registry tags API..."
    
    local tags_response
    tags_response=$(curl -s "http://$REGISTRY_HOST/v2/$IMAGE_NAME/tags/list" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        log_success "Registry tags API is working"
        echo "Tags response: $tags_response"
        return 0
    else
        log_warning "Registry tags API failed (might be empty)"
        return 0  # Not critical for registry functionality
    fi
}

# Test 5: Registry Storage Check
test_registry_storage() {
    log_info "Checking registry storage..."
    
    # Check if we can access the registry pod
    local registry_pod
    registry_pod=$(kubectl get pods -n storage -l app=docker-registry -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -n "$registry_pod" ]; then
        log_success "Registry pod found: $registry_pod"
        
        # Check storage usage
        local storage_info
        storage_info=$(kubectl exec -n storage "$registry_pod" -- df -h /var/lib/registry 2>/dev/null)
        
        if [ $? -eq 0 ]; then
            log_success "Registry storage is accessible"
            echo "Storage info:"
            echo "$storage_info"
        else
            log_warning "Could not access registry storage info"
        fi
    else
        log_error "Registry pod not found"
        return 1
    fi
    
    return 0
}

# Test 6: Registry Performance
test_registry_performance() {
    log_info "Testing registry performance..."
    
    local start_time
    local end_time
    local duration
    
    start_time=$(date +%s.%N)
    
    # Test API response time
    if curl -s -w "%{time_total}" -o /dev/null "http://$REGISTRY_HOST/v2/" > /tmp/response_time.txt; then
        end_time=$(date +%s.%N)
        duration=$(awk '{print $1 - $2}' <<< "$end_time $start_time")
        
        local response_time
        response_time=$(cat /tmp/response_time.txt)
        
        log_success "Registry performance test completed"
        printf "Response time: %.3f seconds\n" "$response_time"
        
        if awk 'BEGIN{exit !('$response_time' < 1.0)}'; then
            log_success "Registry response time is good (< 1s)"
        else
            log_warning "Registry response time is slow (> 1s)"
        fi
    else
        log_error "Registry performance test failed"
        return 1
    fi
    
    rm -f /tmp/response_time.txt
    return 0
}

# Main test execution
main() {
    echo "=================================="
    echo "Docker Registry Test Suite"
    echo "=================================="
    echo ""
    
    local tests_passed=0
    local tests_total=6
    
    # Run all tests
    if test_registry_health; then
        ((tests_passed++))
    fi
    echo ""
    
    if test_registry_catalog; then
        ((tests_passed++))
    fi
    echo ""
    
    if test_registry_tags; then
        ((tests_passed++))
    fi
    echo ""
    
    if test_registry_storage; then
        ((tests_passed++))
    fi
    echo ""
    
    if test_registry_performance; then
        ((tests_passed++))
    fi
    echo ""
    
    if test_image_operations; then
        ((tests_passed++))
    fi
    echo ""
    
    # Summary
    echo "=================================="
    echo "Test Results Summary"
    echo "=================================="
    echo "Tests passed: $tests_passed/$tests_total"
    
    if [ $tests_passed -eq $tests_total ]; then
        log_success "All tests passed! Docker registry is fully functional."
        exit 0
    else
        log_error "Some tests failed. Please check the registry configuration."
        exit 1
    fi
}

# Run tests
main "$@" 