import httpx
import json

def diagnose_ollama():
    url = "http://localhost:11434/api/chat"
    # Testing with 3b which is safer for 4GB VRAM
    payload = {
        "model": "qwen2.5:3b",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "OK?"}
        ],
        "stream": False,
        "options": {
            "temperature": 0.1, 
            "num_predict": 1024,
            "num_ctx": 4096
        }
    }
    
    print(f"Testing Ollama with 3b: {json.dumps(payload, indent=2)}")
    try:
        resp = httpx.post(url, json=payload, timeout=60)
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            print(f"Response: {resp.json().get('message', {}).get('content')}")
        else:
            print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    diagnose_ollama()
