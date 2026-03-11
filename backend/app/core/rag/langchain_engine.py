"""
LangChain RAG Engine - Main Orchestrator for SPBE RAG System
Replaces the legacy RAG engine with LangChain v0.2.x+ LCEL and memory integration.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger
import json

from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.documents import Document

from app.database import SessionLocal
from app.models.db_models import Conversation
from app.core.rag.prompts import SYSTEM_PROMPT_SPBE

# In-memory history cache for RunnableWithMessageHistory
# In production, this should ideally be tied to a Redis/SQLite backend directly.
from langchain_community.chat_message_histories import ChatMessageHistory
_session_store = {}

def get_session_history(session_id: str) -> ChatMessageHistory:
    """Get or create chat history for a session."""
    if session_id not in _session_store:
        history = ChatMessageHistory()
        
        # Load from SQLAlchemy database
        try:
            with SessionLocal() as db:
                messages = (
                    db.query(Conversation)
                    .filter(Conversation.session_id == session_id)
                    .order_by(Conversation.timestamp.asc())
                    .all()
                )
                
                for msg in messages:
                    if msg.role == "user":
                        history.add_user_message(msg.content)
                    elif msg.role == "assistant":
                        history.add_ai_message(msg.content)
        except Exception as e:
            logger.error(f"Failed to load chat history for {session_id}: {e}")
                    
        _session_store[session_id] = history
    return _session_store[session_id]


class LangchainRAGEngine:
    """
    Main RAG Engine using Langchain Expression Language (LCEL).
    """

    def __init__(
        self,
        collection_name: str = None,
        qdrant_url: str = None,
        embedding_model_name: str = None,
        top_k: int = 12,
    ):
        from app.config import settings
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        self.qdrant_url = qdrant_url or settings.QDRANT_URL
        self.embedding_model_name = embedding_model_name or settings.EMBEDDING_MODEL_NAME
        self.top_k = top_k
        self._initialized = False
        
        # Core components
        self.embeddings: Optional[HuggingFaceEmbeddings] = None
        self.qdrant: Optional[QdrantVectorStore] = None
        self.client: Optional[QdrantClient] = None
        self.llms: Dict[str, ChatOllama] = {}
        self.chains: Dict[str, RunnableWithMessageHistory] = {}
        
        logger.info(f"LangchainRAGEngine initialized (top_k={top_k})")

    def initialize(self) -> bool:
        """Initialize embeddings and vector store connections."""
        if self._initialized:
            return True

        logger.info("Initializing LangChain RAG embeddings & vectorstore...")
        try:
            # 1. Load Embeddings
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.embedding_model_name,
                model_kwargs={'device': 'cpu'}, # Use GPU if available
                encode_kwargs={'normalize_embeddings': True}
            )

            # 2. Connect to Qdrant
            self.client = QdrantClient(url=self.qdrant_url, check_compatibility=False)
            self.qdrant = QdrantVectorStore(
                client=self.client,
                collection_name=self.collection_name,
                embedding=self.embeddings,
                # Our custom chunks don't use a nested "metadata" key, 
                # they place keys ('doc_type', 'judul_dokumen', etc.) flat alongside 'text'
                content_payload_key="text",     
            )

            self._initialized = True
            logger.success("Vector store & embeddings ready.")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Langchain Engine: {e}")
            return False

    def _get_llm(self, model_name: str) -> ChatOllama:
        """Get or create ChatOllama instance for the requested model."""
        if model_name not in self.llms:
            # The current server points to a local ollama usually at 11434
            self.llms[model_name] = ChatOllama(
                base_url="http://localhost:11434",
                model=model_name,
                temperature=0.1, # Low temp for RAG
                num_predict=2048,
            )
        return self.llms[model_name]

    def _format_docs_for_prompt(self, docs: List[Document]) -> str:
        """
        Format Qdrant returned Documents into a structured context string.
        Includes explicit source list header to help LLM produce accurate citations.
        """
        if not docs:
            return "Tidak ada dokumen yang ditemukan."

        # Build explicit source list at the top
        source_list = ["DAFTAR SUMBER YANG TERSEDIA:"]
        for i, doc in enumerate(docs, 1):
            meta = doc.metadata or {}
            judul = meta.get("judul_dokumen", "Dokumen Tidak Diketahui")
            source_list.append(f"[{i}] {judul}")

        source_summary = "\n".join(source_list)
        source_summary += f"\n\nPENTING: Gunakan HANYA nomor sumber [1] sampai [{len(docs)}]. Jangan gunakan nomor lain.\n"
        source_summary += "\nDETAIL DOKUMEN:\n"

        # Build detailed context per document
        formatted = []
        for i, doc in enumerate(docs, 1):
            meta = doc.metadata or {}
            judul = meta.get("judul_dokumen", "Dokumen Tidak Diketahui")
            hierarchy = meta.get("hierarchy_path", "") or meta.get("hierarchy", "")

            ref_path = f"{judul} - {hierarchy}" if hierarchy else judul

            chunk_str = f"[{i}] Sumber: {ref_path}\nIsi: {doc.page_content}\n---"
            formatted.append(chunk_str)

        return source_summary + "\n\n".join(formatted)

    def _build_chain(self, model_name: str):
        """Build the full LCEL RAG chain including history."""
        
        # If retriever is not ready
        if not self._initialized:
            self.initialize()
            
        llm = self._get_llm(model_name)
        retriever = self.qdrant.as_retriever(search_kwargs={"k": self.top_k})
        
        # 1. Prompt Definition
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT_SPBE + "\n\nKonteks Referensi:\n{context}"),
            MessagesPlaceholder(variable_name="history"),
            ("human", "Pertanyaan: {input}")
        ])

        # 2. Sub-chain for retrieving and formatting documents
        # We save the raw retrieved documents in memory to extract 'sources' later
        def retrieve_and_format(inputs: dict) -> dict:
            query = inputs["input"]
            docs = retriever.invoke(query)
            
            # WORKAROUND: Langchain QdrantVectorStore ignores flat metadata fields not nested in 'metadata'
            # We fetch the actual payloads directly via our QdrantClient based on the returned UUIDs
            doc_ids = [doc.metadata.get("_id") for doc in docs if "_id" in doc.metadata]
            
            enriched_docs = []
            if doc_ids and self.client:
                try:
                    raw_points = self.client.retrieve(collection_name=self.collection_name, ids=doc_ids)
                    id_to_payload = {p.id: p.payload for p in raw_points}
                    
                    for doc in docs:
                        point_id = doc.metadata.get("_id")
                        if point_id in id_to_payload:
                            payload = id_to_payload[point_id]
                            # Inject the flat payload data back into Langchain's metadata
                            doc.metadata.update(payload)
                except Exception as e:
                    logger.warning(f"Failed to fetch enriched payload from Qdrant: {e}")
            
            # format the prompt using the enriched docs
            formatted_context = self._format_docs_for_prompt(docs)
            return {
                "context": formatted_context,
                "input": query,
                "history": inputs.get("history", []),
                "raw_docs": docs # passing the enriched raw objects to extract in astream_events
            }

        # 3. Main LCEL Pipeline
        # Note: We bind the output parser here.
        rag_pipeline = (
            RunnableLambda(retrieve_and_format)
            | prompt
            | llm
            | StrOutputParser()
        )

        # 4. Wrap with History
        chain_with_history = RunnableWithMessageHistory(
            rag_pipeline,
            get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )
        
        self.chains[model_name] = chain_with_history
        return chain_with_history

    def get_chain(self, model_name: str):
        """Get the LCEL chain ready for invoking or streaming."""
        if model_name not in self.chains:
            self._build_chain(model_name)
        return self.chains[model_name]

    def add_documents(self, texts: List[str], metadatas: List[Dict[str, Any]]):
        """Add new chunks to the Qdrant vector store."""
        if not self._initialized:
            self.initialize()
        self.qdrant.add_texts(texts=texts, metadatas=metadatas)


# Global instance
langchain_engine = LangchainRAGEngine()
