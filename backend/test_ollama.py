"""Test Ollama connection and generation."""

import httpx
import time

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen3:8b"

print("=" * 50)
print("Testing Ollama Connection")
print("=" * 50)

# 1. Check if Ollama is running
print("\n1. Checking Ollama status...")
try:
    response = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
    if response.status_code == 200:
        models = [m["name"] for m in response.json().get("models", [])]
        print(f"   Ollama running. Models: {models}")
    else:
        print(f"   Ollama error: {response.status_code}")
except Exception as e:
    print(f"   Ollama not running: {e}")
    exit(1)

# 2. Check loaded models
print("\n2. Checking loaded models...")
response = httpx.get(f"{OLLAMA_URL}/api/ps", timeout=5.0)
loaded = response.json().get("models", [])
if loaded:
    print(f"   Loaded models: {[m['name'] for m in loaded]}")
else:
    print("   No models currently loaded (will load on first request)")

# 3. Test generation
print(f"\n3. Testing generation with {MODEL}...")
print("   (This may take 30-60 seconds on first call)")

start = time.time()
try:
    response = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": MODEL,
            "prompt": "Apa itu SPBE? Jawab dalam 2 kalimat bahasa Indonesia.",
            "stream": False,
            "options": {
                "num_predict": 150,
                "temperature": 0.7,
            },
        },
        timeout=120.0,
    )

    elapsed = time.time() - start
    print(f"   Time: {elapsed:.1f}s")
    print(f"   Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        answer = data.get("response", "")
        print(f"\n   Response ({len(answer)} chars):")
        print(f"   {answer[:500]}")

        if not answer:
            print("\n   WARNING: Empty response!")
            print(f"   Full response: {data}")
    else:
        print(f"   Error: {response.text}")

except httpx.TimeoutException:
    print("   TIMEOUT after 120 seconds")
except Exception as e:
    print(f"   Error: {e}")

# 4. Check loaded models after generation
print("\n4. Checking loaded models after generation...")
response = httpx.get(f"{OLLAMA_URL}/api/ps", timeout=5.0)
loaded = response.json().get("models", [])
if loaded:
    for m in loaded:
        print(f"   - {m['name']}: {m.get('size_vram', 0) / 1e9:.1f}GB VRAM")
else:
    print("   No models loaded (something went wrong)")

print("\n" + "=" * 50)
print("Test complete")
print("=" * 50)
