import httpx
import json
import re

def test_api_stream_accuracy():
    url = "http://localhost:8000/api/chat/stream"
    payload = {
        "message": "jelaskan mengenai indikator ke 21 penilaian spbe",
        "session_id": None, # Will create new session
        "model": "qwen2.5:3b",
        "use_rag": True,
        "top_k": 5
    }
    
    print(f"Sending STREAM request to API: {url}")
    print(f"Message: {payload['message']}")
    
    try:
        # SSE needs to be read line by line
        with httpx.stream("POST", url, json=payload, timeout=120.0) as response:
            print(f"Status Code: {response.status_code}")
            if response.status_code != 200:
                # Handle potential redirect or error
                print(f"Error Status: {response.status_code}")
                return

            full_answer = ""
            current_event = None
            
            for line in response.iter_lines():
                if not line:
                    continue
                
                if line.startswith("event: "):
                    current_event = line[7:].strip()
                elif line.startswith("data: "):
                    data_str = line[6:].strip()
                    try:
                        data = json.loads(data_str)
                        
                        if current_event == "retrieval":
                            print(f"\n[RETRIEVAL] Found {data.get('count')} sources.")
                        
                        elif current_event == "token":
                            token = data.get("t", "")
                            print(token, end="", flush=True)
                            full_answer += token
                            
                        elif current_event == "complete":
                            print("\n\n[COMPLETE] Answer received.")
                            sources = data.get("sources", [])
                            print(f"Sources used: {len(sources)}")
                            for i, s in enumerate(sources, 1):
                                print(f"  [{i}] {s.get('document')} - {s.get('section')}")
                            
                        elif current_event == "error":
                            print(f"\n[ERROR] {data.get('error')}")
                            
                    except json.JSONDecodeError:
                        print(f"\n[RAW DATA] {data_str}")

            print("\n--- TEST COMPLETE ---")
            
    except Exception as e:
        print(f"\nRequest failed: {e}")

if __name__ == "__main__":
    test_api_stream_accuracy()
