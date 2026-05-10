#!/usr/bin/env python3
"""Check alignment between source PDF structure and stored chunks for one document."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pdfplumber

from app.database import SessionLocal
from app.models.db_models import Chunk, Document


PATTERNS = {
    "bab": re.compile(r"\bBAB\s+[IVXLCDM0-9]+\b", re.IGNORECASE),
    "pasal": re.compile(r"\bPasal\s+\d+\b", re.IGNORECASE),
    "domain": re.compile(r"\bDomain\s+\d+\b", re.IGNORECASE),
    "indikator": re.compile(r"\bIndikator\s+\d+\b", re.IGNORECASE),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate source PDF vs chunk alignment for one document"
    )
    parser.add_argument("--doc-id", type=int, required=True, help="SQLite document id")
    parser.add_argument(
        "--api-base",
        default="http://127.0.0.1:8000",
        help="Backend API base URL",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=200,
        help="Chunk page size for API pagination",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional path to save JSON report",
    )
    return parser.parse_args()


def resolve_source_pdf(doc: Document) -> Optional[Path]:
    candidates: List[Path] = []

    if doc.original_path:
        candidates.append(Path(doc.original_path))
    if doc.file_path:
        candidates.append(Path(doc.file_path))

    repo_root = Path(__file__).resolve().parents[2]
    if doc.filename:
        candidates.append(repo_root / "data" / "documents" / "peraturan" / doc.filename)
        candidates.append(repo_root / "data" / "documents" / "audit" / doc.filename)
        candidates.extend((repo_root / "data" / "documents").rglob(doc.filename))

    seen = set()
    deduped: List[Path] = []
    for p in candidates:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)

    for p in deduped:
        if p.exists() and p.is_file():
            return p
    return None


def extract_pdf_text(pdf_path: Path) -> str:
    parts: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def count_markers(text: str) -> Dict[str, int]:
    return {name: len(pattern.findall(text or "")) for name, pattern in PATTERNS.items()}


def extract_bab_labels(text: str) -> List[str]:
    labels = PATTERNS["bab"].findall(text or "")
    normalized = sorted({label.upper().strip() for label in labels})
    return normalized


def normalize_bab_label(label: str) -> str:
    match = re.search(r"\bBAB\s+([IVXLCDM0-9]+)\b", label or "", re.IGNORECASE)
    if not match:
        return ""
    return f"BAB {match.group(1).upper()}"


def fetch_all_chunks(api_base: str, doc_id: int, page_size: int) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    offset = 0

    with httpx.Client(timeout=30) as client:
        while True:
            resp = client.get(
                f"{api_base}/api/documents/{doc_id}/chunks",
                params={"limit": page_size, "offset": offset},
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break

            chunks.extend(batch)
            if len(batch) < page_size:
                break

            offset += len(batch)

    return chunks


def summarize_alignment(
    doc: Document,
    db_chunk_count: int,
    source_path: Path,
    source_text: str,
    api_chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    joined_chunk_text = "\n".join((c.get("text") or "") for c in api_chunks)

    source_counts = count_markers(source_text)
    chunk_text_counts = count_markers(joined_chunk_text)

    meta_non_empty = {
        "bab": sum(1 for c in api_chunks if str(c.get("bab", "") or "").strip()),
        "pasal": sum(1 for c in api_chunks if str(c.get("pasal", "") or "").strip()),
        "domain": sum(1 for c in api_chunks if str(c.get("domain", "") or "").strip()),
        "indikator": sum(1 for c in api_chunks if str(c.get("indikator", "") or "").strip()),
    }

    source_bab_labels = extract_bab_labels(source_text)
    chunk_bab_labels = sorted(
        {
            str(c.get("bab") or "").upper().strip()
            for c in api_chunks
            if str(c.get("bab") or "").strip()
        }
    )

    source_bab_labels_normalized = sorted(
        {
            normalize_bab_label(label)
            for label in source_bab_labels
            if normalize_bab_label(label)
        }
    )
    chunk_bab_labels_normalized = sorted(
        {
            normalize_bab_label(label)
            for label in chunk_bab_labels
            if normalize_bab_label(label)
        }
    )
    missing_bab_labels = sorted(
        set(source_bab_labels_normalized) - set(chunk_bab_labels_normalized)
    )

    bab_status = "ok"
    if source_counts["bab"] > 0 and meta_non_empty["bab"] == 0:
        bab_status = "missing"
    elif missing_bab_labels:
        bab_status = "partial"

    overall_status = "ok" if bab_status == "ok" else "needs_review"

    return {
        "document": {
            "id": doc.id,
            "filename": doc.filename,
            "status": doc.status,
            "doc_type": doc.doc_type,
            "db_chunk_count": db_chunk_count,
            "api_chunk_count": len(api_chunks),
            "source_pdf": str(source_path),
        },
        "source_marker_counts": source_counts,
        "chunk_text_marker_counts": chunk_text_counts,
        "chunk_metadata_non_empty": meta_non_empty,
        "source_bab_labels": source_bab_labels,
        "chunk_bab_labels": chunk_bab_labels,
        "source_bab_labels_normalized": source_bab_labels_normalized,
        "chunk_bab_labels_normalized": chunk_bab_labels_normalized,
        "missing_bab_labels": missing_bab_labels,
        "assessment": {
            "bab_alignment": bab_status,
            "overall": overall_status,
        },
        "sample_chunks": [
            {
                "chunk_index": c.get("chunk_index"),
                "bab": c.get("bab"),
                "pasal": c.get("pasal"),
                "text_prefix": (c.get("text") or "")[:180].replace("\n", " "),
            }
            for c in api_chunks[:10]
        ],
    }


def main() -> int:
    args = parse_args()

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == args.doc_id).first()
        if not doc:
            raise ValueError(f"Document id={args.doc_id} not found")

        db_chunk_count = db.query(Chunk).filter(Chunk.document_id == doc.id).count()

        source_path = resolve_source_pdf(doc)
        if not source_path:
            raise ValueError(
                f"Unable to resolve source PDF path for doc id={doc.id}, filename={doc.filename}"
            )

        source_text = extract_pdf_text(source_path)
        api_chunks = fetch_all_chunks(args.api_base.rstrip("/"), doc.id, args.page_size)

        report = summarize_alignment(
            doc=doc,
            db_chunk_count=db_chunk_count,
            source_path=source_path,
            source_text=source_text,
            api_chunks=api_chunks,
        )

        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        print(rendered)

        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8")
            print(f"\nReport saved to: {out_path}")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
