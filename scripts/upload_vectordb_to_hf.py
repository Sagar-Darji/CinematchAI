"""
Upload CineMatch AI VectorDB to HuggingFace Datasets Hub.

The vectordb (63GB) is too large for a Space git repo.
This script uploads it as a Dataset, then the app downloads
it on first startup automatically.

Usage:
    python scripts/upload_vectordb_to_hf.py --username YOUR_HF_USERNAME
"""

import argparse
import zipfile
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

PROJECT_ROOT = Path(__file__).parent.parent
VECTORDB_DIR = PROJECT_ROOT / "data" / "vectordb"
UPLOAD_DIR = PROJECT_ROOT / "hf_upload"


def upload_vectordb(username: str, repo_name: str = "cinematch-vectordb"):
    api = HfApi()

    # Verify login
    try:
        user = api.whoami()
        print(f"✅ Logged in as: {user['name']}")
    except Exception:
        print("❌ Not logged in. Run: huggingface-cli login")
        return

    # Create dataset repo
    repo_id = f"{username}/{repo_name}"
    print(f"\n📦 Creating HF Dataset: {repo_id}")
    api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True, private=False)
    print(f"   ✅ Repo ready: https://huggingface.co/datasets/{repo_id}")

    # Zip vectordb if not already done
    zip_path = UPLOAD_DIR / "data_vectordb.zip"
    if not zip_path.exists():
        print("\n🗜️  Zipping vectordb (63 GB, this takes ~20 min)...")
        UPLOAD_DIR.mkdir(exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
            for file in VECTORDB_DIR.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(VECTORDB_DIR.parent))
        print(f"   ✅ Zipped → {zip_path} ({zip_path.stat().st_size / 1e9:.1f} GB)")
    else:
        print(f"   ✅ Using existing zip: {zip_path}")

    # Upload to HF Dataset
    print(f"\n⬆️  Uploading to HF Datasets Hub...")
    print("   (Large file — will take time depending on connection speed)")
    api.upload_file(
        path_or_fileobj=str(zip_path),
        path_in_repo="data_vectordb.zip",
        repo_id=repo_id,
        repo_type="dataset",
    )
    print(f"\n✅ VectorDB uploaded!")
    print(f"   URL: https://huggingface.co/datasets/{repo_id}")
    print(f"\n📝 Add this to your .env or HF Space secrets:")
    print(f"   HF_VECTORDB_DATASET={repo_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True, help="Your HuggingFace username")
    parser.add_argument("--repo", default="cinematch-vectordb", help="Dataset repo name")
    args = parser.parse_args()
    upload_vectordb(args.username, args.repo)
