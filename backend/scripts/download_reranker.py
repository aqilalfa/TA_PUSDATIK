"""
Download reranker model dari HuggingFace
Jalankan script ini SEKALI untuk download model

Usage:
    cd D:\aqil\pusdatik\backend
    python scripts\download_reranker.py

Model akan disimpan di: backend\models\reranker\
Ukuran: ~500MB
"""

import os
import sys
from pathlib import Path

# Cache directory
CACHE_DIR = Path(__file__).parent.parent / "models" / "reranker"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MODEL_NAME = "BAAI/bge-reranker-v2-m3"

print("=" * 60)
print("Download Reranker Model")
print("=" * 60)
print(f"\nModel: {MODEL_NAME}")
print(f"Cache: {CACHE_DIR}")
print(f"\nUkuran download: ~500MB")
print("Pastikan koneksi internet stabil.\n")

input("Tekan Enter untuk mulai download...")

print("\n[1] Downloading tokenizer...")
try:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        cache_dir=str(CACHE_DIR),
    )
    print("    Tokenizer: OK")
except Exception as e:
    print(f"    Tokenizer ERROR: {e}")
    sys.exit(1)

print("\n[2] Downloading model (ini akan memakan waktu)...")
try:
    from transformers import AutoModelForSequenceClassification

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        cache_dir=str(CACHE_DIR),
    )
    print("    Model: OK")
except Exception as e:
    print(f"    Model ERROR: {e}")
    sys.exit(1)

print("\n[3] Testing model...")
try:
    import torch

    pairs = [["Apa itu SPBE?", "SPBE adalah Sistem Pemerintahan Berbasis Elektronik"]]

    with torch.no_grad():
        inputs = tokenizer(
            pairs, padding=True, truncation=True, max_length=512, return_tensors="pt"
        )
        outputs = model(**inputs)
        score = outputs.logits.squeeze(-1).item()
        print(f"    Test score: {score:.4f}")
        print("    Model test: OK")
except Exception as e:
    print(f"    Test ERROR: {e}")

print("\n" + "=" * 60)
print("Download selesai!")
print("=" * 60)
print(f"\nModel tersimpan di: {CACHE_DIR}")
print("\nSekarang Anda bisa menjalankan server:")
print("  .\\start_full.bat")
