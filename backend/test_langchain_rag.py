import asyncio
import json
from loguru import logger
from app.core.rag.langchain_engine import langchain_engine

# Helper to print streaming Output Events from LCEL 
async def test_stream(question: str, session_id: str = "test-session-123"):
    logger.info(f"--- Q: {question} ---")
    
    chain = langchain_engine.get_chain("qwen2.5:3b") # Adjust to your local model
    config = {"configurable": {"session_id": session_id}}
    
    print("\n[Sources]: ", end="")
    
    # Intercept streaming events exactly as server.py
    async for event in chain.astream_events({"input": question}, config=config, version="v2"):
        kind = event["event"]
        name = event["name"]

        # 1. Document Extraction Stage
        if kind == "on_chain_end" and name == "retrieve_and_format":
            raw_docs = event["data"]["output"].get("raw_docs", [])
            for i, doc in enumerate(raw_docs, 1):
                meta = doc.metadata or {}
                doc_title = meta.get("judul_dokumen", "Unknown")
                hierarchy = meta.get("hierarchy_path", "")
                
                print(f"[{i}. {doc_title} - {hierarchy}] ", end="")
            print("\n[Answer]: ", end="")
            
        # 2. Token Streaming Stage
        elif kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if chunk.content:
                print(chunk.content, end="", flush=True)

    print("\n")


async def main():
    logger.info("Initializing LangChain RAG Test")
    
    # 1. First Question (Requires Retrieval)
    await test_stream("Apa itu Kebijakan Internal SPBE?")
    
    # 2. Second Question (Tests Memory)
    await test_stream("Sebutkan level 5 dari indikator tersebut!")

if __name__ == "__main__":
    asyncio.run(main())
