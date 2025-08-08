#!/bin/bash
set -e

# Build script for DuckLake Backend

echo "🏗️  Building DuckLake Backend..."

# Set variables
IMAGE_NAME="ducklake-backend"
IMAGE_TAG="${1:-v1.0.2}"
FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"

# Color codes for better output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Build the Docker image
echo "Building Docker image: ${FULL_IMAGE_NAME}"
if docker build -t "${FULL_IMAGE_NAME}" .; then
    print_status "Docker image built successfully: ${FULL_IMAGE_NAME}"
else
    print_error "Failed to build Docker image"
    exit 1
fi

# Tag as latest
docker tag "${FULL_IMAGE_NAME}" "${IMAGE_NAME}:latest"
print_status "Tagged as latest: ${IMAGE_NAME}:latest"

# Show image info
echo ""
echo "📊 Image Information:"
docker images | grep "${IMAGE_NAME}" | head -2

echo ""
print_status "Build complete!"
echo "Image: ${FULL_IMAGE_NAME}"
echo "Latest: ${IMAGE_NAME}:latest"

# Optional: Push to registry (uncomment if needed)
echo ""
echo "💡 To push to registry, run:"
echo "   docker push ${FULL_IMAGE_NAME}"
echo "   docker push ${IMAGE_NAME}:latest"

echo ""
echo "🚀 To run locally:"
echo "   docker run -p 8000:8000 ${FULL_IMAGE_NAME}"
echo ""
echo "🐳 To run with docker-compose:"
echo "   docker-compose up --build" 