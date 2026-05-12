"""
LangChain RAG Engine - Clean Orchestrator for SPBE RAG System
Refactored for maximum modularity and developer maintainability.
"""

import re
import time
import asyncio
import json
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncIterator, Tuple
from functools import partial
from loguru import logger
import torch
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from langchain_core.embeddings import Embeddings
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.documents import Document

from app.config import settings
from app.database import SessionLocal
from app.models.db_models import Conversation
from app.core.rag.utils import safe_int

# Import Modular Components
from app.core.rag.engine.retrievers import HybridRetriever
from app.core.rag.engine.rankers import RAGRanker
from app.core.rag.engine.context_stitching import ContextStitcher
from app.core.rag.engine.llm_client import stream_answer as _stream_answer_core
from app.core.rag.legal_utils import (
    normalize_document_title,
    build_cover_citation_title,
)
from app.core.rag.prompts import expand_query

def classify_query(query: str) -> str:
    """Classify query type for routing: 'table', 'pasal', 'indikator', or 'general'."""
    q = (query or "").lower()
    if re.search(r'\btabel\b|\btable\b', q):
        return "table"
    if re.search(r'\bindikator\b|\bid[-\s]*\d+', q):
        return "indikator"
    if re.search(r'\bpasal\b|\bayat\b|\bperpres\b|\bpermenpan\b|\bpp\s*\d+\b|\bse\s+menteri\b', q):
        return "pasal"
    return "general"

class SBERTDirectEmbeddings(Embeddings):
    """Direct SentenceTransformer wrapper that inherits LangChain's Embeddings base class.
    
    Bypasses langchain-huggingface's HuggingFaceEmbeddings which hangs on Windows
    due to tokenizer parallelism issues during model initialization.
    """
    def __init__(self, model_name: str, cache_folder: str, device: str):
        import os
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        self.model = SentenceTransformer(model_name, cache_folder=cache_folder, device=device)
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()
        
    def embed_query(self, text: str) -> List[float]:
        return self.model.encode([text], normalize_embeddings=True)[0].tolist()

class LangchainRAGEngine:
    def __init__(self):
        self.collection_name = settings.QDRANT_COLLECTION
        self.qdrant_url = settings.QDRANT_URL
        self.embedding_model_name = settings.EMBEDDING_MODEL_NAME
        self.embedding_cache_dir = settings.EMBEDDING_CACHE_DIR
        self.embedding_device = settings.EMBEDDING_DEVICE
        self._initialized = False

        # Core Engines (Initialized in self.initialize)
        self.retriever: Optional[HybridRetriever] = None
        self.ranker: Optional[RAGRanker] = None
        self.stitcher: Optional[ContextStitcher] = None
        
        # Shared Resources
        self.embeddings = None
        self.client = None
        self.qdrant = None
        self._bm25 = None
        self._bm25_docs = []

    def initialize(self) -> bool:
        """Load models and initialize modular components."""
        if self._initialized:
            return True

        logger.info("[RAG] Initializing modular components...")
        try:
            # 1. Load Embeddings & Qdrant
            # Use custom SBERT wrapper to avoid hangs in langchain-huggingface on Windows
            self.embeddings = SBERTDirectEmbeddings(
                model_name=self.embedding_model_name,
                cache_folder=self.embedding_cache_dir,
                device=self.embedding_device,
            )
            self.client = QdrantClient(url=self.qdrant_url, check_compatibility=False)
            self.qdrant = QdrantVectorStore(
                client=self.client,
                collection_name=self.collection_name,
                embedding=self.embeddings,
                content_payload_key="text",
            )

            # 2. Load BM25 Index
            self._load_bm25()

            # 3. Instantiate Modular Components
            self.retriever = HybridRetriever(self.client, self.qdrant, self._bm25)
            self.ranker = RAGRanker()
            self.stitcher = ContextStitcher(self.client)

            self._initialized = True
            logger.info("[RAG] All components ready.")
            return True
        except Exception as e:
            logger.error(f"[RAG] Initialization failed: {e}")
            raise RuntimeError(f"RAG Engine failed to initialize: {e}") from e

    async def preload(self) -> bool:
        """Async wrapper for initialization."""
        return await asyncio.get_event_loop().run_in_executor(None, self.initialize)

    def _load_bm25(self):
        """Load BM25 index from disk."""
        backend_root = Path(__file__).resolve().parents[3]
        path = backend_root / "data" / "bm25_index.pkl"
        if path.exists():
            try:
                with path.open("rb") as f:
                    data = pickle.load(f)
                self._bm25 = data.get("bm25")
                self._bm25_docs = data.get("documents", [])
                logger.info(f"[BM25] Loaded {len(self._bm25_docs)} chunks")
            except Exception as e:
                logger.warning(f"[BM25] Failed to load: {e}")

    def _build_qdrant_filter(self, doc_id: Optional[str]):
        """Build a Qdrant Filter scoped to a specific document, or None for global search."""
        if not doc_id:
            return None
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        return Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id)))])

    def retrieve_context(
        self,
        query: str,
        top_k: int = 5,
        use_rag: bool = True,
        doc_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Main retrieval pipeline: Search -> Fusion -> Stitch -> Final Rank."""
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("RAG Engine is not initialized and initialization failed.")

        if not use_rag:
            return {"context": "", "sources": [], "raw_docs": []}

        query_type = classify_query(query)
        # Technical queries need more context candidates
        k = int(top_k or (8 if query_type in ["table", "indikator"] else 5))
        
        logger.info(f"[Retrieval] Processing '{query[:50]}...' (type: {query_type})")

        # 1. Expand query into variants for broader recall
        search_queries = expand_query(query)
        logger.info(f"[Retrieval] Expanded into {len(search_queries)} search variants")

        # 2. Parallel Search (Vector + BM25 + Table Literal + Indicator Literal)
        # Vector search: scoped to doc_id when provided — prevents cross-doc contamination in RRF pool
        qdrant_filter = self._build_qdrant_filter(doc_id)
        v_docs = []
        for sq in search_queries:
            v_docs.extend(self.retriever.vector_search(sq, k, qdrant_filter))
            
        b_docs = self.retriever.bm25_search(query, k * 2, self._bm25_docs, doc_id)
        l_docs = self.retriever.table_literal_search(query, self.collection_name, doc_id)
        i_docs = self.retriever.indicator_literal_search(query, self.collection_name, doc_id)

        # 3. Hybrid Fusion (RRF)
        # Combine results from all search paths
        candidates = self.ranker.rrf_fusion([v_docs, b_docs, l_docs, i_docs], max_candidates=25)
        
        # 4. Context Stitching (±1 neighbor chunks for better coherence)
        expanded_docs = self.stitcher.expand_docs_with_neighbor_context(candidates, self.collection_name)
        
        # 5. Final Ranking & Selection
        final_docs = self.ranker.rerank(query, expanded_docs, k)

        # 6. Format for LLM and UI
        context = self._format_context(final_docs)
        sources = self._build_sources_list(final_docs)

        return {
            "context": context,
            "sources": sources,
            "raw_docs": final_docs,
            "query_type": query_type
        }

    def _format_context(self, docs: List[Document]) -> str:
        """Format documents into a readable context string with clear citations and section info."""
        if not docs:
            return "Tidak ada dokumen yang ditemukan."

        lines = ["DAFTAR SUMBER RELEVAN:\n"]
        for i, doc in enumerate(docs, 1):
            meta = doc.metadata or {}
            base_title = build_cover_citation_title(meta)
            
            # Extract section info for label
            section = meta.get("context_header") or meta.get("pasal") or meta.get("hierarchy") or ""
            if section and " > " in section: # Clean up long hierarchy
                section = section.split(" > ")[-1]
            
            label = f"{base_title}"
            if section and section.lower() not in base_title.lower():
                label += f" - {section}"
                
            lines.append(f"[{i}] {label}")
        
        lines.append("\nDETAIL KONTEN SUMBER:\n")
        for i, doc in enumerate(docs, 1):
            meta = doc.metadata or {}
            base_title = build_cover_citation_title(meta)
            section = meta.get("context_header") or meta.get("pasal") or meta.get("hierarchy") or ""
            content = doc.page_content
            
            # Enrich context with parent text or table context if available
            parent_text = meta.get("parent_pasal_text")
            table_context = meta.get("table_context")
            
            if parent_text:
                content = f"[Konteks Induk]: {parent_text}\n[Isi Pasal]: {content}"
            elif table_context:
                content = f"[Konteks Sekitar Tabel]: {table_context}\n[Data Tabel]: {content}"
                
            lines.append(f"[{i}] Sumber: {base_title}\nLokasi: {section}\nIsi:\n{content}\n---\n")
            
        return "\n".join(lines)

    def _build_sources_list(self, docs: List[Document]) -> List[Dict[str, Any]]:
        """Map LangChain documents to serializable source dictionaries for the UI."""
        sources = []
        for i, doc in enumerate(docs, 1):
            meta = doc.metadata or {}
            # Build human-readable section label from best available metadata
            section = (
                meta.get("context_header")
                or meta.get("pasal")
                or meta.get("bab")
                or ""
            )
            hierarchy = meta.get("hierarchy") or ""
            
            raw_score = float(meta.get("rerank_score") or meta.get("rrf_score") or 0.0)
            
            # Normalize score to a 60-99 scale for better UX variance
            if raw_score < 0.1:
                # Base RRF score (usually 0.01 - 0.03) -> 65 to 75
                normalized = min(75.0, 65.0 + (raw_score * 300))
            else:
                # Boosted score (usually 0.5 - 3.0) -> 75 to 99
                normalized = min(99.9, 75.0 + (raw_score * 8.5))
                
            # Inject a small visual variance based on final rank so scores aren't identical in UI
            normalized = max(0.0, normalized - (i * 0.14))
                
            sources.append({
                "id": i,
                "doc_id": str(meta.get("document_id") or meta.get("doc_id") or ""),
                "document": build_cover_citation_title(meta),
                "document_short": normalize_document_title(meta),
                "section": section,
                "hierarchy": hierarchy,
                "score": round(normalized, 2),
                "snippet": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            })
        return sources

    def status(self) -> Dict[str, Any]:
        """Health check for RAG components."""
        return {
            "initialized": self._initialized,
            "qdrant_connected": self.client is not None,
            "bm25_loaded": self._bm25 is not None,
            "retriever_ready": self.retriever is not None,
            "ranker_ready": self.ranker is not None
        }

    async def stream_answer(self, *args, **kwargs) -> AsyncIterator[str]:
        """Streaming answer via modular LLM client."""
        async for token in _stream_answer_core(*args, **kwargs):
            yield token

    def load_history(self, session_id: str) -> List:
        """Load conversation history for context-aware chat."""
        messages = []
        try:
            with SessionLocal() as db:
                rows = db.query(Conversation).filter(Conversation.session_id == session_id).order_by(Conversation.timestamp.asc()).all()
                for row in rows:
                    if row.role == "user":
                        messages.append(HumanMessage(content=row.content))
                    elif row.role == "assistant":
                        messages.append(AIMessage(content=row.content))
        except Exception as e:
            logger.error(f"[History] Load failed: {e}")
        return messages

# Export single instance
langchain_engine = LangchainRAGEngine()
