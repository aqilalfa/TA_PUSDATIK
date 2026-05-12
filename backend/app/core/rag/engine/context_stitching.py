from typing import List, Dict, Any, Optional, Tuple, Set
from loguru import logger
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

from app.core.rag.utils import safe_int, longest_suffix_prefix_overlap

class ContextStitcher:
    def __init__(self, qdrant_client: QdrantClient):
        self.client = qdrant_client

    def fetch_neighbor_documents(
        self, 
        centers_by_doc: Dict[str, Set[int]], 
        collection_name: str
    ) -> List[Document]:
        """Fetch ±1 neighboring chunks for primary documents from Qdrant."""
        if not centers_by_doc:
            return []

        should_conditions = []
        for doc_id, indices in centers_by_doc.items():
            doc_neighbors = set()
            for idx in indices:
                if idx > 0:
                    doc_neighbors.add(idx - 1)
                doc_neighbors.add(idx + 1)
            
            # Remove original indices only for THIS document
            doc_neighbors -= indices
            
            if doc_neighbors:
                should_conditions.append(
                    Filter(must=[
                        FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
                        FieldCondition(key="chunk_index", match=MatchAny(any=list(doc_neighbors)))
                    ])
                )

        if not should_conditions:
            return []

        try:
            points, _ = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(should=should_conditions),
                limit=100,
                with_payload=True,
                with_vectors=False
            )
            
            docs = []
            for p in points:
                payload = p.payload  # flat Qdrant payload — no 'payload.' nesting (confirmed by retrievers.py)
                # Tag these as neighbors for merging logic
                # Find which center this belongs to
                doc_id = payload.get("doc_id")
                idx = safe_int(payload.get("chunk_index"))
                
                # Check if it's a neighbor of any center in that doc
                centers = centers_by_doc.get(doc_id, set())
                neighbor_of = -1
                if (idx + 1) in centers: neighbor_of = idx + 1
                elif (idx - 1) in centers: neighbor_of = idx - 1
                
                if neighbor_of != -1:
                    payload["_neighbor_of_chunk_index"] = neighbor_of
                    docs.append(Document(page_content=payload.get("text", ""), metadata=payload))
            return docs
        except Exception as e:
            logger.error(f"[NeighborFetch] Failed: {e}")
            return []

    def merge_text_parts(self, parts: List[str]) -> str:
        """Merge neighboring chunk texts while resolving duplicated overlaps."""
        if not parts:
            return ""
        
        merged = parts[0]
        for part in parts[1:]:
            if part in merged:
                continue
            
            overlap = longest_suffix_prefix_overlap(merged, part)
            if overlap > 0:
                merged += part[overlap:]
            else:
                # Add newline separator if no overlap found
                merged += "\n" + part
        return merged

    def expand_docs_with_neighbor_context(
        self, 
        primary_docs: List[Document], 
        collection_name: str
    ) -> List[Document]:
        """Combine primary documents with their ±1 neighbors for fuller context."""
        if not primary_docs:
            return []

        # 1. Map center docs
        centers_by_doc: Dict[str, Set[int]] = {}
        for doc in primary_docs:
            meta = doc.metadata or {}
            doc_id = str(meta.get("doc_id") or "").strip()
            chunk_index = safe_int(meta.get("chunk_index"))
            if not doc_id or chunk_index is None:
                continue
            centers_by_doc.setdefault(doc_id, set()).add(chunk_index)

        # 2. Fetch neighbors
        neighbor_docs = self.fetch_neighbor_documents(centers_by_doc, collection_name)
        
        # 3. Group by center
        neighbors_by_anchor: Dict[Tuple[str, int], List[Document]] = {}
        for ndoc in neighbor_docs:
            nmeta = ndoc.metadata or {}
            doc_id = str(nmeta.get("doc_id") or "").strip()
            anchor = safe_int(nmeta.get("_neighbor_of_chunk_index"))
            if not doc_id or anchor is None:
                continue
            neighbors_by_anchor.setdefault((doc_id, anchor), []).append(ndoc)

        # 4. Stitch
        stitched_docs = []
        for pdoc in primary_docs:
            pmeta = dict(pdoc.metadata or {})
            doc_id = str(pmeta.get("doc_id") or "").strip()
            center_idx = safe_int(pmeta.get("chunk_index"))

            if not doc_id or center_idx is None:
                stitched_docs.append(pdoc)
                continue

            # Find its neighbors
            neighbors = neighbors_by_anchor.get((doc_id, center_idx), [])
            if not neighbors:
                stitched_docs.append(pdoc)
                continue

            # Sort: previous, center, next
            parts = neighbors + [pdoc]
            unique_by_index: Dict[int, Document] = {}
            for part in parts:
                idx = safe_int((part.metadata or {}).get("chunk_index"))
                if idx is None: continue
                if idx not in unique_by_index:
                    unique_by_index[idx] = part
            
            sorted_indices = sorted(unique_by_index.keys())
            sorted_texts = [unique_by_index[idx].page_content for idx in sorted_indices]
            
            # Merge
            merged_text = self.merge_text_parts(sorted_texts)
            
            # Create new doc with merged text
            # Keep original metadata but update merged flag
            pmeta["is_stitched"] = True
            pmeta["original_chunk_index"] = center_idx
            pmeta["stitched_indices"] = sorted_indices
            
            stitched_docs.append(Document(page_content=merged_text, metadata=pmeta))

        return stitched_docs
