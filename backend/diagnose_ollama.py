import httpx
import json

def diagnose_ollama():
    url = "http://localhost:11434/api/chat"
    # Simulasi payload yang menyebabkan error
    payload = {
        "model": "qwen3.5:4b",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Tes koneksi. Balas dengan 'OK'."}
        ],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 2048},
        "think": False
    }
    
    print(f"Testing Ollama with payload: {json.dumps(payload, indent=2)}")
    try:
        resp = httpx.post(url, json=payload, timeout=30)
        print(f"Status Code: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    diagnose_ollama()
