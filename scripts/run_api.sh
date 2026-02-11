#!/bin/bash
# Script to run the CineMatch AI FastAPI server

set -e

# Set PYTHONPATH
export PYTHONPATH="/Users/sagardarji/CinematchAI:$PYTHONPATH"

echo "🚀 Starting CineMatch AI API Server..."
echo "================================================"
echo "API Documentation: http://localhost:8000/docs"
echo "Health Check: http://localhost:8000/api/v1/health"
echo "================================================"
echo ""

# Run uvicorn server
uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level info
