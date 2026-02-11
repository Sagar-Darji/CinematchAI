"""Deploy CineMatch AI to Hugging Face Spaces."""

import os
import shutil
import subprocess
from pathlib import Path

print("🎬 CineMatch AI - Hugging Face Spaces Deployment")
print("=" * 60)

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

def check_prerequisites():
    """Check if git and huggingface_hub are installed."""
    print("\n📋 Checking prerequisites...")

    # Check git
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        print("✅ Git installed")
    except:
        print("❌ Git not found. Please install git first.")
        return False

    # Check if logged in to HF
    try:
        result = subprocess.run(
            ["huggingface-cli", "whoami"],
            check=True,
            capture_output=True,
            text=True
        )
        username = result.stdout.strip()
        print(f"✅ Logged in to Hugging Face as: {username}")
        return True
    except:
        print("❌ Not logged in to Hugging Face.")
        print("\nPlease run: huggingface-cli login")
        return False


def prepare_deployment():
    """Prepare files for deployment."""
    print("\n📦 Preparing deployment files...")

    # Copy requirements
    shutil.copy(
        PROJECT_ROOT / "requirements-hf.txt",
        PROJECT_ROOT / "requirements.txt"
    )
    print("✅ Copied requirements-hf.txt → requirements.txt")

    # Copy README
    shutil.copy(
        PROJECT_ROOT / "README_HF.md",
        PROJECT_ROOT / "README.md"
    )
    print("✅ Copied README_HF.md → README.md")

    # Ensure .streamlit config exists
    streamlit_dir = PROJECT_ROOT / ".streamlit"
    if not streamlit_dir.exists():
        print("❌ .streamlit/config.toml not found")
        return False

    print("✅ .streamlit/config.toml ready")

    # Check if app_hf.py exists
    if not (PROJECT_ROOT / "app_hf.py").exists():
        print("❌ app_hf.py not found")
        return False

    print("✅ app_hf.py ready")

    return True


def create_gitignore():
    """Create .gitignore for HF Spaces."""
    print("\n📝 Creating .gitignore...")

    gitignore_content = """
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
ENV/

# Data (too large for HF Spaces)
data/raw/
data/processed/*.csv
data/processed/*.parquet

# Embeddings (will be generated on-the-fly or cached)
# Keep small test embeddings only

# Vector DB (will be rebuilt)
data/vectordb/

# Logs
logs/
*.log

# Environment
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Build
dist/
build/
*.egg-info/

# Evaluation results
evaluation/results/
"""

    with open(PROJECT_ROOT / ".gitignore", "w") as f:
        f.write(gitignore_content.strip())

    print("✅ .gitignore created")


def create_space_repo(space_name: str):
    """Create Hugging Face Space repository."""
    print(f"\n🚀 Creating HF Space: {space_name}...")

    try:
        # Get username
        result = subprocess.run(
            ["huggingface-cli", "whoami"],
            check=True,
            capture_output=True,
            text=True
        )
        username = result.stdout.strip().split()[0]

        # Create space
        subprocess.run(
            [
                "huggingface-cli",
                "repo",
                "create",
                space_name,
                "--type",
                "space",
                "--space_sdk",
                "streamlit",
            ],
            check=True,
        )

        space_url = f"https://huggingface.co/spaces/{username}/{space_name}"
        print(f"✅ Space created: {space_url}")

        return space_url

    except subprocess.CalledProcessError as e:
        print(f"⚠️  Space may already exist or creation failed: {e}")
        return None


def push_to_space(space_name: str):
    """Push code to HF Space."""
    print(f"\n📤 Pushing to HF Space: {space_name}...")

    try:
        # Get username
        result = subprocess.run(
            ["huggingface-cli", "whoami"],
            check=True,
            capture_output=True,
            text=True
        )
        username = result.stdout.strip().split()[0]

        space_url = f"https://huggingface.co/spaces/{username}/{space_name}"

        # Initialize git if needed
        if not (PROJECT_ROOT / ".git").exists():
            subprocess.run(["git", "init"], cwd=PROJECT_ROOT, check=True)
            subprocess.run(
                ["git", "add", "."],
                cwd=PROJECT_ROOT,
                check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit for HF Spaces"],
                cwd=PROJECT_ROOT,
                check=True
            )

        # Add HF remote
        subprocess.run(
            ["git", "remote", "add", "spaces", f"https://huggingface.co/spaces/{username}/{space_name}"],
            cwd=PROJECT_ROOT,
            capture_output=True
        )

        # Push
        subprocess.run(
            ["git", "push", "spaces", "main", "--force"],
            cwd=PROJECT_ROOT,
            check=True
        )

        print(f"✅ Pushed to: {space_url}")
        return space_url

    except subprocess.CalledProcessError as e:
        print(f"❌ Push failed: {e}")
        return None


def print_next_steps(space_url: str):
    """Print next steps for user."""
    print("\n" + "=" * 60)
    print("🎉 Deployment Initiated!")
    print("=" * 60)

    print(f"\n📍 Your Space: {space_url}")

    print("\n📝 Next Steps:")
    print("\n1. Add Secrets in Space Settings:")
    print("   - GROQ_API_KEY (required)")
    print("   - TMDB_API_KEY (optional)")

    print("\n2. Wait for Build (may take 5-10 minutes)")
    print("   - Check build logs in Space settings")

    print("\n3. Test Your Space:")
    print("   - Click 'App' tab to view running app")
    print("   - Complete onboarding flow")
    print("   - Get recommendations")

    print("\n4. Share Your Space:")
    print(f"   - Direct link: {space_url}")
    print("   - Add to your portfolio/resume")

    print("\n⚠️  Important Notes:")
    print("   - Free tier has 16GB RAM limit")
    print("   - Cold start may take 30-60 seconds")
    print("   - Groq API has rate limits (30 req/min)")

    print("\n" + "=" * 60)


def main():
    """Main deployment flow."""

    # Check prerequisites
    if not check_prerequisites():
        return

    # Get space name
    print("\n📛 Enter Space name (e.g., cinematch-ai):")
    space_name = input("> ").strip()

    if not space_name:
        print("❌ Space name required")
        return

    # Prepare files
    if not prepare_deployment():
        print("❌ Deployment preparation failed")
        return

    # Create .gitignore
    create_gitignore()

    # Create space
    space_url = create_space_repo(space_name)

    if not space_url:
        print("\nSpace may already exist. Continuing with push...")
        result = subprocess.run(
            ["huggingface-cli", "whoami"],
            capture_output=True,
            text=True
        )
        username = result.stdout.strip().split()[0]
        space_url = f"https://huggingface.co/spaces/{username}/{space_name}"

    # Push code
    final_url = push_to_space(space_name)

    if final_url:
        print_next_steps(final_url)
    else:
        print("\n❌ Deployment failed. Please check errors above.")


if __name__ == "__main__":
    main()
