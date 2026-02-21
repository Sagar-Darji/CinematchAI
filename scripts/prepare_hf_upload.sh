#!/usr/bin/env bash
# ============================================================
#  CineMatch AI — HuggingFace Upload Preparation
#  Zips all deployable data and guides vectordb upload
# ============================================================
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data"
UPLOAD_DIR="$PROJECT_ROOT/hf_upload"

echo ""
echo "🎬 CineMatch AI — HuggingFace Upload Prep"
echo "=========================================="
echo ""

# ── Create staging folder ──────────────────────────────────
mkdir -p "$UPLOAD_DIR"

# ── 1. Zip small data (raw + processed + SQLite DBs) ───────
echo "📦 Zipping raw data (~257 MB)..."
zip -r -q "$UPLOAD_DIR/data_raw.zip" "$DATA_DIR/raw/" && \
  echo "   ✅ data_raw.zip → $(du -sh "$UPLOAD_DIR/data_raw.zip" | cut -f1)"

echo "📦 Zipping processed data (~230 MB)..."
zip -r -q "$UPLOAD_DIR/data_processed.zip" "$DATA_DIR/processed/" && \
  echo "   ✅ data_processed.zip → $(du -sh "$UPLOAD_DIR/data_processed.zip" | cut -f1)"

echo "📦 Zipping SQLite databases..."
zip -q "$UPLOAD_DIR/data_databases.zip" \
  "$DATA_DIR"/*.db 2>/dev/null && \
  echo "   ✅ data_databases.zip → $(du -sh "$UPLOAD_DIR/data_databases.zip" | cut -f1)"

# ── 2. Zip vectordb (63 GB) ────────────────────────────────
echo ""
echo "🗄️  VectorDB is 63 GB — zipping (this will take 10–30 min)..."
echo "   (Press Ctrl+C to skip and upload to HF Datasets instead)"
echo ""
zip -r -q "$UPLOAD_DIR/data_vectordb.zip" "$DATA_DIR/vectordb/" --exclude '*.bak' && \
  echo "   ✅ data_vectordb.zip → $(du -sh "$UPLOAD_DIR/data_vectordb.zip" | cut -f1)"

echo ""
echo "✅ All archives ready in: $UPLOAD_DIR"
echo ""
echo "📁 Contents:"
ls -lh "$UPLOAD_DIR"
echo ""
echo "──────────────────────────────────────────────────────"
echo "🚀 NEXT: Upload to HuggingFace"
echo "──────────────────────────────────────────────────────"
echo ""
echo "  Option A — Upload as HF Dataset (Recommended for vectordb):"
echo "    python scripts/upload_vectordb_to_hf.py"
echo ""
echo "  Option B — Upload zip files via HF CLI:"
echo "    huggingface-cli upload YOUR_USERNAME/cinematch-ai hf_upload/ ."
echo ""
