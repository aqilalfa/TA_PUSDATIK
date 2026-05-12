import re
import time
from typing import List, Dict, Any, Optional
from loguru import logger
from langchain_core.documents import Document

class RAGRanker:
    def __init__(self, reranker_instance=None):
        self._reranker = reranker_instance

    def rrf_fusion(self, ranked_lists: List[List[Document]], max_candidates: int, k: int = 60) -> List[Document]:
        """Perform Reciprocal Rank Fusion on multiple ranked lists."""
        scores: Dict[str, float] = {}
        docs: Dict[str, Document] = {}

        for ranked_list in ranked_lists:
            for rank, doc in enumerate(ranked_list):
                # Use page_content + doc_id as unique key
                doc_id = str(doc.metadata.get("document_id") or doc.metadata.get("doc_id") or "none")
                content_hash = str(hash(doc.page_content))
                key = f"{doc_id}_{content_hash}"
                
                score = 1.0 / (k + rank + 1)
                scores[key] = scores.get(key, 0.0) + score
                if key not in docs:
                    docs[key] = doc

        # Sort by score
        fused = sorted(docs.keys(), key=lambda k: scores[k], reverse=True)
        
        results = []
        for key in fused[:max_candidates]:
            doc = docs[key]
            doc.metadata["rrf_score"] = scores[key]
            results.append(doc)
            
        return results

    def query_metadata_boost(self, query: str, metadata: Dict[str, Any], text: str = "") -> float:
        """
        Apply detailed query-aware metadata boost from legacy engine.
        Essential for legal document accuracy (Perpres, Permen, Pasal, Indikator).
        """
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

        # Regulation Type Boosts
        if "perpres" in q and ("peraturan presiden" in doc_blob or "perpres" in doc_blob):
            boost += 0.25
        if "permen" in q and ("peraturan menteri" in doc_blob or "permen" in doc_blob):
            boost += 0.25
        if "pp " in q and ("peraturan pemerintah" in doc_blob or " pp " in f" {doc_blob} "):
            boost += 0.25

        # ID/Number Matchers
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

        # Pasal/Ayat Matchers
        pasal_match = re.search(r"pasal\s+(\d+)", q)
        if pasal_match:
            pasal_no = pasal_match.group(1)
            if re.search(rf"\bpasal\s+{re.escape(pasal_no)}\b", pasal_meta):
                boost += 0.55
            elif re.search(rf"\bpasal\s+{re.escape(pasal_no)}\b", doc_blob):
                boost += 0.20

        # Indicator Matchers (SPBE Specific)
        indicator_match = re.search(r"\b(?:indikator|id)\s*(?:ke[-\s]*)?(\d{1,3})\b", q)
        if indicator_match:
            ind_no = indicator_match.group(1)
            hierarchy_meta = str(meta.get("hierarchy", "") or "").lower()

            # Highest boost: chunk's hierarchy explicitly names this indicator
            if re.search(rf"\bindikator\s+{re.escape(ind_no)}\b", hierarchy_meta):
                boost += 2.0  # Definitive indicator chunk

            # Strong boost: indicator number appears in text/blob
            elif re.search(rf"\bindikator\s*{re.escape(ind_no)}\b", doc_blob) or \
               re.search(rf"\bid[- \t]*{re.escape(ind_no)}\b", doc_blob):
                boost += 0.85

            # Context bonus: document is about SPBE
            if "spbe" in doc_blob:
                boost += 0.15

        # Table-sensitive Matcher
        table_match = re.search(r"\b(?:tabel|table)\s*(?:ke[-\s]*)?(\d{1,3})\b", q)
        if table_match:
            table_no = table_match.group(1)
            if re.search(rf"\btabel\s*(?:ke[-\s]*)?{re.escape(table_no)}\b", doc_blob):
                boost += 1.35
            elif "tabel" in doc_blob:
                boost += 0.20

            if metadata.get("is_table"):
                boost += 0.40
            
            label = str(metadata.get("table_label", "") or "").lower()
            if label and f"tabel {table_no}" in label:
                boost += 0.25

        # Definition Matcher
        if "definisi" in q or "pengertian" in q:
            if re.search(r"\bpasal\s+1\b", pasal_meta):
                boost += 0.55
                if "bab i" in bab_meta or "ketentuan umum" in doc_blob:
                    boost += 1.10
            if "yang dimaksud dengan" in doc_blob:
                boost += 0.90
            if "selanjutnya disingkat spbe adalah" in doc_blob:
                boost += 1.00

        return boost

    def rerank(self, query: str, docs: List[Document], top_k: int) -> List[Document]:
        """Rerank documents using CrossEncoder + Metadata Heuristics."""
        if not docs:
            return []

        try:
            t_start = time.perf_counter()
            
            # 1. Base scores from CrossEncoder if available
            scored_docs = []
            if self._reranker:
                pairs = [[query, (doc.page_content or "")[:3000]] for doc in docs]
                ce_scores = self._reranker.predict(pairs)
                for i, score in enumerate(ce_scores):
                    scored_docs.append({"score": float(score), "doc": docs[i]})
            else:
                # Fallback to RRF score if no reranker
                for doc in docs:
                    scored_docs.append({"score": doc.metadata.get("rrf_score", 0.0), "doc": doc})

            # 2. Apply Domain Heuristic Boosting
            final_ranked = []
            for item in scored_docs:
                doc = item["doc"]
                meta_boost = self.query_metadata_boost(query, doc.metadata, doc.page_content)
                final_score = item["score"] + meta_boost
                
                doc.metadata["rerank_base_score"] = item["score"]
                doc.metadata["query_boost"] = float(meta_boost)
                doc.metadata["rerank_score"] = float(final_score)
                final_ranked.append((final_score, doc))

            final_ranked.sort(key=lambda x: x[0], reverse=True)
            
            logger.info(f"[Rerank] Boosted {len(docs)} candidates in {time.perf_counter()-t_start:.3f}s")
            return [doc for _, doc in final_ranked[:top_k]]
            
        except Exception as e:
            logger.error(f"[Rerank] Failed: {e}")
            return docs[:top_k]
