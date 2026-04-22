"""
LangChain RAG Engine - Main Orchestrator for SPBE RAG System

Simplified architecture:
- retrieve_context() → does retrieval + formatting (sync, called in thread)  
- stream_answer()    → streams LLM tokens (async generator)
- add_documents()    → adds new chunks to Qdrant
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncIterator
import json
import pickle
import re
from collections import Counter
from loguru import logger

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from langchain_qdrant import QdrantVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.documents import Document

from app.database import SessionLocal
from app.models.db_models import Conversation
from app.core.rag.prompts import (
    SYSTEM_PROMPT_TABLE,
    SYSTEM_PROMPT_LEGAL,
    SYSTEM_PROMPT_GENERAL,
    expand_query,
)
from app.config import settings


def classify_query(query: str) -> str:
    """Classify query type for routing: 'table', 'pasal', or 'general'."""
    q = (query or "").lower()
    if re.search(r'\btabel\b|\btable\b', q):
        return "table"
    if re.search(r'\bpasal\b|\bayat\b|\bperpres\b|\bpermenpan\b|\bpp\s*\d+\b|\bse\s+menteri\b', q):
        return "pasal"
    return "general"


class LangchainRAGEngine:
    """
    Simplified RAG Engine — no opaque LCEL chains.
    Retrieval and LLM streaming are explicit, debuggable steps.
    """

    def __init__(
        self,
        collection_name: str = None,
        qdrant_url: str = None,
        embedding_model_name: str = None,
        top_k: int = 5,
    ):
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        self.qdrant_url = qdrant_url or settings.QDRANT_URL
        self.embedding_model_name = embedding_model_name or settings.EMBEDDING_MODEL_NAME
        self.top_k = top_k
        self.vector_top_k = max(settings.VECTOR_SEARCH_TOP_K, top_k)
        self.bm25_top_k = max(settings.BM25_TOP_K, top_k)
        self.rrf_k = 60
        self.candidate_pool_size = max(40, top_k * 8)
        self._initialized = False

        # Core components
        self.embeddings: Optional[HuggingFaceEmbeddings] = None
        self.qdrant: Optional[QdrantVectorStore] = None
        self.client: Optional[QdrantClient] = None
        self.llms: Dict[str, ChatOllama] = {}
        self._bm25 = None
        self._bm25_docs: List[Dict[str, Any]] = []
        self._bm25_loaded = False
        self._bm25_mtime: Optional[float] = None
        self._reranker = None
        self._reranker_failed = False

        logger.info(
            "RAG Engine created "
            f"(top_k={top_k}, vector_top_k={self.vector_top_k}, bm25_top_k={self.bm25_top_k})"
        )

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self) -> bool:
        """Load embedding model and connect to Qdrant (blocking — call at startup)."""
        if self._initialized:
            return True

        logger.info("Loading embedding model & connecting to Qdrant...")
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.embedding_model_name,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )

            self.client = QdrantClient(url=self.qdrant_url, check_compatibility=False)
            self.qdrant = QdrantVectorStore(
                client=self.client,
                collection_name=self.collection_name,
                embedding=self.embeddings,
                content_payload_key="text",
            )

            self._load_bm25(force=True)

            self._initialized = True
            logger.success("Embedding model & Qdrant ready.")
            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False

    async def preload(self) -> bool:
        """Async wrapper — offloads blocking initialize() to a thread pool."""
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, self.initialize)

    # ------------------------------------------------------------------
    # LLM Management
    # ------------------------------------------------------------------

    def _get_llm(self, model_name: str) -> ChatOllama:
        """Get or create a ChatOllama instance."""
        if model_name not in self.llms:
            logger.info(f"[LLM] Creating ChatOllama: {model_name}")
            # Qwen3.x / Qwen3.5.x menggunakan "thinking" mode by default.
            # Mode ini menyebabkan chunk.content kosong selama fase reasoning.
            # Disable dengan think=False agar token langsung di-yield.
            is_thinking_model = any(model_name.startswith(p) for p in ["qwen3", "qwen3.5"])
            # langchain-ollama 1.0.1: parameter-nya adalah 'reasoning', bukan 'think'
            # ini akan di-pass sebagai {"think": False} ke Ollama API options
            extra_kwargs = {"reasoning": False} if is_thinking_model else {}
            self.llms[model_name] = ChatOllama(
                base_url=settings.OLLAMA_BASE_URL,
                model=model_name,
                temperature=0.1,
                num_predict=2048,
                timeout=600,  # 10 menit — model besar perlu waktu load awal
                **extra_kwargs,
            )
            if is_thinking_model:
                logger.info(f"[LLM] Thinking mode DISABLED for {model_name}")
        return self.llms[model_name]

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def _build_doc_filter(self, doc_id: Optional[str]) -> Optional[Filter]:
        """Build Qdrant filter to scope retrieval to a single document."""
        if not doc_id:
            return None
        return Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id)))])

    def _bm25_index_path(self) -> Path:
        backend_root = Path(__file__).resolve().parents[3]
        return backend_root / "data" / "bm25_index.pkl"

    def _load_bm25(self, force: bool = False):
        """Load/reload BM25 index from disk if available."""
        path = self._bm25_index_path()

        if not path.exists():
            if not self._bm25_loaded:
                logger.warning(f"BM25 index not found at {path}")
            self._bm25 = None
            self._bm25_docs = []
            self._bm25_loaded = True
            self._bm25_mtime = None
            return

        current_mtime = path.stat().st_mtime
        if not force and self._bm25_loaded and self._bm25_mtime == current_mtime:
            return

        try:
            with path.open("rb") as f:
                data = pickle.load(f)
            self._bm25 = data.get("bm25")
            self._bm25_docs = data.get("documents", [])
            self._bm25_loaded = True
            self._bm25_mtime = current_mtime
            logger.info(f"BM25 loaded ({len(self._bm25_docs)} chunks)")
        except Exception as e:
            logger.warning(f"Failed to load BM25 index: {e}")
            self._bm25 = None
            self._bm25_docs = []
            self._bm25_loaded = True
            self._bm25_mtime = None

    def _chunk_key(self, doc: Document) -> str:
        """Stable key for dedup/fusion across retrieval methods."""
        meta = doc.metadata or {}
        point_id = meta.get("_id")
        if point_id is not None:
            return f"point:{point_id}"

        doc_id = meta.get("doc_id")
        chunk_index = meta.get("chunk_index")
        if doc_id is not None and chunk_index is not None:
            return f"chunk:{doc_id}:{chunk_index}"

        text_prefix = (doc.page_content or "")[:180].strip().lower()
        return "|".join(
            [
                str(meta.get("doc_id", "")),
                str(meta.get("pasal", "")),
                str(meta.get("ayat", "")),
                str(meta.get("context_header", "")),
                text_prefix,
            ]
        )

    def _enrich_vector_payloads(self, docs: List[Document]):
        """Enrich LangChain docs with full Qdrant payload metadata."""
        doc_ids = [d.metadata.get("_id") for d in docs if "_id" in d.metadata]
        if not doc_ids or not self.client:
            return

        try:
            raw_points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=doc_ids,
            )
            id_map = {p.id: p.payload for p in raw_points}
            for doc in docs:
                pid = doc.metadata.get("_id")
                if pid in id_map:
                    doc.metadata.update(id_map[pid])
        except Exception as e:
            logger.warning(f"[Retrieval] Payload enrichment failed: {e}")

    def _vector_search(self, query: str, top_k: int, qdrant_filter=None) -> List[Document]:
        search_kwargs: dict = {"k": top_k}
        if qdrant_filter is not None:
            search_kwargs["filter"] = qdrant_filter
        retriever = self.qdrant.as_retriever(search_kwargs=search_kwargs)
        docs = retriever.invoke(query)
        self._enrich_vector_payloads(docs)
        return docs

    def _bm25_search(self, query: str, top_k: int, doc_id: Optional[str] = None) -> List[Document]:
        self._load_bm25()
        if self._bm25 is None or not self._bm25_docs:
            return []

        tokens = re.findall(r"\b\w+\b", query.lower())
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)
        top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        docs: List[Document] = []
        for idx in top_idx:
            raw = self._bm25_docs[idx]
            text = raw.get("text", "")
            metadata = dict(raw.get("metadata", {}))
            metadata["bm25_score"] = float(scores[idx])
            docs.append(Document(page_content=text, metadata=metadata))
        if doc_id:
            docs = [d for d in docs if str(d.metadata.get("doc_id", "")) == str(doc_id)]
        return docs

    def _table_literal_search(self, query: str, top_k: int) -> List[Document]:
        """Literal table lookup over BM25 source docs for queries like 'Tabel 13'."""
        self._load_bm25()
        if not self._bm25_docs:
            return []

        q = (query or "").lower()
        table_match = re.search(r"\b(?:tabel|table)\s*(?:ke[-\s]*)?(\d{1,3})\b", q)
        if not table_match:
            return []

        table_no = table_match.group(1)
        nomor_match = re.search(r"nomor\s+(\d+)", q)
        tahun_match = re.search(r"tahun\s+(\d{4})", q)

        table_regex = re.compile(
            rf"\b(?:tabel|table)\s*(?:ke[-\s]*)?{re.escape(table_no)}\b",
            re.IGNORECASE,
        )

        ranked: List[tuple[float, Document]] = []
        for raw in self._bm25_docs:
            text = str(raw.get("text", "") or "")
            if not text:
                continue

            if not table_regex.search(text):
                continue

            metadata = dict(raw.get("metadata", {}))
            meta_blob = " ".join(
                [
                    str(metadata.get("document_title", "") or ""),
                    str(metadata.get("judul_dokumen", "") or ""),
                    str(metadata.get("filename", "") or ""),
                    str(metadata.get("context_header", "") or ""),
                    str(metadata.get("bab", "") or ""),
                ]
            ).lower()
            text_blob = text.lower()[:2800]
            mention_only_index = "daftar tabel" in text_blob

            score = 2.50
            if "lampiran" in meta_blob or "lampiran" in text.lower()[:500]:
                score += 0.30
            if nomor_match and re.search(rf"\b{re.escape(nomor_match.group(1))}\b", meta_blob):
                score += 0.25
            if tahun_match and re.search(rf"\b{re.escape(tahun_match.group(1))}\b", meta_blob):
                score += 0.25
            if metadata.get("pasal"):
                score -= 0.10
            if mention_only_index:
                score -= 0.95
            if "isi" in q and mention_only_index:
                score -= 0.35
            if len(text.strip()) < 280:
                score -= 0.25

            if metadata.get("is_table"):
                score += 0.50
            label = str(metadata.get("table_label", "") or "").lower()
            if label and label == f"tabel {table_no}":
                score += 0.30

            metadata["table_literal_score"] = float(score)
            ranked.append((score, Document(page_content=text, metadata=metadata)))

        ranked.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in ranked[:top_k]]

    @staticmethod
    def _append_unique_search_query(queries: List[str], candidate: str):
        """Append candidate query if not already present (case-insensitive)."""
        normalized = " ".join(str(candidate or "").split())
        if not normalized:
            return

        existing = {q.lower() for q in queries}
        if normalized.lower() not in existing:
            queries.append(normalized)

    def _run_hybrid_retrieval(
        self,
        query: str,
        search_queries: List[str],
        final_top_k: int,
        vector_top_k: Optional[int] = None,
        bm25_top_k: Optional[int] = None,
        literal_table_top_k: Optional[int] = None,
        qdrant_filter=None,
        doc_id: Optional[str] = None,
    ) -> List[Document]:
        """Run vector+BM25+literal retrieval, fusion, rerank, then neighbor stitching."""
        cleaned_queries: List[str] = []
        for q in search_queries or []:
            self._append_unique_search_query(cleaned_queries, q)
        if not cleaned_queries:
            cleaned_queries = [query]

        v_top_k = max(1, int(vector_top_k or self.vector_top_k))
        b_top_k = max(1, int(bm25_top_k or self.bm25_top_k))
        t_top_k = max(1, int(literal_table_top_k or max(3, final_top_k)))

        ranked_lists: List[List[Document]] = []
        for q in cleaned_queries:
            vdocs = self._vector_search(q, v_top_k, qdrant_filter=qdrant_filter)
            if vdocs:
                ranked_lists.append(vdocs)

            bdocs = self._bm25_search(q, b_top_k, doc_id=doc_id)
            if bdocs:
                ranked_lists.append(bdocs)

        literal_table_docs = self._table_literal_search(query, top_k=t_top_k)
        if literal_table_docs:
            logger.info(f"[Retrieval] Literal table candidates: {len(literal_table_docs)}")
            ranked_lists.append(literal_table_docs)

        if not ranked_lists:
            return []

        fused = self._rrf_fusion(
            ranked_lists,
            max_candidates=max(self.candidate_pool_size, final_top_k * 4),
        )
        docs = self._rerank(query, fused, top_k=final_top_k)

        if docs:
            docs = self._expand_docs_with_neighbor_context(docs, radius=1)
        return docs

    @staticmethod
    def _extract_table_anchors(
        docs: List[Document],
        table_no: str,
        min_hits: int = 2,
        max_anchors: int = 5,
    ) -> List[str]:
        """Extract recurring structural phrases from retrieved table chunks.

        A phrase found in >= min_hits distinct chunks is likely a real column
        header or row label for this table, not noise. Returns at most
        max_anchors phrases sorted by frequency.
        """
        if not docs or not table_no:
            return []

        target_label = f"tabel {table_no}".lower()
        word_pattern = re.compile(r"[A-Za-z\u00C0-\u024F]+")

        table_chunks = [
            d for d in docs
            if target_label in (d.page_content or "").lower()
            or str(d.metadata.get("table_label", "")).lower() == target_label
        ]
        if not table_chunks:
            return []

        phrase_counter: Counter = Counter()
        for doc in table_chunks:
            preview = (doc.page_content or "")[:400].lower()
            words = [w for w in word_pattern.findall(preview) if len(w) >= 3]
            seen: set = set()
            for n in range(2, 5):
                for i in range(len(words) - n + 1):
                    phrase = " ".join(words[i : i + n])
                    seen.add(phrase)
            for phrase in seen:
                phrase_counter[phrase] += 1

        anchors = [
            phrase
            for phrase, count in phrase_counter.most_common(20)
            if count >= min_hits
        ]
        return anchors[:max_anchors]

    @staticmethod
    def _table_anchor_coverage_score(docs: List[Document], anchors: List[str]) -> int:
        """Count how many anchors appear in combined docs text.

        Returns 0 when anchors is empty (no anchors = no penalty, treat as complete).
        """
        if not anchors or not docs:
            return 0
        blob = "\n".join((doc.page_content or "") for doc in docs).lower()
        return sum(1 for anchor in anchors if anchor in blob)

    @staticmethod
    def _is_table_index_noise_doc(doc: Document, table_no: Optional[str]) -> bool:
        """Identify chunks that mostly list table titles (index pages) without actual table content."""
        text = str((doc.page_content or "")).strip()
        if not text:
            return True

        text_blob = text.lower()
        meta = doc.metadata or {}
        meta_blob = " ".join(
            [
                str(meta.get("context_header", "") or ""),
                str(meta.get("hierarchy", "") or ""),
                str(meta.get("hierarchy_path", "") or ""),
                str(meta.get("bab", "") or ""),
                str(meta.get("bagian", "") or ""),
            ]
        ).lower()

        has_table_semantic_content = any(
            marker in text_blob
            for marker in (
                "persamaan",
                "perbedaan",
                "pemantauan spbe",
                "evaluasi spbe",
            )
        )

        is_index_like = "daftar tabel" in text_blob or "daftar tabel" in meta_blob

        if table_no:
            table_pattern = re.compile(
                rf"\b(?:tabel|table)\s*(?:ke[-\s]*)?{re.escape(table_no)}\b",
                re.IGNORECASE,
            )
            mentions_target_table = bool(table_pattern.search(text))
        else:
            mentions_target_table = "tabel" in text_blob

        very_short = len(text) < 420

        return (
            mentions_target_table
            and is_index_like
            and not has_table_semantic_content
            and very_short
        )

    def _filter_table_noise_docs(
        self,
        docs: List[Document],
        table_no: Optional[str],
        final_top_k: int,
    ) -> List[Document]:
        """Remove table index-only chunks when enough richer chunks are available."""
        if not docs:
            return docs

        clean_docs: List[Document] = []
        noise_docs: List[Document] = []
        for doc in docs:
            if self._is_table_index_noise_doc(doc, table_no):
                noise_docs.append(doc)
            else:
                clean_docs.append(doc)

        # Keep conservative behavior when we do not have enough non-noise candidates.
        if len(clean_docs) < max(4, final_top_k // 2):
            return docs[:final_top_k]

        filtered = clean_docs[:final_top_k]
        if not filtered:
            return docs[:final_top_k]
        return filtered

    def _rrf_fusion(self, ranked_lists: List[List[Document]], max_candidates: int) -> List[Document]:
        """Reciprocal Rank Fusion across multiple ranked lists."""
        if not ranked_lists:
            return []

        scores: Dict[str, float] = {}
        docs_by_key: Dict[str, Document] = {}

        for docs in ranked_lists:
            for rank, doc in enumerate(docs, 1):
                key = self._chunk_key(doc)
                scores[key] = scores.get(key, 0.0) + 1.0 / (self.rrf_k + rank)
                if key not in docs_by_key:
                    docs_by_key[key] = doc

        fused: List[Document] = []
        ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for key, score in ordered[:max_candidates]:
            doc = docs_by_key[key]
            doc.metadata = doc.metadata or {}
            doc.metadata["rrf_score"] = float(score)
            fused.append(doc)

        return fused

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        """Best-effort integer conversion for metadata fields."""
        try:
            if value is None or value == "":
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _longest_suffix_prefix_overlap(left: str, right: str, max_window: int = 220) -> int:
        """Return overlap length where suffix(left) == prefix(right)."""
        if not left or not right:
            return 0

        max_len = min(len(left), len(right), max_window)
        for size in range(max_len, 23, -1):
            if left[-size:] == right[:size]:
                return size
        return 0

    def _merge_text_parts(self, parts: List[str]) -> str:
        """Merge neighboring chunk texts while minimizing duplicated overlap."""
        clean_parts = [str(part or "").strip() for part in parts if str(part or "").strip()]
        if not clean_parts:
            return ""
        if len(clean_parts) == 1:
            return clean_parts[0]

        merged = clean_parts[0]
        for part in clean_parts[1:]:
            if part == merged:
                continue

            overlap = self._longest_suffix_prefix_overlap(merged, part)
            if overlap > 0:
                merged += part[overlap:]
            else:
                merged += "\n\n" + part
        return merged

    def _fetch_neighbor_documents(
        self,
        centers_by_doc: Dict[str, set],
        radius: int = 1,
    ) -> List[Document]:
        """Fetch i-1/i+1 neighbors from SQLite for selected chunks."""
        if not centers_by_doc:
            return []

        from app.models.db_models import Document as DBDocument, Chunk

        results: List[Document] = []
        radius = max(0, int(radius))

        with SessionLocal() as db:
            for raw_doc_id, center_indexes in centers_by_doc.items():
                doc_id = str(raw_doc_id or "").strip()
                if not doc_id:
                    continue

                db_doc = db.query(DBDocument).filter(DBDocument.doc_id == doc_id).first()
                if not db_doc and doc_id.isdigit():
                    db_doc = db.query(DBDocument).filter(DBDocument.id == int(doc_id)).first()
                if not db_doc:
                    continue

                neighbor_indexes = set()
                for center in center_indexes:
                    for delta in range(1, radius + 1):
                        prev_idx = center - delta
                        next_idx = center + delta
                        if prev_idx >= 0:
                            neighbor_indexes.add(prev_idx)
                        neighbor_indexes.add(next_idx)

                if not neighbor_indexes:
                    continue

                rows = (
                    db.query(Chunk)
                    .filter(
                        Chunk.document_id == db_doc.id,
                        Chunk.chunk_index.in_(neighbor_indexes),
                    )
                    .all()
                )

                for row in rows:
                    anchor_index = None
                    for center in center_indexes:
                        if abs(center - row.chunk_index) <= radius and center != row.chunk_index:
                            anchor_index = center
                            break

                    if anchor_index is None:
                        continue

                    meta = {}
                    if row.chunk_metadata:
                        try:
                            meta = json.loads(row.chunk_metadata)
                        except Exception:
                            meta = {}

                    meta = dict(meta or {})
                    meta.setdefault("doc_id", db_doc.doc_id or str(db_doc.id))
                    meta.setdefault("document_title", db_doc.document_title or db_doc.filename or "")
                    meta.setdefault("filename", db_doc.original_filename or db_doc.filename or "")
                    meta.setdefault("doc_type", db_doc.doc_type or "other")
                    meta["chunk_index"] = int(row.chunk_index)
                    meta["_neighbor_of_chunk_index"] = int(anchor_index)
                    meta["_source_kind"] = "neighbor"

                    results.append(
                        Document(
                            page_content=row.chunk_text or "",
                            metadata=meta,
                        )
                    )

        return results

    def _expand_docs_with_neighbor_context(
        self,
        primary_docs: List[Document],
        radius: int = 1,
    ) -> List[Document]:
        """Create stitched retrieval docs by combining primary hits with nearby chunks."""
        if not primary_docs:
            return []

        centers_by_doc: Dict[str, set] = {}
        for doc in primary_docs:
            meta = doc.metadata or {}
            doc_id = str(meta.get("doc_id") or "").strip()
            chunk_index = self._safe_int(meta.get("chunk_index"))
            if not doc_id or chunk_index is None:
                continue

            centers_by_doc.setdefault(doc_id, set()).add(chunk_index)

        if not centers_by_doc:
            return primary_docs

        neighbor_docs = self._fetch_neighbor_documents(centers_by_doc, radius=radius)
        neighbors_by_anchor: Dict[tuple, List[Document]] = {}
        for ndoc in neighbor_docs:
            nmeta = ndoc.metadata or {}
            doc_id = str(nmeta.get("doc_id") or "").strip()
            anchor = self._safe_int(nmeta.get("_neighbor_of_chunk_index"))
            if not doc_id or anchor is None:
                continue
            neighbors_by_anchor.setdefault((doc_id, anchor), []).append(ndoc)

        stitched_docs: List[Document] = []
        for pdoc in primary_docs:
            pmeta = dict(pdoc.metadata or {})
            doc_id = str(pmeta.get("doc_id") or "").strip()
            center_idx = self._safe_int(pmeta.get("chunk_index"))

            if not doc_id or center_idx is None:
                stitched_docs.append(pdoc)
                continue

            related = neighbors_by_anchor.get((doc_id, center_idx), [])
            parts = [pdoc] + related

            unique_by_index: Dict[int, Document] = {}
            for part in parts:
                idx = self._safe_int((part.metadata or {}).get("chunk_index"))
                if idx is None:
                    continue
                if idx not in unique_by_index:
                    unique_by_index[idx] = part

            if not unique_by_index:
                stitched_docs.append(pdoc)
                continue

            ordered_indexes = sorted(unique_by_index.keys())
            ordered_parts = [unique_by_index[i] for i in ordered_indexes]
            stitched_text = self._merge_text_parts([d.page_content for d in ordered_parts])

            stitched_meta = dict(pmeta)
            if len(ordered_parts) > 1:
                stitched_meta["stitched_parts"] = len(ordered_parts)
                stitched_meta["stitched_chunk_start"] = ordered_indexes[0]
                stitched_meta["stitched_chunk_end"] = ordered_indexes[-1]

            if not stitched_meta.get("parent_pasal_text"):
                for part in ordered_parts:
                    parent_text = str((part.metadata or {}).get("parent_pasal_text") or "").strip()
                    if parent_text:
                        stitched_meta["parent_pasal_text"] = parent_text
                        break

            stitched_docs.append(Document(page_content=stitched_text, metadata=stitched_meta))

        return stitched_docs

    def _get_reranker(self):
        """Lazy-load cross-encoder reranker. Fallback gracefully if unavailable."""
        if self._reranker_failed:
            return None

        if self._reranker is None:
            try:
                from sentence_transformers import CrossEncoder

                self._reranker = CrossEncoder(
                    settings.RERANKER_MODEL_NAME,
                    device=settings.RERANKER_DEVICE,
                )
                logger.info(f"Reranker loaded: {settings.RERANKER_MODEL_NAME}")
            except Exception as e:
                self._reranker_failed = True
                logger.warning(f"Reranker unavailable, fallback to RRF-only: {e}")
                return None

        return self._reranker

    def _clean_title_text(self, value: str) -> str:
        """Normalize title-like text for consistent source rendering."""
        text = str(value or "").strip()
        if not text:
            return ""
        text = re.sub(r"\.pdf$", "", text, flags=re.IGNORECASE)
        text = text.replace("_", " ")
        text = re.sub(r"\s+", " ", text).strip(" -")
        return text

    def _detect_regulation_type(self, text: str) -> str:
        """Detect high-level doc type to resolve conflicting metadata titles."""
        t = str(text or "").lower()
        if "peraturan presiden" in t or re.search(r"\bperpres\b", t):
            return "perpres"
        if "peraturan menteri" in t or "permenpan" in t or re.search(r"\bpermen\b", t):
            return "permen"
        if "peraturan pemerintah" in t or re.search(r"\bpp\b", t):
            return "pp"
        if "pedoman" in t:
            return "pedoman"
        if "laporan" in t:
            return "laporan"
        return ""

    def _is_suspicious_title(self, title: str) -> bool:
        """Identify malformed extracted titles such as 'tentang 59 Tahun 2020'."""
        t = str(title or "").lower()
        if not t:
            return True
        if re.search(r"\btentang\s+\d+\s+tahun\s+\d{4}\b", t):
            return True
        if t.count("tahun") >= 2 and re.search(
            r"\bnomor\s+\d+.*\btahun\s+\d{4}.*\btahun\s+\d{4}\b", t
        ):
            return True
        return False

    def _normalize_document_title(self, metadata: Dict[str, Any]) -> str:
        """Choose the most reliable document title between metadata fields and filename."""
        meta = metadata or {}
        raw_title = (
            meta.get("document_title")
            or meta.get("judul_dokumen")
            or meta.get("tentang")
            or ""
        )
        raw_filename = meta.get("filename") or ""

        title = self._clean_title_text(raw_title)
        filename_title = self._clean_title_text(raw_filename)

        if not title:
            return filename_title or "Dokumen"
        if not filename_title:
            return title

        title_type = self._detect_regulation_type(title)
        file_type = self._detect_regulation_type(filename_title)

        if title_type and file_type and title_type != file_type:
            return filename_title
        if self._is_suspicious_title(title):
            return filename_title
        if len(title) < 12 and len(filename_title) > len(title):
            return filename_title

        return title

    def _clean_about_text(self, value: str) -> str:
        """Normalize about/subject phrase used in legal document cover titles."""
        text = self._clean_title_text(value)
        if not text:
            return ""
        text = re.sub(r"^(?i:tentang)\s+", "", text).strip()
        text = re.sub(r"\s+", " ", text)

        # Many parsed PDF titles are all-caps; convert to readable phrase while keeping key acronyms.
        if text.isupper() and len(text) > 6:
            text = text.title()
            text = re.sub(r"\bSpbe\b", "SPBE", text)
            text = re.sub(r"\bTik\b", "TIK", text)
            text = re.sub(r"\bBssn\b", "BSSN", text)
            text = re.sub(r"\bPan\s*Rb\b", "PAN RB", text)

        return text.strip(" -")

    def _build_cover_citation_title(self, metadata: Dict[str, Any]) -> str:
        """Build a fuller citation title aligned with document cover style when possible."""
        meta = metadata or {}
        base_title = self._normalize_document_title(meta)
        about_text = self._clean_about_text(str(meta.get("tentang") or ""))

        if not about_text:
            return base_title
        if self._is_suspicious_title(about_text):
            return base_title

        base_lower = base_title.lower()
        about_lower = about_text.lower()

        if about_lower in base_lower:
            return base_title
        if "tentang" in base_lower:
            return base_title
        if base_title == "Dokumen":
            return about_text

        return f"{base_title} tentang {about_text}"

    def _build_table_guardrail(self, query: str, context: str) -> str:
        """Build dynamic instruction so table queries do not collapse to false negatives."""
        q = str(query or "")
        c = str(context or "")
        table_match = re.search(r"\b(?:tabel|table)\s*(?:ke[-\s]*)?(\d{1,3})\b", q, re.IGNORECASE)
        if not table_match:
            return ""

        table_no = table_match.group(1)
        table_pattern = re.compile(
            rf"\b(?:tabel|table)\s*(?:ke[-\s]*)?{re.escape(table_no)}\b",
            re.IGNORECASE,
        )
        if not table_pattern.search(c):
            return ""

        return (
            f"Instruksi tambahan pertanyaan tabel: konteks memuat Tabel {table_no}. "
            f"Wajib jawab menggunakan isi Tabel {table_no} yang tersedia di konteks, sertakan sitasi [n], "
            "dan jangan menyatakan 'tidak ditemukan' untuk Tabel tersebut. "
            "Jika isi tabel yang tersedia benar-benar parsial, nyatakan jawaban berdasar bagian yang tersedia saja."
        )

    def _extract_guardrail_focus_terms(self, query: str, max_terms: int = 8) -> List[str]:
        """Extract concise focus terms from query for generic grounding guardrails."""
        stopwords = {
            "yang",
            "dan",
            "atau",
            "dari",
            "pada",
            "untuk",
            "dalam",
            "dengan",
            "apa",
            "siapa",
            "bagaimana",
            "kapan",
            "dimana",
            "jelaskan",
            "sebutkan",
            "tolong",
            "berdasarkan",
            "dokumen",
            "peraturan",
            "tentang",
            "isi",
        }

        tokens = re.findall(r"[a-zA-Z0-9]{2,}", str(query or "").lower())
        focus_terms: List[str] = []

        for token in tokens:
            if token in stopwords:
                continue
            if token.isdigit() and len(token) < 2:
                continue
            if not token.isdigit() and len(token) < 3:
                continue
            if token not in focus_terms:
                focus_terms.append(token)
            if len(focus_terms) >= max_terms:
                break

        return focus_terms

    def _build_generic_grounding_guardrail(self, query: str, context: str) -> str:
        """Build query-agnostic grounding instruction to reduce generic false-negative claims."""
        q = str(query or "")
        c = str(context or "")
        c_lower = c.lower()

        if not q.strip() or not c.strip():
            return ""

        focus_terms = self._extract_guardrail_focus_terms(q)
        anchored_terms = [
            term
            for term in focus_terms
            if re.search(rf"\b{re.escape(term)}\b", c_lower)
        ]

        if not anchored_terms:
            return ""

        instructions = [
            "Instruksi tambahan kualitas jawaban:",
            "- Gunakan hanya fakta yang ada pada konteks referensi.",
            "- Fokus pada inti pertanyaan, jangan melebar ke topik lain.",
            "- Jangan menyatakan informasi 'tidak ditemukan/tidak tersedia' jika istilah kunci terlihat di konteks;"
            " jelaskan bagian yang tersedia secara faktual.",
            "- Pastikan poin informatif memiliki sitasi [n].",
            "- Istilah kunci yang wajib dicakup bila tersedia: " + ", ".join(anchored_terms[:8]) + ".",
        ]

        if re.search(
            r"\b(?:apa saja|sebutkan|daftar|rincian|langkah|tahap|komponen|indikator)\b",
            q,
            re.IGNORECASE,
        ):
            instructions.append(
                "- Karena pertanyaan meminta rincian, tulis butir utama secara lengkap dalam format daftar."
            )

        return "\n".join(instructions)

    def _build_quality_guardrail(self, query: str, context: str) -> str:
        """Combine generic and specialized guardrails to keep prompts reusable across cases."""
        parts: List[str] = []

        generic_guardrail = self._build_generic_grounding_guardrail(query, context)
        if generic_guardrail:
            parts.append(generic_guardrail)

        table_guardrail = self._build_table_guardrail(query, context)
        if table_guardrail:
            parts.append(table_guardrail)

        return "\n\n".join(parts)

    def _query_metadata_boost(self, query: str, metadata: Dict[str, Any], text: str = "") -> float:
        """Apply lightweight query-aware metadata boost to reduce legal-document ambiguity."""
        q = (query or "").lower()
        meta = metadata or {}
        pasal_meta = str(meta.get("pasal", "") or "").lower()
        bab_meta = str(meta.get("bab", "") or "").lower()
        ayat_meta = str(meta.get("ayat", "") or "").lower()
        text_blob = (text or "")[:2500].lower()

        doc_blob = " ".join(
            [
                str(meta.get("document_title", "") or ""),
                str(meta.get("judul_dokumen", "") or ""),
                str(meta.get("filename", "") or ""),
                str(meta.get("hierarchy", "") or ""),
                str(meta.get("context_header", "") or ""),
                str(meta.get("doc_type", "") or ""),
                pasal_meta,
                str(meta.get("ayat", "") or ""),
                text_blob,
            ]
        ).lower()

        boost = 0.0

        if "perpres" in q and ("peraturan presiden" in doc_blob or "perpres" in doc_blob):
            boost += 0.25
        if "permen" in q and ("peraturan menteri" in doc_blob or "permen" in doc_blob):
            boost += 0.25
        if "pp " in q and ("peraturan pemerintah" in doc_blob or " pp " in f" {doc_blob} "):
            boost += 0.25

        nomor_match = re.search(r"nomor\s+(\d+)", q)
        if nomor_match:
            nomor = nomor_match.group(1)
            if re.search(rf"\b{re.escape(nomor)}\b", doc_blob):
                boost += 0.20

        tahun_match = re.search(r"tahun\s+(\d{4})", q)
        if tahun_match:
            tahun = tahun_match.group(1)
            if re.search(rf"\b{re.escape(tahun)}\b", doc_blob):
                boost += 0.20

        pasal_match = re.search(r"pasal\s+(\d+)", q)
        if pasal_match:
            pasal_no = pasal_match.group(1)
            if re.search(rf"\bpasal\s+{re.escape(pasal_no)}\b", pasal_meta):
                boost += 0.55
            elif re.search(rf"\bpasal\s+{re.escape(pasal_no)}\b", doc_blob):
                boost += 0.20

        # Table-sensitive retrieval: keep "Tabel X" queries anchored to table chunks,
        # not to similarly numbered Pasal chunks.
        table_match = re.search(r"\b(?:tabel|table)\s*(?:ke[-\s]*)?(\d{1,3})\b", q)
        if table_match:
            table_no = table_match.group(1)
            if re.search(rf"\btabel\s*(?:ke[-\s]*)?{re.escape(table_no)}\b", doc_blob):
                boost += 1.35
            elif "tabel" in doc_blob:
                boost += 0.20

            # Metadata-driven boost: chunks explicitly flagged as table content
            # get prioritized independent of text-pattern matching.
            if metadata.get("is_table"):
                boost += 0.40
            label = str(metadata.get("table_label", "") or "").lower()
            if label and label == f"tabel {table_no}":
                boost += 0.25

            if "lampiran" in doc_blob:
                boost += 0.25

            mention_only_index = "daftar tabel" in text_blob
            if mention_only_index:
                boost -= 0.95
            if "isi" in q and mention_only_index:
                boost -= 0.35

            if "perbandingan pemantauan dan evaluasi spbe" in doc_blob:
                boost += 0.35

            # Down-rank pure Pasal chunks if user asks table but does not ask Pasal explicitly.
            if pasal_meta and not pasal_match:
                boost -= 0.35

            if "domain" in q and any(
                kw in doc_blob for kw in ["domain 1", "domain 2", "domain 3", "domain 4"]
            ):
                boost += 0.20
            if "indikator" in q and "indikator" in doc_blob:
                boost += 0.15

        if "definisi" in q or "pengertian" in q:
            if re.search(r"\bpasal\s+1\b", pasal_meta):
                boost += 0.55
                if "bab i" in bab_meta or "ketentuan umum" in doc_blob:
                    boost += 1.10
                else:
                    boost -= 0.20
            if "yang dimaksud dengan" in doc_blob:
                boost += 0.90
            if "selanjutnya disingkat spbe adalah" in doc_blob:
                boost += 1.00
            if (
                "arsitektur spbe nasional" in doc_blob
                and "yang dimaksud dengan" not in doc_blob
            ):
                boost -= 0.45
            if ayat_meta:
                boost -= 0.10
            if "lampiran" in doc_blob:
                boost -= 0.40

        if "domain" in q and "evaluasi" in q and "spbe" in q:
            if any(
                kw in doc_blob
                for kw in [
                    "pemantauan dan evaluasi spbe",
                    "kebijakan internal spbe",
                    "tata kelola spbe",
                    "manajemen spbe",
                    "layanan spbe",
                ]
            ):
                boost += 0.65
            if "arsitektur spbe" in doc_blob and "evaluasi spbe" not in doc_blob:
                boost -= 0.35

        return boost

    def _rerank(self, query: str, docs: List[Document], top_k: int) -> List[Document]:
        """Rerank candidate docs with cross-encoder, fallback to plain ranking."""
        if not docs:
            return []

        reranker = self._get_reranker()
        if reranker is None:
            return docs[:top_k]

        try:
            pairs = [(query, (doc.page_content or "")[:3000]) for doc in docs]
            scores = reranker.predict(pairs, show_progress_bar=False)
            ranked = sorted(zip(scores, docs), key=lambda x: float(x[0]), reverse=True)

            boosted: List[tuple] = []
            for score, doc in ranked:
                doc.metadata = doc.metadata or {}
                base_score = float(score)
                query_boost = self._query_metadata_boost(query, doc.metadata, doc.page_content)
                final_score = base_score + query_boost
                doc.metadata["rerank_score"] = base_score
                doc.metadata["query_boost"] = float(query_boost)
                doc.metadata["final_score"] = float(final_score)
                boosted.append((final_score, doc))

            boosted.sort(key=lambda x: x[0], reverse=True)
            return [doc for _, doc in boosted[:top_k]]
        except Exception as e:
            logger.warning(f"Reranker failed at runtime, fallback to RRF-only: {e}")
            return docs[:top_k]

    def retrieve_context(
        self,
        query: str,
        top_k: Optional[int] = None,
        use_rag: bool = True,
        doc_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve relevant documents from Qdrant and format them as context.
        
        Returns dict with:
          - context: formatted string for the LLM prompt
          - sources: list of source metadata for the UI
          - raw_docs: list of LangChain Document objects
        """
        if not self._initialized:
            self.initialize()

        if not use_rag:
            return {"context": "", "sources": [], "raw_docs": []}

        query_type = classify_query(query)
        is_table_query = query_type == "table"

        base_top_k = max(1, int(top_k or self.top_k))
        if query_type == "table":
            final_top_k = max(base_top_k, 8)
        else:
            final_top_k = min(base_top_k, 6)

        qdrant_filter = self._build_doc_filter(doc_id)

        logger.info(f"[Retrieval] Query: '{query[:60]}'")

        expanded_queries = expand_query(query)
        logger.info(f"[Retrieval] Expanded into {len(expanded_queries)} query variants")

        docs = self._run_hybrid_retrieval(
            query=query,
            search_queries=expanded_queries,
            final_top_k=final_top_k,
            qdrant_filter=qdrant_filter,
            doc_id=doc_id,
        )

        # Fallback: if doc_id filter returned 0 results, retry without filter
        if qdrant_filter is not None and not docs:
            logger.warning(
                f"[Retrieval] doc_id filter returned 0 results for doc_id='{doc_id}', "
                "falling back to unscoped retrieval"
            )
            docs = self._run_hybrid_retrieval(
                query=query,
                search_queries=expanded_queries,
                final_top_k=final_top_k,
            )

        # Table completeness safety-net: if anchor-based coverage is low, retry once
        # using the missing anchor phrases as additional query keywords.
        if is_table_query:
            anchor_table_match = re.search(
                r"\b(?:tabel|table)\s*(?:ke[-\s]*)?(\d{1,3})\b", query, re.IGNORECASE
            )
            anchor_table_no = anchor_table_match.group(1) if anchor_table_match else ""
            anchors = self._extract_table_anchors(docs, anchor_table_no)
            base_coverage = self._table_anchor_coverage_score(docs, anchors)
            anchor_threshold = max(1, len(anchors) // 2) if anchors else 0

            if anchors and base_coverage < anchor_threshold:
                combined_blob = "\n".join(
                    (d.page_content or "") for d in docs
                ).lower()
                missing_anchors = [a for a in anchors if a not in combined_blob]
                retry_queries = list(expanded_queries)
                if missing_anchors:
                    self._append_unique_search_query(
                        retry_queries,
                        f"{query} {' '.join(missing_anchors[:3])}",
                    )

                retry_docs = self._run_hybrid_retrieval(
                    query=query,
                    search_queries=retry_queries,
                    final_top_k=final_top_k,
                    vector_top_k=max(self.vector_top_k, final_top_k * 4),
                    bm25_top_k=max(self.bm25_top_k, final_top_k * 4),
                    literal_table_top_k=max(6, final_top_k * 2),
                    qdrant_filter=qdrant_filter,
                    doc_id=doc_id,
                )
                retry_coverage = self._table_anchor_coverage_score(retry_docs, anchors)

                if retry_coverage > base_coverage:
                    logger.info(
                        "[Retrieval] Table anchor coverage improved "
                        f"({base_coverage} -> {retry_coverage}); using retry results"
                    )
                    docs = retry_docs
                else:
                    logger.info(
                        "[Retrieval] Table anchor retry did not improve "
                        f"({base_coverage} -> {retry_coverage}); keeping initial results"
                    )

            table_match = re.search(
                r"\b(?:tabel|table)\s*(?:ke[-\s]*)?(\d{1,3})\b",
                query,
                re.IGNORECASE,
            )
            table_no = table_match.group(1) if table_match else None
            pre_filter_count = len(docs)
            docs = self._filter_table_noise_docs(docs, table_no=table_no, final_top_k=final_top_k)
            if len(docs) < pre_filter_count:
                logger.info(
                    "[Retrieval] Table-noise filter removed "
                    f"{pre_filter_count - len(docs)} index-like chunks"
                )

        logger.info(f"[Retrieval] Final selected chunks: {len(docs)}")

        # 3. Format context string (single source of truth)
        context = self._format_context(docs)
        logger.info(f"[Retrieval] Context ready ({len(context)} chars)")

        # 4. Build sources list for UI
        sources = []
        for i, doc in enumerate(docs, 1):
            meta = doc.metadata or {}
            doc_title = self._normalize_document_title(meta)
            citation_title = self._build_cover_citation_title(meta)
            # Build section dari hierarchy info yang tersedia
            # CATATAN: field pasal/ayat di Qdrant SUDAH berisi prefix ("Pasal 9", "Ayat (1)")
            # jadi jangan tambahkan prefix lagi untuk menghindari duplikat
            section_parts = []
            if meta.get("bab"): section_parts.append(str(meta["bab"]))
            if meta.get("bagian"): section_parts.append(str(meta["bagian"]))
            pasal_val = str(meta["pasal"]) if meta.get("pasal") else ""
            if pasal_val:
                section_parts.append(pasal_val if pasal_val.lower().startswith("pasal") else f"Pasal {pasal_val}")
            ayat_val = str(meta["ayat"]) if meta.get("ayat") else ""
            if ayat_val:
                section_parts.append(ayat_val if ayat_val.lower().startswith("ayat") else f"Ayat ({ayat_val})")
            section = (
                " > ".join(section_parts)
                or meta.get("context_header", "")
                or meta.get("hierarchy_path", "")
                or meta.get("hierarchy", "")
            )

            score = (
                meta.get("rerank_score")
                or meta.get("rrf_score")
                or meta.get("bm25_score")
                or 0.0
            )

            sources.append({
                "id": i,
                "document": citation_title,
                "document_short": doc_title,
                "citation_title": citation_title,
                "citation_label": f"[{i}] {citation_title}",
                "section": section,
                "pasal": str(meta.get("pasal") or ""),
                "ayat": str(meta.get("ayat") or ""),
                "context_header": str(meta.get("context_header") or ""),
                "hierarchy_path": str(meta.get("hierarchy_path") or ""),
                "score": float(score),
            })

        return {"context": context, "sources": sources, "raw_docs": docs, "query_type": query_type}

    def _format_context(self, docs: List[Document]) -> str:
        """Format documents into structured context string.
        
        Menggunakan field names yang sesuai dengan payload Qdrant:
        document_title, context_header, bab, bagian, pasal, ayat
        """
        if not docs:
            return "Tidak ada dokumen yang ditemukan."

        # Baris 1: Daftar sumber ringkas
        lines = ["DAFTAR SUMBER YANG TERSEDIA:"]
        for i, doc in enumerate(docs, 1):
            meta = doc.metadata or {}
            judul = self._build_cover_citation_title(meta)
            lines.append(f"[{i}] {judul}")

        lines.append(f"\nPENTING: Gunakan HANYA nomor sumber [1] sampai [{len(docs)}]. Jangan gunakan nomor lain.\n")
        lines.append("DETAIL DOKUMEN:\n")

        # Baris 2: Detail setiap dokumen
        for i, doc in enumerate(docs, 1):
            meta = doc.metadata or {}
            judul = self._build_cover_citation_title(meta)
            # Build lokasi spesifik dalam dokumen (sama — hindari duplikat prefix)
            loc_parts = []
            if meta.get("bab"): loc_parts.append(str(meta["bab"]))
            if meta.get("bagian"): loc_parts.append(str(meta["bagian"]))
            pasal_v = str(meta["pasal"]) if meta.get("pasal") else ""
            if pasal_v:
                loc_parts.append(pasal_v if pasal_v.lower().startswith("pasal") else f"Pasal {pasal_v}")
            ayat_v = str(meta["ayat"]) if meta.get("ayat") else ""
            if ayat_v:
                loc_parts.append(ayat_v if ayat_v.lower().startswith("ayat") else f"Ayat ({ayat_v})")
            lokasi = (
                " | ".join(loc_parts)
                or meta.get("context_header", "")
                or meta.get("hierarchy_path", "")
                or meta.get("hierarchy", "")
                or ""
            )

            ref = f"{judul} — {lokasi}" if lokasi else judul
            # page_content adalah isi teks chunk (field 'text' dari Qdrant via content_payload_key)
            isi = doc.page_content or ""
            parent_context = str(meta.get("parent_pasal_text") or "").strip()
            if parent_context and meta.get("ayat") and parent_context not in isi:
                if len(parent_context) > 1500:
                    parent_context = parent_context[:1500].rstrip() + "..."
                lines.append(
                    f"[{i}] Sumber: {ref}\nKonteks Pasal:\n{parent_context}\nIsi: {isi}\n---\n"
                )
            else:
                lines.append(f"[{i}] Sumber: {ref}\nIsi: {isi}\n---\n")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Chat History
    # ------------------------------------------------------------------

    def load_history(self, session_id: str) -> List:
        """Load chat history as LangChain message objects."""
        messages = []
        try:
            with SessionLocal() as db:
                rows = (
                    db.query(Conversation)
                    .filter(Conversation.session_id == session_id)
                    .order_by(Conversation.timestamp.asc())
                    .all()
                )
                for row in rows:
                    if row.role == "user":
                        messages.append(HumanMessage(content=row.content))
                    elif row.role == "assistant":
                        messages.append(AIMessage(content=row.content))
        except Exception as e:
            logger.error(f"[History] Failed to load for {session_id}: {e}")
        return messages

    # ------------------------------------------------------------------
    # Streaming LLM
    # ------------------------------------------------------------------

    async def stream_answer(
        self, query: str, context: str, history: List, model_name: str, query_type: str = "general"
    ) -> AsyncIterator[str]:
        """
        Stream LLM answer token by token.
        
        This is a simple async generator that yields string chunks directly.
        No LCEL, no opaque event routing — just direct llm.astream().
        """
        llm = self._get_llm(model_name)

        # Build messages list
        _PROMPT_MAP = {
            "table": SYSTEM_PROMPT_TABLE,
            "pasal": SYSTEM_PROMPT_LEGAL,
            "general": SYSTEM_PROMPT_GENERAL,
        }
        system_prompt = _PROMPT_MAP.get(query_type, SYSTEM_PROMPT_GENERAL)
        system_content = system_prompt + "\n\nKonteks Referensi:\n" + context
        messages = [SystemMessage(content=system_content)]
        messages.extend(history)

        quality_guardrail = self._build_quality_guardrail(query, context)
        user_content_parts = [f"Pertanyaan: {query}"]
        if quality_guardrail:
            user_content_parts.append(quality_guardrail)
        messages.append(HumanMessage(content="\n\n".join(user_content_parts)))

        logger.info(f"[LLM] Streaming {model_name} ({len(messages)} messages, context {len(context)} chars)...")

        token_count = 0
        async for chunk in llm.astream(messages):
            if chunk.content:
                token_count += 1
                yield chunk.content

        logger.info(f"[LLM] Done. Generated {token_count} tokens.")

    # ------------------------------------------------------------------
    # Document Ingestion (unchanged)
    # ------------------------------------------------------------------

    def add_documents(self, texts: List[str], metadatas: List[Dict[str, Any]]):
        """Add new chunks to the Qdrant vector store."""
        if not self._initialized:
            self.initialize()
        self.qdrant.add_texts(texts=texts, metadatas=metadatas)

    # Legacy compatibility
    def get_chain(self, model_name: str):
        """Legacy — returns self for backward compat. Use stream_answer() instead."""
        if not self._initialized:
            self.initialize()
        self._get_llm(model_name)
        return self


# Global instance
langchain_engine = LangchainRAGEngine()
