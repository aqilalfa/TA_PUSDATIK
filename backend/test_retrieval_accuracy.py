from app.core.rag.langchain_engine import langchain_engine
import json
import sys

def test_retrieval():
    try:
        query = "jelaskan mengenai indikator ke 21 penilaian spbe"
        print(f"Testing Retrieval for: '{query}'")
        
        # Initialize engine
        print("Starting initialization...")
        success = langchain_engine.initialize()
        if not success:
            print("Initialization FAILED")
            return
        print("Initialization SUCCESS")
        
        # Run retrieval
        print("Running retrieval context...")
        result = langchain_engine.retrieve_context(query)
        
        print("\n--- RETRIEVAL RESULTS ---")
        print(f"Query Type: {result.get('query_type')}")
        sources = result.get('sources', [])
        print(f"Total Sources Found: {len(sources)}")
        
        for i, src in enumerate(sources, 1):
            print(f"\nSource [{i}]:")
            print(f"  Title: {src.get('document')}")
            print(f"  Section: {src.get('section')}")
            print(f"  Score: {src.get('score')}")
            
        if not sources:
            print("\nWARNING: No sources found. This confirms the accuracy issue is still present.")
        else:
            print("\nSUCCESS: Sources found with new modular engine.")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_retrieval()
