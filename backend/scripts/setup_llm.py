"""
Setup and Test Script for SPBE RAG LLM

Run this after installing Ollama to complete the RAG setup.

Steps:
1. Install Ollama from https://ollama.ai (download installer)
2. Run Ollama (it starts as a service)
3. Pull model: ollama pull qwen2.5:7b
4. Run this script to test

Usage:
    cd D:\aqil\pusdatik\backend
    .\venv\Scripts\python scripts\setup_llm.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import time


def check_ollama() -> bool:
    """Check if Ollama is running."""
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False


def list_models() -> list:
    """List available Ollama models."""
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=10.0)
        if response.status_code == 200:
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        pass
    return []


def pull_model(model: str) -> bool:
    """Pull a model from Ollama."""
    print(f"Pulling model: {model}")
    print("This may take several minutes...")

    try:
        with httpx.Client(timeout=1800.0) as client:
            with client.stream(
                "POST",
                "http://localhost:11434/api/pull",
                json={"name": model},
            ) as response:
                import json

                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        status = data.get("status", "")
                        if "pulling" in status or "downloading" in status:
                            completed = data.get("completed", 0)
                            total = data.get("total", 0)
                            if total > 0:
                                pct = (completed / total) * 100
                                print(f"\r  {status}: {pct:.1f}%", end="", flush=True)
                        elif status:
                            print(f"\r  {status}          ")

                print()
                return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_generation(model: str) -> bool:
    """Test model generation."""
    print(f"\nTesting generation with {model}...")

    try:
        start = time.perf_counter()
        response = httpx.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": "Apa itu SPBE? Jawab singkat dalam 1 kalimat.",
                "stream": False,
                "options": {
                    "num_predict": 100,
                    "temperature": 0.1,
                },
            },
            timeout=120.0,
        )
        elapsed = time.perf_counter() - start

        if response.status_code == 200:
            text = response.json().get("response", "")
            print(f"Response ({elapsed:.1f}s):")
            print(f"  {text}")
            return True
        else:
            print(f"Error: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_rag():
    """Test full RAG pipeline."""
    print("\n" + "=" * 50)
    print("Testing Full RAG Pipeline")
    print("=" * 50)

    from app.core.rag.engine import RAGEngine

    engine = RAGEngine()

    print("\nInitializing RAG Engine...")
    if not engine.initialize(load_llm=True):
        print("ERROR: Failed to initialize RAG Engine")
        return False

    print("\nRAG Engine initialized!")
    print(f"LLM Info: {engine.llm.get_model_info()}")

    # Test query
    query = "Apa itu SPBE dan apa tujuannya?"
    print(f"\nQuery: {query}")
    print("-" * 50)

    result = engine.query(query, top_k=5, max_tokens=512)

    print(f"\nAnswer:")
    print(result.answer)

    print(f"\nSources ({len(result.sources)}):")
    for s in result.sources[:3]:
        print(f"  [{s['id']}] {s['document']}")

    print(f"\nMetrics:")
    print(f"  - Retrieval: {result.retrieval_time_ms:.1f}ms")
    print(f"  - Generation: {result.generation_time_ms:.1f}ms")
    print(f"  - Total: {result.total_time_ms:.1f}ms")

    return result.error is None


def main():
    print("=" * 50)
    print("SPBE RAG - LLM Setup & Test")
    print("=" * 50)

    model = "qwen2.5:7b"

    # Step 1: Check Ollama
    print("\n1. Checking Ollama...")
    if not check_ollama():
        print("   Ollama is NOT running!")
        print("\n   Please install Ollama:")
        print("   1. Download from https://ollama.ai")
        print("   2. Run the installer")
        print("   3. Ollama will start automatically")
        print("   4. Run this script again")
        return 1

    print("   Ollama is running!")

    # Step 2: Check model
    print(f"\n2. Checking model '{model}'...")
    models = list_models()
    print(f"   Available models: {models}")

    if not any(model in m for m in models):
        print(f"   Model '{model}' not found, pulling...")
        if not pull_model(model):
            print("   Failed to pull model!")
            return 1
    else:
        print(f"   Model '{model}' is available!")

    # Step 3: Test generation
    print("\n3. Testing LLM generation...")
    if not test_generation(model):
        print("   Generation test failed!")
        return 1

    print("   Generation test passed!")

    # Step 4: Test RAG
    print("\n4. Testing RAG pipeline...")
    if not test_rag():
        print("   RAG test failed!")
        return 1

    print("\n" + "=" * 50)
    print("All tests PASSED!")
    print("=" * 50)
    print("\nRAG system is ready to use!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
