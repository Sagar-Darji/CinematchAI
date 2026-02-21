"""Deploy CineMatch AI to Hugging Face Spaces."""

import argparse
import shutil
import subprocess
from pathlib import Path

from huggingface_hub import HfApi

print("🎬 CineMatch AI - Hugging Face Spaces Deployment")
print("=" * 60)

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


def check_prerequisites():
    """Check if git and huggingface_hub are installed and authenticated."""
    print("\n📋 Checking prerequisites...")

    # Check git
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        print("✅ Git installed")
    except Exception:
        print("❌ Git not found. Please install git first.")
        return None

    # Check if logged in to HF
    try:
        api = HfApi()
        user_info = api.whoami()
        username = user_info["name"]
        print(f"✅ Logged in to Hugging Face as: {username}")
        return username
    except Exception:
        print("❌ Not logged in to Hugging Face.")
        print("\nPlease run: huggingface-cli login")
        return None


def prepare_deployment():
    """Prepare files for deployment."""
    print("\n📦 Preparing deployment files...")

    # Copy requirements
    src_req = PROJECT_ROOT / "requirements-hf.txt"
    if src_req.exists():
        shutil.copy(src_req, PROJECT_ROOT / "requirements.txt")
        print("✅ Copied requirements-hf.txt → requirements.txt")
    else:
        print("❌ requirements-hf.txt not found")
        return False

    # Copy README (contains HF Space metadata in frontmatter)
    src_readme = PROJECT_ROOT / "README_HF.md"
    if src_readme.exists():
        shutil.copy(src_readme, PROJECT_ROOT / "README.md")
        print("✅ Copied README_HF.md → README.md")
    else:
        print("❌ README_HF.md not found")
        return False

    # Check Dockerfile.spaces exists (used as the Docker build file for HF)
    if not (PROJECT_ROOT / "Dockerfile.spaces").exists():
        print("❌ Dockerfile.spaces not found")
        return False

    print("✅ Dockerfile.spaces ready")

    return True


def deploy_to_space(username: str, space_name: str):
    """Create Space and upload all files using HfApi."""
    repo_id = f"{username}/{space_name}"
    space_url = f"https://huggingface.co/spaces/{repo_id}"

    api = HfApi()

    # Step 1: Create the Space repo (README frontmatter defines sdk: docker)
    print(f"\n🚀 Creating/verifying HF Space: {repo_id}...")
    try:
        api.create_repo(
            repo_id=repo_id,
            repo_type="space",
            space_sdk="docker",
            exist_ok=True,
        )
        print(f"✅ Space ready: {space_url}")
    except Exception as e:
        # If streamlit SDK fails via API, upload README first to set it
        print(f"⚠️  API create with sdk failed ({e}), uploading README to configure...")
        try:
            api.create_repo(
                repo_id=repo_id,
                repo_type="space",
                space_sdk="static",
                exist_ok=True,
            )
            # Upload README with streamlit frontmatter to reconfigure
            api.upload_file(
                path_or_fileobj=str(PROJECT_ROOT / "README.md"),
                path_in_repo="README.md",
                repo_id=repo_id,
                repo_type="space",
            )
            print(f"✅ Space created and configured via README: {space_url}")
        except Exception as e2:
            print(f"⚠️  Space setup issue: {e2}")
            print("   Continuing with upload (space may already exist)...")

    # Step 2: Upload project files
    print(f"\n📤 Uploading files to {repo_id}...")

    # Define patterns to ignore during upload
    ignore_patterns = [
        "data/raw/*",
        "data/processed/*",
        "data/vectordb/*",
        "data/posters/*",
        "*.parquet",
        "logs/*",
        "*.log",
        ".env",
        ".env.local",
        ".git/*",
        ".claude/*",
        "__pycache__/*",
        "*.pyc",
        ".DS_Store",
        "evaluation/results/*",
        "cache/*",
        "*.zip",
        "*.npy",
        "venv/*",
        "ENV/*",
        "docs/*",
        "hf_upload/*",
        "tests/*",
        "*.db",
        ".streamlit/*",         # not needed for Docker SDK
        "app_hf.py",            # legacy Streamlit entry point, not used
        "Dockerfile",           # local docker-compose Dockerfile, not for HF
        "docker-compose.yml",   # local only
        "Makefile",             # local only
        "run_script.sh",        # local only
        "api.log",
        "ui.log",
        "README_HF.md",         # already copied to README.md by prepare_deployment()
    ]

    try:
        api.upload_folder(
            folder_path=str(PROJECT_ROOT),
            repo_id=repo_id,
            repo_type="space",
            ignore_patterns=ignore_patterns,
        )
        print(f"✅ Files uploaded to: {space_url}")
        return space_url

    except Exception as e:
        print(f"❌ Upload failed: {e}")
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
    parser = argparse.ArgumentParser(description="Deploy CineMatch AI to HF Spaces")
    parser.add_argument(
        "--space-name",
        default="cinematch-ai",
        help="HF Space name (default: cinematch-ai)",
    )
    args = parser.parse_args()

    space_name = args.space_name

    # Check prerequisites
    username = check_prerequisites()
    if not username:
        return

    print(f"\n📛 Space name: {space_name}")

    # Prepare files
    if not prepare_deployment():
        print("❌ Deployment preparation failed")
        return

    # Deploy
    space_url = deploy_to_space(username, space_name)

    if space_url:
        print_next_steps(space_url)
    else:
        print("\n❌ Deployment failed. Please check errors above.")


if __name__ == "__main__":
    main()
