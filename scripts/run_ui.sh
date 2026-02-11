#!/bin/bash
# Script to run the CineMatch AI Streamlit UI

set -e

# Set PYTHONPATH
export PYTHONPATH="/Users/sagardarji/CinematchAI:$PYTHONPATH"

echo "🎬 Starting CineMatch AI Streamlit UI..."
echo "================================================"
echo "UI will be available at: http://localhost:8501"
echo "================================================"
echo ""
echo "⚠️  Make sure the API server is running first!"
echo "   (Run: ./scripts/run_api.sh in another terminal)"
echo ""

# Run Streamlit
cd /Users/sagardarji/CinematchAI
streamlit run src/ui/app.py \
    --server.port 8501 \
    --server.address localhost \
    --theme.base light
