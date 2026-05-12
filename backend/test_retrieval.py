import sys
from pathlib import Path

# Add backend to path
backend_path = Path("d:/aqil/pusdatik/backend")
sys.path.append(str(backend_path))

from app.core.rag.langchain_engine import langchain_engine

def test_retrieval():
    print("=== TESTING RETRIEVAL ===")
    query = "jelaskan isi indikator ke 30 yang harus dipenuhi badan atau pemerintah untuk memenuhi oenilaian spbe?"
    result = langchain_engine.retrieve_context(query)
    
    print(f"Query: {query}")
    print(f"Query Type: {result.get('query_type')}")
    print(f"Found {len(result.get('sources', []))} sources")
    
    for i, source in enumerate(result.get('sources', []), 1):
        print(f"[{i}] Score: {source['score']:.4f} | {source['document_short']} | {source['section']}")
        # print(f"    Snippet: {source['snippet'][:100]}...")

if __name__ == "__main__":
    test_retrieval()
