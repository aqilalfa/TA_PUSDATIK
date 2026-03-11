#!/usr/bin/env python3
"""
Auto-download all required models for SPBE RAG system
"""

import os
import sys
from pathlib import Path
from huggingface_hub import hf_hub_download, snapshot_download
from loguru import logger

# Model configurations
MODELS = {
    "llm": {
        "repo_id": "bartowski/Qwen2.5-7B-Instruct-GGUF",
        "filename": "Qwen2.5-7B-Instruct-Q4_K_M.gguf",  # ~4.37 GB, optimal for GTX 1650 4GB
        "local_dir": "models/llm",
        "type": "single_file",
    },
    "embedding": {
        "repo_id": "firqaaa/indo-sentence-bert-base",
        "local_dir": "models/embeddings/indo-sentence-bert-base",
        "type": "snapshot",
    },
    "reranker": {
        "repo_id": "BAAI/bge-reranker-base",
        "local_dir": "models/reranker/bge-reranker-base",
        "type": "snapshot",
    },
}


def setup_logging():
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )

    # Create logs directory if not exists
    Path("logs").mkdir(exist_ok=True)
    logger.add("logs/download_models.log", rotation="10 MB", encoding="utf-8")


def check_model_exists(model_config):
    """Check if model already exists locally"""
    local_dir = Path(model_config["local_dir"])

    if model_config["type"] == "single_file":
        model_path = local_dir / model_config["filename"]
        return model_path.exists()
    else:
        # For snapshot, check if directory exists and has files
        return local_dir.exists() and any(local_dir.iterdir())


def download_single_file(model_config):
    """Download single model file"""
    logger.info(f"[DOWNLOAD] {model_config['repo_id']} ({model_config['filename']})...")

    local_dir = Path(model_config["local_dir"])
    local_dir.mkdir(parents=True, exist_ok=True)

    try:
        filepath = hf_hub_download(
            repo_id=model_config["repo_id"],
            filename=model_config["filename"],
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
        )
        logger.success(f"[OK] Downloaded to: {filepath}")
        return True
    except Exception as e:
        logger.error(f"[ERROR] Failed to download: {e}")
        return False


def download_snapshot(model_config):
    """Download entire model repository"""
    logger.info(f"[DOWNLOAD] {model_config['repo_id']} (full repository)...")

    local_dir = Path(model_config["local_dir"])
    local_dir.mkdir(parents=True, exist_ok=True)

    try:
        snapshot_download(
            repo_id=model_config["repo_id"],
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
        )
        logger.success(f"[OK] Downloaded to: {local_dir}")
        return True
    except Exception as e:
        logger.error(f"[ERROR] Failed to download: {e}")
        return False


def download_models(force=False):
    """Download all required models"""
    logger.info("[START] Starting model download process...")
    logger.info("=" * 60)

    for model_name, model_config in MODELS.items():
        logger.info(f"\n[MODEL] Processing: {model_name.upper()}")
        logger.info("-" * 60)

        # Check if already exists
        if not force and check_model_exists(model_config):
            logger.info(f"[OK] Model already exists: {model_config['local_dir']}")
            logger.info("  Skipping download. Use --force to re-download.")
            continue

        # Download based on type
        if model_config["type"] == "single_file":
            success = download_single_file(model_config)
        else:
            success = download_snapshot(model_config)

        if not success:
            logger.error(f"[ERROR] Failed to download {model_name}")
            return False

    logger.success("\n" + "=" * 60)
    logger.success("[SUCCESS] All models downloaded successfully!")
    logger.success("=" * 60)

    # Print summary
    logger.info("\n[SUMMARY] Model Summary:")
    logger.info(f"  - LLM: models/llm/Qwen2.5-7B-Instruct-Q4_K_M.gguf (~4.37 GB)")
    logger.info(f"  - Embedding: models/embeddings/indo-sentence-bert-base/ (~400 MB)")
    logger.info(f"  - Reranker: models/reranker/bge-reranker-base/ (~1 GB)")
    logger.info(f"\n  Total size: ~6-7 GB")

    return True


def verify_models():
    """Verify all models are present and valid"""
    logger.info("\n[VERIFY] Verifying models...")
    logger.info("-" * 60)

    all_present = True

    for model_name, model_config in MODELS.items():
        exists = check_model_exists(model_config)
        status = "[OK]" if exists else "[MISSING]"
        status_text = "Present" if exists else "Missing"
        logger.info(
            f"  {status} {model_name.upper():<12} : {status_text:<10} ({model_config['local_dir']})"
        )

        if not exists:
            all_present = False

    logger.info("-" * 60)

    return all_present


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Download models for SPBE RAG system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all models
  python download_models.py
  
  # Force re-download even if exists
  python download_models.py --force
  
  # Only verify without downloading
  python download_models.py --verify
        """,
    )
    parser.add_argument(
        "--force", action="store_true", help="Force re-download even if models exist"
    )
    parser.add_argument(
        "--verify", action="store_true", help="Only verify models without downloading"
    )
    args = parser.parse_args()

    setup_logging()

    # Create models directory
    Path("models").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)

    logger.info("=" * 60)
    logger.info("  SPBE RAG System - Model Downloader")
    logger.info("=" * 60)

    if args.verify:
        if verify_models():
            logger.success("\n[OK] All models are present!")
            sys.exit(0)
        else:
            logger.error(
                "\n[ERROR] Some models are missing. Run without --verify to download."
            )
            sys.exit(1)
    else:
        if download_models(force=args.force):
            verify_models()
            logger.success("\n[SUCCESS] Model download completed successfully!")
            logger.info("\n[NEXT STEPS]:")
            logger.info("  1. Copy .env.example to .env")
            logger.info("  2. Configure .env if needed")
            logger.info("  3. Run: docker-compose -f docker-compose.dev.yml up --build")
            sys.exit(0)
        else:
            logger.error("\n[ERROR] Model download failed!")
            sys.exit(1)
