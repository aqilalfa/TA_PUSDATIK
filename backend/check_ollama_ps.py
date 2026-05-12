import httpx
import json

def check_ps():
    try:
        resp = httpx.get("http://localhost:11434/api/ps")
        print(f"Loaded Models: {json.dumps(resp.json(), indent=2)}")
    except Exception as e:
        print(f"Failed to check PS: {e}")

if __name__ == "__main__":
    check_ps()
