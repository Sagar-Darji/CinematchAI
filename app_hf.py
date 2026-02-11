"""
Hugging Face Spaces Entry Point for CineMatch AI.

This file launches both the FastAPI backend and Streamlit frontend
optimized for HF Spaces deployment.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# Set environment for HF Spaces
os.environ["PYTHONPATH"] = str(Path(__file__).parent)
os.environ["HF_SPACES"] = "1"  # Flag to indicate running on HF Spaces

# Use Groq API instead of Ollama (not available on HF Spaces)
os.environ["USE_GROQ"] = "1"

print("🎬 Starting CineMatch AI on Hugging Face Spaces...")
print("=" * 60)

# Start FastAPI backend in background
print("🚀 Starting FastAPI backend...")
api_process = subprocess.Popen(
    [
        sys.executable,
        "-m",
        "uvicorn",
        "src.api.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "7860",  # HF Spaces default port
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Wait for API to start
print("⏳ Waiting for API to start...")
time.sleep(5)

# Check if API is running
try:
    import requests
    response = requests.get("http://localhost:7860/api/v1/health", timeout=5)
    if response.status_code == 200:
        print("✅ API backend started successfully!")
    else:
        print("⚠️  API backend may not be ready yet")
except Exception as e:
    print(f"⚠️  Could not verify API status: {e}")

# Start Streamlit frontend
print("🎨 Starting Streamlit frontend...")
print("=" * 60)

subprocess.run(
    [
        "streamlit",
        "run",
        "src/ui/app.py",
        "--server.port",
        "7860",
        "--server.address",
        "0.0.0.0",
        "--server.headless",
        "true",
        "--server.enableCORS",
        "false",
        "--server.enableXsrfProtection",
        "false",
    ]
)
