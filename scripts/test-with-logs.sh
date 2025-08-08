#!/bin/bash

# Test runner with unified log tailing
# This script runs tests while monitoring logs for issues

set -e

# Configuration
CONTEXT="kind-ducklake-cluster"
LOKI_ADDR="http://localhost:3100"
BACKEND_ADDR="http://localhost:8000"
LOG_TAIL_DURATION=5  # seconds to tail logs after test completion

echo "🧪 Starting tests with unified log monitoring..."

# Ensure log setup is active
if ! curl -s "$LOKI_ADDR/ready" | grep -q "ready"; then
    echo "🔧 Setting up log access first..."
    ./setup-logs.sh
fi

# Function to tail logs during tests
tail_logs() {
    echo "📋 Tailing logs for $1 seconds..."
    timeout "$1" ./logs.sh tail-ducklake 2>/dev/null || true
}

# Function to check for errors in logs
check_for_errors() {
    echo "🔍 Checking for errors in logs..."
    local errors=$(./logs.sh errors 2>/dev/null | wc -l)
    local postgres_errors=$(./logs.sh postgres-errors 2>/dev/null | wc -l)
    
    if [ "$errors" -gt 0 ] || [ "$postgres_errors" -gt 0 ]; then
        echo "⚠️  Found $errors general error(s) and $postgres_errors PostgreSQL error(s) in logs:"
        if [ "$errors" -gt 0 ]; then
            echo "--- General Errors ---"
            ./logs.sh errors 2>/dev/null | head -5
        fi
        if [ "$postgres_errors" -gt 0 ]; then
            echo "--- PostgreSQL Errors ---"
            ./logs.sh postgres-errors 2>/dev/null | head -5
        fi
        return 1
    else
        echo "✅ No errors found in logs"
        return 0
    fi
}

# Function to check PostgreSQL health
check_postgres_health() {
    echo "🏥 Checking PostgreSQL health via logs..."
    ./monitor-postgres.sh health
}

# Function to verify backend health
check_backend_health() {
    echo "🏥 Checking backend health..."
    if curl -s "$BACKEND_ADDR/health" | grep -q "ok"; then
        echo "✅ Backend health check passed"
        return 0
    else
        echo "❌ Backend health check failed"
        return 1
    fi
}

# Main test execution
main() {
    echo "🎯 Running test suite with log monitoring..."
    
    # Check initial state
    check_backend_health || exit 1
    check_postgres_health
    
    # Start log tailing in background
    echo "📊 Starting log monitoring..."
    tail_logs 30 &
    LOG_PID=$!
    
    # Run tests (placeholder - add actual test commands here)
    echo "🧪 Running tests..."
    
    # Example: Basic API tests
    echo "  Testing health endpoint..."
    curl -s "$BACKEND_ADDR/health" > /dev/null
    
    echo "  Testing tables endpoint..."
    curl -s "$BACKEND_ADDR/tables" > /dev/null
    
    # Add more test commands here
    # pytest tests/ --verbose
    # python -m pytest tests/test_api.py
    
    # Stop log tailing
    kill $LOG_PID 2>/dev/null || true
    
    # Check for errors after tests
    sleep 1
    check_for_errors || {
        echo "❌ Tests may have caused errors. Check logs above."
        exit 1
    }
    
    echo "✅ All tests completed successfully!"
    echo "📊 Final log summary:"
    ./logs.sh ducklake 2>/dev/null | tail -5
}

# Cleanup function
cleanup() {
    echo "🧹 Cleaning up..."
    kill $LOG_PID 2>/dev/null || true
}

# Set up cleanup trap
trap cleanup EXIT

# Run main function
main "$@"