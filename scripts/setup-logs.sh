#!/bin/bash

# Setup script for log access during testing
# This script ensures port forwarding is active and Loki CLI is accessible

CONTEXT="kind-ducklake-cluster"
LOKI_PORT=3100
BACKEND_PORT=8000

echo "🔧 Setting up log access for testing..."

# Check if kubectl context exists
if ! kubectl config get-contexts | grep -q "$CONTEXT"; then
    echo "❌ Kubernetes context '$CONTEXT' not found. Please run 'make deploy-kind' first."
    exit 1
fi

# Check if Loki service is running
if ! kubectl --context "$CONTEXT" get svc loki > /dev/null 2>&1; then
    echo "❌ Loki service not found. Please run 'make deploy-kind' first."
    exit 1
fi

# Kill existing port forwards
echo "🧹 Cleaning up existing port forwards..."
pkill -f "kubectl.*port-forward.*loki" 2>/dev/null || true
pkill -f "kubectl.*port-forward.*ducklake-backend" 2>/dev/null || true

# Set up port forwarding
echo "🔌 Setting up port forwarding..."
kubectl --context "$CONTEXT" port-forward svc/loki $LOKI_PORT:3100 > /dev/null 2>&1 &
LOKI_PID=$!

kubectl --context "$CONTEXT" port-forward svc/ducklake-backend-service $BACKEND_PORT:80 > /dev/null 2>&1 &
BACKEND_PID=$!

# Wait for port forwards to be established
sleep 2

# Verify port forwarding is working
echo "🔍 Verifying log access..."
if curl -s "http://localhost:$LOKI_PORT/ready" | grep -q "ready"; then
    echo "✅ Loki is accessible on port $LOKI_PORT"
else
    echo "❌ Loki is not accessible. Check port forwarding."
    exit 1
fi

if curl -s "http://localhost:$BACKEND_PORT/health" | grep -q "ok"; then
    echo "✅ Backend is accessible on port $BACKEND_PORT"
else
    echo "❌ Backend is not accessible. Check port forwarding."
    exit 1
fi

# Test Loki CLI
echo "🧪 Testing Loki CLI access..."
export LOKI_ADDR="http://localhost:$LOKI_PORT"
export PATH="$HOME/bin:$PATH"

if logcli labels > /dev/null 2>&1; then
    echo "✅ Loki CLI is working"
else
    echo "❌ Loki CLI is not working. Check installation."
    exit 1
fi

echo "🎉 Log access setup complete!"
echo "📊 Available log commands:"
echo "  ./logs.sh tail-ducklake  # Tail backend logs"
echo "  ./logs.sh errors         # Show error logs"
echo "  ./logs.sh labels         # Show available labels"
echo ""
echo "🔗 Port forwards (background processes):"
echo "  Loki: localhost:$LOKI_PORT (PID: $LOKI_PID)"
echo "  Backend: localhost:$BACKEND_PORT (PID: $BACKEND_PID)"
echo ""
echo "To stop port forwarding: pkill -f 'kubectl.*port-forward'"