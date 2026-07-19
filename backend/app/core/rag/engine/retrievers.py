import re
from typing import List, Optional, Dict, Any, Tuple, cast
from loguru import logger
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny, MatchValue, MatchText
from langchain_qdrant import QdrantVectorStore

from app.core.rag.utils import safe_int
from app.core.rag.access_control import ADMIN_ROLE, NO_MATCH_ROLE, parse_user_roles, user_can_access_metadata


def _role_access_condition(current_user=None):
    roles = parse_user_roles(current_user)
    if current_user is not None and not roles:
        return FieldCondition(key="allowed_roles", match=MatchAny(any=[NO_MATCH_ROLE]))
    if roles and ADMIN_ROLE not in roles:
        return FieldCondition(key="allowed_roles", match=MatchAny(any=roles))
    return None

class HybridRetriever:
    def __init__(self, qdrant_client: QdrantClient, vector_store: QdrantVectorStore, bm25_instance=None):
        self.client = qdrant_client
        self.qdrant = vector_store
        self._bm25 = bm25_instance

    def vector_search(self, query: str, top_k: int, qdrant_filter=None) -> List[Document]:
        """Perform vector search using Qdrant directly to preserve flat payload metadata."""
        try:
            query_vector = self.qdrant.embeddings.embed_query(query)
            response = self.client.query_points(
                collection_name=self.qdrant.collection_name,
                query=query_vector,
                query_filter=qdrant_filter,
                limit=top_k,
                with_payload=True
            )
            docs = []
            for p in response.points:
                payload = p.payload.copy() if p.payload else {}
                text = payload.pop("text", "")
                # Ensure document_id is available for downstream rankers/stitchers
                docs.append(Document(page_content=text, metadata=payload))
            return docs
        except Exception as e:
            logger.error(f"[VectorSearch] Failed: {e}")
            raise RuntimeError("Vector search failed") from e

    def bm25_search(
        self,
        query: str,
        top_k: int,
        bm25_docs: List[Dict[str, Any]],
        doc_id: Optional[str] = None,
        current_user=None,
    ) -> List[Document]:
        """Perform keyword search using BM25 (local)."""
        if not self._bm25 or not bm25_docs:
            return []
        
        try:
            # Tokenize query
            tokenized_query = query.lower().split()
            scores = self._bm25.get_scores(tokenized_query)
            
            # Create pairs and sort
            doc_scores = []
            for i, score in enumerate(scores):
                if score <= 0: continue
                
                # Filter by doc_id if provided
                if doc_id:
                    meta = bm25_docs[i].get("metadata", {})
                    # Support both document_id (integer-based) and doc_id (UUID-based)
                    match_val = meta.get("document_id") or meta.get("doc_id")
                    if str(match_val) != str(doc_id):
                        continue

                meta = bm25_docs[i].get("metadata", {})
                if current_user is not None and not user_can_access_metadata(meta, current_user):
                    continue
                         
                doc_scores.append((score, bm25_docs[i]))
            
            doc_scores.sort(key=lambda x: x[0], reverse=True)
            
            results = []
            for score, doc_data in doc_scores[:top_k]:
                doc = Document(
                    page_content=doc_data["text"],
                    metadata={**doc_data["metadata"], "bm25_score": float(score)}
                )
                results.append(doc)
            return results
        except Exception as e:
            logger.error(f"[BM25] Search failed: {e}")
            raise RuntimeError("BM25 search failed") from e

    def table_literal_search(
        self, 
        query: str, 
        collection_name: str,
        doc_id: Optional[str] = None,
        current_user=None,
    ) -> List[Document]:
        """
        Specialized search for table numbers (e.g., 'tabel 10').
        Bypasses embeddings to find exact table identifiers.
        """
        match = re.search(r"\b(?:tabel|table)\s*(?:ke[-\s]*)?(\d{1,3})\b", query, re.IGNORECASE)
        if not match:
            return []

        table_no = match.group(1)
        logger.info(f"[LiteralSearch] Attempting exact match for Table {table_no}")

        # NOTE: Qdrant payload has NO 'payload.' wrapper — fields are top-level
        must_conditions: list[Any] = [
            FieldCondition(key="table_context", match=MatchValue(value=f"Tabel {table_no}"))
        ]
        if doc_id:
            must_conditions.append(FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id))))
        role_condition = _role_access_condition(current_user)
        if role_condition is not None:
            must_conditions.append(role_condition)

        try:
            points, _ = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(must=must_conditions),
                limit=5,
                with_payload=True,
                with_vectors=False
            )
            
            docs = []
            for p in points:
                # Top-level payload — no 'payload' or 'metadata' nesting
                payload = cast(dict[str, Any], p.payload or {})
                docs.append(Document(
                    page_content=str(payload.get("text", "")),
                    metadata={**payload, "literal_match": True, "score": 2.0}
                ))
            return docs
        except Exception as e:
            logger.error(f"[LiteralSearch] Failed: {e}")
            raise RuntimeError("Table literal search failed") from e

    def indicator_literal_search(
        self, 
        query: str, 
        collection_name: str,
        doc_id: Optional[str] = None,
        current_user=None,
    ) -> List[Document]:
        """
        Specialized search for indicator numbers (e.g., 'Indikator 21').
        Searches in metadata.hierarchy which is where indicator labels are stored.
        """
        match = re.search(r"\b(?:indikator|id)\s*(?:ke[-\s]*)?(\d{1,3})\b", query, re.IGNORECASE)
        if not match:
            return []

        ind_no = match.group(1)
        logger.info(f"[LiteralSearch] Attempting match for Indicator {ind_no} in hierarchy")

        # Try several field variations — hierarchy is the most reliable
        # NOTE: Qdrant payload has NO 'metadata.' wrapper — fields are top-level
        search_targets = [
            ("hierarchy", f"Indikator {ind_no}:"),   # e.g. "Indikator 21:"
            ("hierarchy", f"Indikator {ind_no} "),   # trailing space variant
            ("context_header", f"Indikator {ind_no}"),
        ]

        docs = []
        seen_ids = set()
        failed_targets = 0
        for field, value in search_targets:
            if len(docs) >= 5:
                break
            must_conditions: list[Any] = [FieldCondition(key=field, match=MatchText(text=value))]
            if doc_id:
                must_conditions.append(FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id))))
            role_condition = _role_access_condition(current_user)
            if role_condition is not None:
                must_conditions.append(role_condition)
            try:
                points, _ = self.client.scroll(
                    collection_name=collection_name,
                    scroll_filter=Filter(must=must_conditions),
                    limit=5,
                    with_payload=True,
                    with_vectors=False
                )
                for p in points:
                    pid = str(p.id)
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)
                    point_payload = cast(dict[str, Any], p.payload or {})
                    nested_metadata = point_payload.get("metadata")
                    payload = nested_metadata if isinstance(nested_metadata, dict) else point_payload
                    docs.append(Document(
                        page_content=str(point_payload.get("text", "")),
                        metadata={**payload, "literal_match": True, "score": 2.5}
                    ))
            except Exception as e:
                logger.warning(f"[LiteralSearch] field={field} failed: {e}")
                failed_targets += 1
                continue

        if failed_targets == len(search_targets):
            raise RuntimeError("Indicator literal search failed for all metadata targets")
        logger.info(f"[LiteralSearch] Found {len(docs)} indicator literal matches")
        return docs
