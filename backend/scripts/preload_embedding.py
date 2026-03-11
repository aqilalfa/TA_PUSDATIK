"""
Pre-load and test embedding model
Run this before starting the server to ensure model is cached
"""

import sys
import os
from pathlib import Path

# Set environment
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "0"  # Show progress
os.environ["TOKENIZERS_PARALLELISM"] = "false"

print("=" * 60)
print("SPBE RAG - Embedding Model Pre-loader")
print("=" * 60)

# Check cache dir
cache_dir = Path("D:/aqil/pusdatik/backend/models/embeddings")
local_model = cache_dir / "indo-sentence-bert-base"

print(f"\nCache directory: {cache_dir}")
print(f"Local model path: {local_model}")
print(f"Local model exists: {local_model.exists()}")

if local_model.exists():
    print(f"Model files: {list(local_model.glob('*'))[:5]}...")

print("\n[1] Loading SentenceTransformer...")

try:
    from sentence_transformers import SentenceTransformer

    if local_model.exists():
        print(f"Loading from LOCAL cache: {local_model}")
        model = SentenceTransformer(str(local_model), device="cpu")
    else:
        print(f"Downloading model: firqaaa/indo-sentence-bert-base")
        model = SentenceTransformer(
            "firqaaa/indo-sentence-bert-base", device="cpu", cache_folder=str(cache_dir)
        )

    print("Model loaded successfully!")

    print("\n[2] Testing embedding...")
    test_text = "Sistem Pemerintahan Berbasis Elektronik adalah sistem penyelenggaraan pemerintahan"
    embedding = model.encode(test_text)

    print(f"Input: {test_text[:50]}...")
    print(f"Embedding dimension: {len(embedding)}")
    print(f"Embedding sample: {embedding[:5]}")

    print("\n[3] Testing batch embedding...")
    texts = [
        "Apa itu SPBE?",
        "Domain arsitektur SPBE",
        "Pasal 8 tentang penyelenggaraan",
    ]
    embeddings = model.encode(texts)
    print(f"Batch size: {len(texts)}")
    print(f"Embeddings shape: {embeddings.shape}")

    print("\n" + "=" * 60)
    print("SUCCESS! Embedding model is ready.")
    print("You can now start the server with: start_backend.bat")
    print("=" * 60)

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
