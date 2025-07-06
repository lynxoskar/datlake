#!/bin/bash

# Local test script for Marimo notebook
# This script runs the Marimo notebook locally for testing

set -e

echo "🧪 Testing Marimo notebook locally..."

# Check if dependencies are installed
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Please run 'uv sync' first."
    exit 1
fi

# Set environment variables for local testing
export BACKEND_URL="http://localhost:8000"
export MARIMO_HOST="localhost"
export MARIMO_PORT="2718"

echo "🌐 Starting Marimo on http://localhost:2718"
echo "📝 Make sure your backend is running on http://localhost:8000"
echo "🔍 Press Ctrl+C to stop"

# Run the Marimo notebook
.venv/bin/marimo run marimo/test_data_generator.py --host localhost --port 2718 