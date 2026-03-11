import json
from pprint import pprint
from app.core.ingestion.structured_chunker import chunk_document

def test_chunking(filepath):
    print(f"\n--- Testing Chunking for: {filepath} ---")
    with open(filepath, "r", encoding="utf-8") as f:
        doc = json.load(f)
        
    chunks = chunk_document(doc)
    print(f"Produced {len(chunks)} chunks.")
    
    # Just show the first 3 chunks and their lengths
    for i, c in enumerate(chunks[:3]):
        print(f"\nChunk {i+1} (Length: {len(c['text'])}):")
        print(c["text"][:200] + ("..." if len(c["text"]) > 200 else ""))
        print("Metadata:", c["metadata"])
        
    print("\n-------------------------------------------------\n")

if __name__ == "__main__":
    # Assuming there are parsed JSONs in data/parsed
    import glob
    parsed_files = glob.glob("data/parsed/*.json")
    if parsed_files:
        for f in parsed_files[:2]:
            test_chunking(f)
    else:
        print("No JSON files found in data/parsed/ to test.")
