"""Export LLM09 responses with full retrieved chunk text.

Fetches full chunk text from Qdrant vector store payload for each source snippet
and writes JSON files formatted with response_id and sources (with full_chunk_text).
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List
from qdrant_client import QdrantClient
from app.config import settings


def clean_snippet(snippet: str) -> str:
    """Remove leading/trailing ellipsis or whitespace from snippet for matching."""
    s = snippet.strip()
    if s.startswith("..."):
        s = s[3:].strip()
    if s.endswith("..."):
        s = s[:-3].strip()
    if s.startswith("…"):
        s = s[1:].strip()
    if s.endswith("…"):
        s = s[:-1].strip()
    return s


def build_chunk_corpus() -> List[Dict[str, Any]]:
    """Scroll all points from Qdrant to get full text and metadata."""
    url = settings.QDRANT_URL.replace("localhost", "127.0.0.1")
    client = QdrantClient(url=url, timeout=30)
    collection_name = settings.QDRANT_COLLECTION
    
    chunks = []
    offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=collection_name,
            limit=200,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for pt in points:
            payload = pt.payload or {}
            chunks.append({
                "chunk_id": pt.id,
                "text": payload.get("text", ""),
                "doc_id": str(payload.get("doc_id") or payload.get("document_id") or ""),
                "document_title": payload.get("judul_dokumen") or payload.get("document_title") or payload.get("filename") or "",
                "hierarchy": payload.get("hierarchy") or "",
                "pasal": payload.get("pasal") or "",
                "bab": payload.get("bab") or "",
                "bagian": payload.get("bagian") or "",
            })
        if not next_offset:
            break
        offset = next_offset
        
    print(f"[Qdrant] Loaded {len(chunks)} chunks into memory.")
    return chunks


def normalize_ws(text: str) -> str:
    """Normalize all newlines and whitespace sequences to single space for robust matching."""
    return re.sub(r"\s+", " ", text).strip()


def find_full_chunk_text(source: Dict[str, Any], corpus: List[Dict[str, Any]]) -> str:
    """Find the exact full_chunk_text matching a source dictionary."""
    snippet = source.get("snippet", "")
    if not snippet:
        return ""
    
    cleaned = clean_snippet(snippet)
    source_doc_id = str(source.get("doc_id", ""))
    source_sec = normalize_ws(source.get("section", ""))
    source_hier = normalize_ws(source.get("hierarchy", ""))
    norm_snippet = normalize_ws(cleaned)
    
    # 1. Try exact normalized substring match with doc_id filter
    for chunk in corpus:
        if source_doc_id and chunk["doc_id"] != source_doc_id:
            continue
        if norm_snippet in normalize_ws(chunk["text"]):
            return chunk["text"]
            
    # 2. Try prefix matching (first 30 chars of normalized snippet)
    prefix = norm_snippet[:30]
    if len(prefix) >= 10:
        for chunk in corpus:
            if source_doc_id and chunk["doc_id"] != source_doc_id:
                continue
            if prefix in normalize_ws(chunk["text"]):
                return chunk["text"]

    # 3. Try exact normalized substring match across all docs
    for chunk in corpus:
        if norm_snippet in normalize_ws(chunk["text"]):
            return chunk["text"]
            
    # 4. Try prefix match across all docs
    if len(prefix) >= 10:
        for chunk in corpus:
            if prefix in normalize_ws(chunk["text"]):
                return chunk["text"]

    # 5. Match by doc_id + section/hierarchy/pasal
    for chunk in corpus:
        if source_doc_id and chunk["doc_id"] == source_doc_id:
            chunk_pasal = normalize_ws(chunk.get("pasal", ""))
            chunk_hier = normalize_ws(chunk.get("hierarchy", ""))
            if (chunk_pasal and chunk_pasal in source_sec) or (chunk_hier and chunk_hier in source_hier):
                return chunk["text"]

    # Fallback to snippet if no match found
    print(f"[Warning] Could not find full chunk match for snippet starting with: {cleaned[:30]!r}")
    return snippet


def process_response_file(input_file: Path, output_file: Path, corpus: List[Dict[str, Any]]) -> None:
    """Read LLM09 response JSON, find full chunk text for each source, and export formatted JSON."""
    if not input_file.exists():
        print(f"[Skip] Input file {input_file} does not exist.")
        return
        
    records = json.loads(input_file.read_text(encoding="utf-8"))
    formatted_output: List[Dict[str, Any]] = []
    
    for item in records:
        resp_id = item.get("id", "")
        raw_sources = item.get("response", {}).get("sources", []) if item.get("response") else []
        
        formatted_sources: List[Dict[str, Any]] = []
        for idx, src in enumerate(raw_sources, 1):
            full_text = find_full_chunk_text(src, corpus)
            formatted_sources.append({
                "id": src.get("id", idx),
                "document": src.get("document", ""),
                "section": src.get("section", ""),
                "full_chunk_text": full_text
            })
            
        formatted_output.append({
            "response_id": resp_id,
            "sources": formatted_sources
        })
        
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(formatted_output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[Success] Wrote {len(formatted_output)} record(s) to {output_file}")


def main():
    corpus = build_chunk_corpus()
    reports_dir = Path(__file__).resolve().parents[1] / "reports" / "llm09"
    
    files_to_process = [
        ("llm09_holdout_responses.json", "llm09_holdout_full_context.json"),
        ("llm09_live_responses.json", "llm09_live_full_context.json"),
        ("llm09_guard_smoke.json", "llm09_guard_smoke_full_context.json"),
    ]
    
    for in_name, out_name in files_to_process:
        in_path = reports_dir / in_name
        out_path = reports_dir / out_name
        process_response_file(in_path, out_path, corpus)


if __name__ == "__main__":
    main()
