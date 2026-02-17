#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy_spaces.sh — Deploy CinematchAI to HuggingFace Spaces
#
# Deploys the CURRENT working tree (including uncommitted changes) so you
# don't need to commit to main before deploying.
#
# What it does:
#   1. Builds the React frontend (dist/)
#   2. Creates a temporary orphan `spaces-deploy` branch with ALL current files
#   3. Adds Dockerfile.spaces as Dockerfile and pre-built React dist as /static
#   4. Force-pushes spaces-deploy → spaces/main
#   5. Switches back to original branch — nothing on main changes
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

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# ── 1. Build React frontend ───────────────────────────────────────────────────
echo ""
echo "📦 Building React frontend..."
cd frontend
npm ci --legacy-peer-deps --silent
VITE_API_URL="" npm run build
cd "$REPO_ROOT"
echo "✅ React build complete ($(du -sh frontend/dist | cut -f1) output)"

# ── 2. Create deploy snapshot ─────────────────────────────────────────────────
# Use a temp directory to avoid touching the working tree
echo ""
echo "📸 Creating deploy snapshot from current working tree..."

DEPLOY_DIR=$(mktemp -d)
trap 'rm -rf "$DEPLOY_DIR"' EXIT

# Copy all source files (respecting .gitignore via git ls-files + untracked)
# First: all tracked files (including modified/uncommitted)
git ls-files -z | xargs -0 -I{} sh -c 'mkdir -p "$1/$(dirname "$2")" && cp "$2" "$1/$2"' _ "$DEPLOY_DIR" {}

# Also copy untracked source files that matter
for dir in src config frontend/src frontend/public; do
  if [ -d "$dir" ]; then
    rsync -a --exclude='node_modules' --exclude='.git' "$dir/" "$DEPLOY_DIR/$dir/"
  fi
done

# Copy key config files
for f in setup.py pyproject.toml requirements.txt Dockerfile.spaces; do
  [ -f "$f" ] && cp "$f" "$DEPLOY_DIR/$f"
done

# Add pre-built React files
mkdir -p "$DEPLOY_DIR/static"
cp -r frontend/dist/. "$DEPLOY_DIR/static/"

# Use Dockerfile.spaces as the Dockerfile
cp "$DEPLOY_DIR/Dockerfile.spaces" "$DEPLOY_DIR/Dockerfile" 2>/dev/null || true

echo "✅ Snapshot ready ($(du -sh "$DEPLOY_DIR" | cut -f1))"

# ── 3. Build deploy commit ─────────────────────────────────────────────────────
echo ""
echo "🌿 Creating spaces-deploy branch..."

# Save current state
STASHED=0
if ! git diff --quiet || ! git diff --cached --quiet; then
  git stash push -m "deploy_spaces: auto-stash"
  STASHED=1
fi

# Create orphan branch (clean history — no bloat on HF)
git checkout --orphan spaces-deploy 2>/dev/null || git checkout -B spaces-deploy

# Remove everything from index
git rm -rf --cached . > /dev/null 2>&1 || true
git clean -fd > /dev/null 2>&1 || true

# Copy deploy snapshot into working tree
rsync -a "$DEPLOY_DIR/" .

# Stage everything
git add -A

COMMIT_MSG="deploy: CinematchAI React+FastAPI — $(date '+%Y-%m-%d %H:%M')"
git commit -m "$COMMIT_MSG" --allow-empty
echo "✅ Deploy commit: $COMMIT_MSG"

# ── 4. Push to HuggingFace Spaces ────────────────────────────────────────────
echo ""
echo "🚀 Pushing to HuggingFace Spaces..."

if [ -n "${HF_TOKEN:-}" ]; then
  SPACES_URL="https://sagardarji:${HF_TOKEN}@huggingface.co/spaces/sagardarji/cinematch-ai"
  git push "$SPACES_URL" spaces-deploy:main --force
else
  git push spaces spaces-deploy:main --force
fi
echo "✅ Pushed to spaces/main"

# ── 5. Return to original branch ─────────────────────────────────────────────
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
