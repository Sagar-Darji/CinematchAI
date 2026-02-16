#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy_spaces.sh — Deploy CinematchAI to HuggingFace Spaces
#
# What it does:
#   1. Builds the React frontend (dist/)
#   2. Creates a temporary `spaces-deploy` branch from main
#   3. On that branch: uses Dockerfile.spaces as Dockerfile and force-tracks
#      the pre-built React dist as /static (normally git-ignored)
#   4. Force-pushes spaces-deploy → spaces/main
#   5. Switches back to main — nothing on main changes
#
# Usage:
#   bash scripts/deploy_spaces.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "🎬 CinematchAI → HuggingFace Spaces deploy"
echo "============================================"

# ── Pre-flight checks ─────────────────────────────────────────────────────────
if ! git remote | grep -q "^spaces$"; then
  echo "❌ Remote 'spaces' not found. Add it with:"
  echo "   git remote add spaces https://huggingface.co/spaces/sagardarji/cinematch-ai"
  exit 1
fi

if [ ! -f "Dockerfile.spaces" ]; then
  echo "❌ Dockerfile.spaces not found"
  exit 1
fi

# ── 1. Build React frontend ───────────────────────────────────────────────────
echo ""
echo "📦 Building React frontend..."
cd frontend
npm ci --legacy-peer-deps --silent
VITE_API_URL="" npm run build
cd "$REPO_ROOT"
echo "✅ React build complete ($(du -sh frontend/dist | cut -f1) output)"

# ── 2. Stash any local changes on main ───────────────────────────────────────
STASHED=0
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo ""
  echo "📋 Stashing local changes..."
  git stash push -m "deploy_spaces: auto-stash"
  STASHED=1
fi

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# ── 3. Create spaces-deploy branch ───────────────────────────────────────────
echo ""
echo "🌿 Creating spaces-deploy branch from main..."
git checkout -B spaces-deploy main

# ── 4. Add pre-built React files ─────────────────────────────────────────────
echo "📁 Adding built React files to static/..."
rm -rf static
mkdir -p static
cp -r frontend/dist/. static/
git add -f static/   # -f to override .gitignore

# ── 5. Replace Dockerfile with spaces version ─────────────────────────────────
cp Dockerfile.spaces Dockerfile
git add Dockerfile

# ── 6. Commit ─────────────────────────────────────────────────────────────────
COMMIT_MSG="deploy: CinematchAI React+FastAPI — $(date '+%Y-%m-%d %H:%M')"
git commit -m "$COMMIT_MSG"
echo "✅ Deploy commit: $COMMIT_MSG"

# ── 7. Push to HuggingFace Spaces ────────────────────────────────────────────
echo ""
echo "🚀 Pushing to HuggingFace Spaces..."

# Auth: uses HF_TOKEN env var or git credential helper.
# Set your token once with:  export HF_TOKEN=hf_xxxxx
# Or run:                    huggingface-cli login
if [ -n "${HF_TOKEN:-}" ]; then
  SPACES_URL="https://sagardarji:${HF_TOKEN}@huggingface.co/spaces/sagardarji/cinematch-ai"
  git push "$SPACES_URL" spaces-deploy:main --force
else
  git push spaces spaces-deploy:main --force
fi
echo "✅ Pushed to spaces/main"

# ── 8. Return to original branch ─────────────────────────────────────────────
git checkout "$CURRENT_BRANCH"
if [ "$STASHED" -eq 1 ]; then
  git stash pop
  echo "📋 Restored stashed changes"
fi

echo ""
echo "🎉 Deployment complete!"
echo "   → https://huggingface.co/spaces/sagardarji/cinematch-ai"
echo ""
echo "⏳ HuggingFace will rebuild the Docker container (usually 5-10 min)."
echo "   Watch build logs at: https://huggingface.co/spaces/sagardarji/cinematch-ai/logs"
