"""Quick test to see if LLM can be loaded with current RAM."""

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 50)
print("Testing LLM Loading")
print("=" * 50)

model_path = (
    Path(__file__).parent / "models" / "llm" / "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
)
print(f"Model: {model_path.name}")
print(f"Exists: {model_path.exists()}")

if not model_path.exists():
    print("ERROR: Model file not found!")
    sys.exit(1)

print(f"Size: {model_path.stat().st_size / 1024 / 1024:.1f} MB")
print()

print("Loading llama-cpp-python with minimal settings...")
print("  n_ctx=512 (minimal context)")
print("  n_gpu_layers=0 (CPU only)")
print()

try:
    from llama_cpp import Llama

    print("Creating Llama instance...")
    llm = Llama(
        model_path=str(model_path),
        n_ctx=512,
        n_gpu_layers=0,
        verbose=True,
    )

    print("\n" + "=" * 50)
    print("SUCCESS! LLM loaded!")
    print("=" * 50)

    # Quick test
    print("\nTesting generation...")
    response = llm("SPBE adalah", max_tokens=20)
    print(f"Response: {response['choices'][0]['text']}")

except Exception as e:
    print(f"\nFAILED: {e}")
    print("\nRAM not sufficient. Options:")
    print("1. Close other applications")
    print("2. Use Ollama (better memory management)")
    print("3. Use smaller model (Qwen2.5-1.5B)")
    sys.exit(1)
