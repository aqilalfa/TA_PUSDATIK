#!/usr/bin/env python3
"""Build canonical SPBE ground truth with chunk-level reference IDs.

The source JSONL contains legal citations and quotes. This script enriches it
with IDs that match the retrievable chunk granularity currently available in the
local SQLite/Qdrant data: primarily SQLite chunk IDs (`dbchunk:<id>`) plus
stable-ish metadata fallbacks.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "ground_truth_spbe_rag.jsonl"
DEFAULT_OUTPUT = BACKEND / "data" / "ground_truth_spbe_ragas_canonical.jsonl"
DEFAULT_DB = BACKEND / "data" / "spbe_rag.db"


DOC_PATTERNS = [
    (re.compile(r"perpres\s+nomor\s+95\s+tahun\s+2018", re.I), "Perpres Nomor 95 Tahun 2018", "perpres95_2018"),
    (re.compile(r"permenpan\s+rb\s+nomor\s+59\s+tahun\s+2020", re.I), "Permenpan RB Nomor 59 Tahun 2020", "permenpan59_2020"),
    (re.compile(r"perpres\s+nomor\s+82\s+tahun\s+2023", re.I), "Perpres Nomor 82 Tahun 2023", "perpres82_2023"),
    (re.compile(r"peraturan\s+bssn\s+nomor\s+8\s+tahun\s+2024", re.I), "Peraturan BSSN Nomor 8 Tahun 2024", "bssn8_2024"),
    (re.compile(r"pp\s+nomor\s+71\s+tahun\s+2019", re.I), "PP Nomor 71 Tahun 2019", "pp71_2019"),
    (re.compile(r"peraturan\s+bssn\s+nomor\s+2\s+tahun\s+2023", re.I), "Peraturan BSSN Nomor 2 Tahun 2023", "bssn2_2023"),
    (re.compile(r"laporan\s+evaluasi\s+spbe\s+tahun\s+2024", re.I), "Laporan Evaluasi SPBE Tahun 2024", "lap_spbe2024"),
]


@dataclass
class ChunkCandidate:
    chunk_id: int
    document_id: int
    doc_id: str
    chunk_index: int
    text: str
    metadata: dict[str, Any]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9À-ÿ]+", normalize_space(text).lower()))


def detect_doc(source: str) -> tuple[str, str]:
    for pattern, canonical, slug in DOC_PATTERNS:
        if pattern.search(source or ""):
            return canonical, slug
    slug = re.sub(r"[^a-z0-9]+", "_", (source or "unknown").lower()).strip("_") or "unknown"
    return source or "unknown", slug[:60]


def extract_citation_parts(sitasi: str) -> dict[str, str]:
    text = sitasi or ""
    parts: dict[str, str] = {}
    patterns = {
        "pasal": r"Pasal\s+(\d+[A-Za-z]?)",
        "ayat": r"Ayat\s*\(?([\dA-Za-z]+)\)?",
        "angka": r"Angka\s+(\d+[A-Za-z]?)",
        "huruf": r"Huruf\s+([A-Za-z])",
        "tabel": r"Tabel\s+(\d+[A-Za-z]?)",
        "lampiran": r"Lampiran\s+([IVXLC]+|\d+)",
        "halaman": r"Halaman\s+([\d\-]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        if match:
            parts[key] = match.group(1)
    return parts


def citation_id(doc_slug: str, parts: dict[str, str]) -> str:
    segments = [doc_slug]
    if parts.get("lampiran"):
        segments.append(f"lamp{parts['lampiran'].lower()}")
    if parts.get("tabel"):
        segments.append(f"t{parts['tabel'].lower()}")
    if parts.get("pasal"):
        segments.append(f"p{parts['pasal'].lower()}")
    if parts.get("ayat"):
        segments.append(f"ay{parts['ayat'].lower()}")
    if parts.get("angka"):
        segments.append(f"a{parts['angka'].lower()}")
    if parts.get("huruf"):
        segments.append(f"h{parts['huruf'].lower()}")
    if parts.get("halaman"):
        segments.append(f"hal{parts['halaman'].lower()}")
    return ":".join(segments)


def load_chunks(db_path: Path) -> list[ChunkCandidate]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        select c.id as chunk_id, c.document_id, d.doc_id, c.chunk_index,
               c.chunk_text, c.chunk_metadata, d.original_filename, d.document_title
        from chunks c
        join documents d on d.id = c.document_id
        order by c.document_id, c.chunk_index
        """
    ).fetchall()
    chunks: list[ChunkCandidate] = []
    for row in rows:
        meta = json.loads(row["chunk_metadata"] or "{}")
        meta.setdefault("original_filename", row["original_filename"] or "")
        meta.setdefault("document_title", row["document_title"] or meta.get("judul_dokumen", ""))
        chunks.append(
            ChunkCandidate(
                chunk_id=int(row["chunk_id"]),
                document_id=int(row["document_id"]),
                doc_id=str(row["doc_id"] or row["document_id"]),
                chunk_index=int(row["chunk_index"]),
                text=row["chunk_text"] or "",
                metadata=meta,
            )
        )
    return chunks


def chunk_doc_slug(chunk: ChunkCandidate) -> str:
    blob = " ".join(
        str(chunk.metadata.get(k, ""))
        for k in ("filename", "original_filename", "document_title", "judul_dokumen", "tentang")
    )
    _, slug = detect_doc(blob)
    return slug


def chunk_context_id(chunk: ChunkCandidate) -> str:
    return f"dbchunk:{chunk.chunk_id}"


def score_chunk(item: dict[str, Any], chunk: ChunkCandidate, doc_slug: str, parts: dict[str, str]) -> float:
    source_doc, expected_slug = detect_doc(item.get("sumber_dokumen", ""))
    if doc_slug != expected_slug:
        return -1.0

    quote = item.get("kutipan_sumber") or item.get("jawaban") or ""
    quote_tokens = tokens(quote)
    chunk_tokens = tokens(chunk.text)
    overlap = len(quote_tokens & chunk_tokens) / max(len(quote_tokens), 1)

    meta_blob = normalize_space(" ".join(str(v) for v in chunk.metadata.values())).lower()
    bonus = 0.0
    if parts.get("pasal") and f"pasal {parts['pasal'].lower()}" in meta_blob:
        bonus += 0.25
    if parts.get("ayat") and str(parts["ayat"]).lower() in meta_blob:
        bonus += 0.08
    if parts.get("tabel") and f"tabel {parts['tabel'].lower()}" in meta_blob:
        bonus += 0.20
    if source_doc.lower() in meta_blob:
        bonus += 0.05

    return overlap + bonus


def best_reference_chunks(item: dict[str, Any], chunks: list[ChunkCandidate], max_refs: int = 3) -> list[dict[str, Any]]:
    _, doc_slug = detect_doc(item.get("sumber_dokumen", ""))
    parts = extract_citation_parts(item.get("sitasi", ""))
    scored = []
    for chunk in chunks:
        score = score_chunk(item, chunk, chunk_doc_slug(chunk), parts)
        if score >= 0:
            scored.append((score, chunk))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    refs = []
    for score, chunk in scored[:max_refs]:
        if score <= 0:
            continue
        refs.append(
            {
                "context_id": chunk_context_id(chunk),
                "score": round(float(score), 4),
                "document_id": chunk.document_id,
                "doc_id": chunk.doc_id,
                "chunk_index": chunk.chunk_index,
                "metadata": chunk.metadata,
                "text_preview": normalize_space(chunk.text)[:300],
            }
        )
    return refs


def convert_item(item: dict[str, Any], chunks: list[ChunkCandidate]) -> dict[str, Any]:
    source_doc, doc_slug = detect_doc(item.get("sumber_dokumen", ""))
    parts = extract_citation_parts(item.get("sitasi", ""))
    fallback_citation_id = citation_id(doc_slug, parts)
    refs = best_reference_chunks(item, chunks)
    reference_context_ids = [ref["context_id"] for ref in refs] or [fallback_citation_id]

    return {
        "id": item.get("id"),
        "user_input": item.get("pertanyaan"),
        "reference": item.get("jawaban"),
        "reference_contexts": [item.get("kutipan_sumber") or item.get("jawaban", "")],
        "reference_context_ids": reference_context_ids,
        "reference_citation_id": fallback_citation_id,
        "reference_chunk_matches": refs,
        "expected_citations": [
            {
                "sumber_dokumen": source_doc,
                "sitasi": item.get("sitasi"),
                "sitasi_full": item.get("sitasi_full"),
                "halaman_pdf": item.get("halaman_pdf"),
                "pdf_page_start": item.get("pdf_page_start"),
                "pdf_page_end": item.get("pdf_page_end"),
                "kutipan": item.get("kutipan_sumber"),
                **parts,
            }
        ],
        "metadata": {
            "jenis": item.get("jenis"),
            "jenis_dokumen": "laporan" if doc_slug.startswith("lap_") else "peraturan",
            "sumber_dokumen": source_doc,
            "sumber_slug": doc_slug,
            "sitasi": item.get("sitasi"),
            "halaman_pdf": item.get("halaman_pdf"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build canonical SPBE RAGAS/retrieval ground truth")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    items = load_jsonl(args.input)
    chunks = load_chunks(args.db)
    converted = [convert_item(item, chunks) for item in items]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in converted) + "\n",
        encoding="utf-8",
    )

    matched = sum(1 for item in converted if item.get("reference_chunk_matches"))
    print(f"Wrote {len(converted)} rows → {args.output}")
    print(f"Rows with DB chunk match: {matched}/{len(converted)}")


if __name__ == "__main__":
    main()
