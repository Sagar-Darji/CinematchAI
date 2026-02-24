"""
Hugging Face Spaces Entry Point for CineMatch AI.

This file launches the FastAPI backend on HF Spaces (port 7860).
Frontend is served as static React build from /app/static.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Set environment for HF Spaces
os.environ["PYTHONPATH"] = str(Path(__file__).parent)
os.environ["HF_SPACES"] = "1"
os.environ["USE_GROQ"] = "1"

print("🎬 Starting CineMatch AI on Hugging Face Spaces...")
print("=" * 60)

# Start FastAPI backend (serves React build from /app/static at /)
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
        "7860",
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

def _shutdown(signum=None, frame=None):
    if api_process.poll() is None:
        api_process.terminate()
        try:
            api_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api_process.kill()
    sys.exit(0)

signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)

print("⏳ Waiting for API to start...")
time.sleep(5)

try:
    import requests
    response = requests.get("http://localhost:7860/api/v1/health", timeout=5)
    if response.status_code == 200:
        print("✅ API backend started successfully!")
    else:
        print("⚠️  API backend may not be ready yet")
except Exception as e:
    print(f"⚠️  Could not verify API status: {e}")

print("=" * 60)
print("🎬 CineMatch AI running at http://localhost:7860")

# Keep alive
api_process.wait()

