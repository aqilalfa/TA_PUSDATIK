"""
LangChain RAG Engine - Clean Orchestrator for SPBE RAG System
Refactored for maximum modularity and developer maintainability.
"""

import re
import time
import asyncio
import json
import hashlib
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncIterator, Tuple, Literal, Callable
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
from app.core.rag.observability import RagTrace
from app.core.rag.query_profile import classify_query_profile
from app.core.rag.access_control import build_qdrant_access_filter

RetrievalMode = Literal["vector_only", "bm25_only", "hybrid", "final"]
RETRIEVAL_MODES: tuple[str, ...] = ("vector_only", "bm25_only", "hybrid", "final")
DEFAULT_RETRIEVAL_MODE: RetrievalMode = "final"


def normalize_retrieval_mode(mode: str | None) -> RetrievalMode:
    """Normalize and validate retrieval modes used for ablation experiments."""
    normalized = (mode or DEFAULT_RETRIEVAL_MODE).strip().lower().replace("-", "_")
    aliases = {
        "vector": "vector_only",
        "dense": "vector_only",
        "dense_only": "vector_only",
        "bm25": "bm25_only",
        "keyword": "bm25_only",
        "keyword_only": "bm25_only",
        "full": "final",
        "full_pipeline": "final",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in RETRIEVAL_MODES:
        allowed = ", ".join(RETRIEVAL_MODES)
        raise ValueError(f"Invalid retrieval_mode={mode!r}. Expected one of: {allowed}")
    return normalized  # type: ignore[return-value]

def classify_query(query: str) -> str:
    """Backward-compatible retrieval classification."""
    return classify_query_profile(query).retrieval_type

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
        self._reranker = None
        self.reranker_readiness = {"status": "not_loaded"}

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
            self.ranker = RAGRanker(
                reranker_instance=self._load_reranker(),
                deduplicate_contexts=True,
            )
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

    def _load_reranker(self):
        """Load the configured CrossEncoder once from local cache on bounded CPU."""
        if self._reranker is not None:
            return self._reranker
        try:
            from sentence_transformers import CrossEncoder

            snapshot_dir = Path(settings.RERANKER_CACHE_DIR) / settings.RERANKER_MODEL.rsplit("/", 1)[-1]
            model_source = (
                str(snapshot_dir)
                if (snapshot_dir / "config.json").is_file()
                else settings.RERANKER_MODEL
            )
            self._reranker = CrossEncoder(
                model_source,
                device="cpu",
                cache_folder=settings.RERANKER_CACHE_DIR,
                local_files_only=True,
            )
            self.reranker_readiness = {
                "status": "ready",
                "model": settings.RERANKER_MODEL,
                "source": model_source,
                "device": "cpu",
            }
        except (OSError, ValueError, RuntimeError) as exc:
            self._reranker = None
            self.reranker_readiness = {
                "status": "degraded",
                "reason": "local_model_unavailable",
                "error_type": type(exc).__name__,
            }
            logger.warning("[Reranker] Local CrossEncoder unavailable; degraded retrieval active")
        return self._reranker

    def _bm25_index_path(self) -> Path:
        """Return the configured local BM25 index path."""
        backend_root = Path(__file__).resolve().parents[3]
        return backend_root / "data" / "bm25_index.pkl"

    def _load_bm25(self, force: bool = False):
        """Load and validate the local BM25 index payload."""
        if self._bm25 is not None and not force:
            return

        path = self._bm25_index_path()
        if not path.exists():
            self._bm25 = None
            self._bm25_docs = []
            return

        try:
            with path.open("rb") as f:
                data = pickle.load(f)
            bm25 = data.get("bm25") if isinstance(data, dict) else None
            documents = data.get("documents") if isinstance(data, dict) else None
            if not callable(getattr(bm25, "get_scores", None)) or not isinstance(documents, list):
                raise ValueError("Invalid BM25 index payload")
            self._bm25 = bm25
            self._bm25_docs = documents
            logger.info(f"[BM25] Loaded {len(self._bm25_docs)} chunks")
        except Exception as e:
            self._bm25 = None
            self._bm25_docs = []
            logger.warning(f"[BM25] Failed to load: {e}")

    def _build_qdrant_filter(self, doc_id: Optional[str], current_user=None):
        """Build a Qdrant Filter scoped by document and user access metadata."""
        return build_qdrant_access_filter(doc_id=doc_id, current_user=current_user)

    def retrieve_context(
        self,
        query: str,
        top_k: int = 5,
        use_rag: bool = True,
        doc_id: Optional[str] = None,
        current_user=None,
        retrieval_mode: RetrievalMode | str = DEFAULT_RETRIEVAL_MODE,
        trace: RagTrace | None = None,
        rerank_candidate_limit_override: int | None = None,
    ) -> Dict[str, Any]:
        """Retrieve context using an explicit ablation-study retrieval mode."""
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("RAG Engine is not initialized and initialization failed.")

        mode = normalize_retrieval_mode(retrieval_mode)
        if not use_rag:
            return {
                "context": "",
                "sources": [],
                "raw_docs": [],
                "retrieval_mode": mode,
                "retrieval_status": "disabled",
                "failed_retrievers": [],
            }

        retriever = self.retriever
        ranker = self.ranker
        stitcher = self.stitcher
        if retriever is None or ranker is None or stitcher is None:
            raise RuntimeError("RAG Engine components are not initialized.")

        query_profile = classify_query_profile(query)
        query_type = query_profile.retrieval_type if mode == "final" else "general"
        k = int(top_k or 5)
        if mode == "final" and not top_k and query_type in ["table", "indikator"]:
            k = 8
        candidate_k = max(k * 3, 15)
        qdrant_filter = self._build_qdrant_filter(doc_id, current_user)
        search_queries = expand_query(query) if mode == "final" else [query]
        ranked_lists: List[List[Document]] = []
        ranked_families: List[str] = []
        attempted_retrievers: set[str] = set()
        failed_retrievers: set[str] = set()

        def run_search(family: str, operation: Callable[[], List[Document]]) -> List[Document]:
            attempted_retrievers.add(family)
            try:
                return operation()
            except Exception as exc:
                failed_retrievers.add(family)
                logger.error(
                    "[Retrieval] family={} failed error_type={}".format(
                        family,
                        type(exc).__name__,
                    )
                )
                return []

        if trace:
            trace.stage(
                "query.classified",
                status="ok",
                retrieval_type=query_type,
                answer_type=query_profile.answer_type,
                query_scope=query_profile.scope,
                retrieval_mode=mode,
                document_scope=doc_id,
            )
            trace.stage(
                "query.expanded",
                status="ok",
                variant_count=len(search_queries),
                variants=[{"variant_id": index, "query_hash": hashlib.sha256(item.encode("utf-8")).hexdigest()} for index, item in enumerate(search_queries)],
            )

        query_hash = trace.query_hash if trace else hashlib.sha256(query.encode("utf-8")).hexdigest()
        logger.info(
            "[Retrieval] Processing query_hash={} mode={} type={} variants={}".format(
                query_hash,
                mode,
                query_type,
                len(search_queries),
            )
        )

        if mode == "vector_only":
            final_docs = run_search(
                "vector",
                lambda: retriever.vector_search(query, k, qdrant_filter),
            )[:k]
        elif mode == "bm25_only":
            final_docs = run_search(
                "bm25",
                lambda: retriever.bm25_search(
                    query,
                    k,
                    self._bm25_docs,
                    doc_id,
                    current_user=current_user,
                ),
            )[:k]
        else:
            for query_index, sq in enumerate(search_queries):
                ranked_lists.append(
                    run_search(
                        "vector",
                        lambda sq=sq: retriever.vector_search(sq, candidate_k, qdrant_filter),
                    )
                )
                ranked_families.append("vector_original" if query_index == 0 else "vector_expansion")

            for query_index, sq in enumerate(search_queries):
                ranked_lists.append(
                    run_search(
                        "bm25",
                        lambda sq=sq: retriever.bm25_search(
                            sq,
                            candidate_k * 2,
                            self._bm25_docs,
                            doc_id,
                            current_user=current_user,
                        ),
                    )
                )
                ranked_families.append("bm25_original" if query_index == 0 else "bm25_expansion")

            for query_index, sq in enumerate(search_queries):
                ranked_lists.append(
                    run_search(
                        "table_literal",
                        lambda sq=sq: retriever.table_literal_search(
                            sq,
                            self.collection_name,
                            doc_id,
                            current_user=current_user,
                        ),
                    )
                )
                ranked_families.append("literal_original" if query_index == 0 else "literal_expansion")
                ranked_lists.append(
                    run_search(
                        "indicator_literal",
                        lambda sq=sq: retriever.indicator_literal_search(
                            sq,
                            self.collection_name,
                            doc_id,
                            current_user=current_user,
                        ),
                    )
                )
                ranked_families.append("literal_original" if query_index == 0 else "literal_expansion")

            if trace:
                trace.stage(
                    "retrieval.completed",
                    status="ok",
                    ranked_list_count=len(ranked_lists),
                    input_count=sum(len(items) for items in ranked_lists),
                )
            candidates = ranker.rrf_fusion(
                ranked_lists,
                max_candidates=max(100, candidate_k * 4),
                list_families=ranked_families,
                family_weights={
                    "vector_original": 1.0,
                    "bm25_original": 1.0,
                    "literal_original": 0.8,
                    "vector_expansion": 0.55,
                    "bm25_expansion": 0.55,
                    "literal_expansion": 0.4,
                },
            )
            if trace:
                trace.stage(
                    "fusion.rrf.completed",
                    status="ok",
                    output_count=len(candidates),
                    documents=[
                        {
                            "doc_id": (doc.metadata or {}).get("doc_id") or (doc.metadata or {}).get("document_id"),
                            "rank": index,
                            "score": (doc.metadata or {}).get("rrf_score"),
                        }
                        for index, doc in enumerate(candidates[:20], 1)
                    ],
                )
            if mode == "hybrid":
                final_docs = candidates[:k]
            else:
                expanded_docs = stitcher.expand_docs_with_neighbor_context(
                    candidates,
                    self.collection_name,
                    current_user=current_user,
                )
                if trace:
                    trace.stage(
                        "context.stitching.completed",
                        status="ok",
                        input_count=len(candidates),
                        output_count=len(expanded_docs),
                    )
                final_docs = ranker.rerank(
                    query,
                    expanded_docs,
                    k,
                    retrieval_type=query_type,
                    candidate_limit_override=rerank_candidate_limit_override,
                )
                if trace:
                    rerank_metadata = final_docs[0].metadata if final_docs else {}
                    trace.stage(
                        "rerank.completed",
                        status="ok",
                        input_count=len(expanded_docs),
                        output_count=len(final_docs),
                        candidate_limit=rerank_metadata.get("rerank_candidate_limit"),
                        candidate_count=rerank_metadata.get("rerank_candidate_count"),
                        candidate_policy=rerank_metadata.get("rerank_candidate_policy"),
                        elapsed_ms=rerank_metadata.get("rerank_elapsed_ms"),
                        documents=[
                            {
                                "doc_id": (doc.metadata or {}).get("doc_id") or (doc.metadata or {}).get("document_id"),
                                "rank": index,
                                "score": (doc.metadata or {}).get("rerank_score"),
                            }
                            for index, doc in enumerate(final_docs, 1)
                        ],
                    )

        context = self._format_context(final_docs)
        sources = self._build_sources_list(final_docs)
        if failed_retrievers:
            retrieval_status = (
                "failed"
                if attempted_retrievers and failed_retrievers == attempted_retrievers
                else "partial"
            )
        else:
            retrieval_status = "ok" if final_docs else "ok-empty"

        if trace:
            trace.stage(
                "retrieval.outcome",
                status=retrieval_status,
                attempted_retrievers=sorted(attempted_retrievers),
                failed_retrievers=sorted(failed_retrievers),
                output_count=len(final_docs),
            )

        return {
            "context": context,
            "sources": sources,
            "raw_docs": final_docs,
            "query_type": query_type,
            "answer_type": query_profile.answer_type,
            "query_scope": query_profile.scope,
            "retrieval_mode": mode,
            "retrieval_status": retrieval_status,
            "failed_retrievers": sorted(failed_retrievers),
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
