#!/usr/bin/env python3
"""Evaluate retrieval without LLM judge using reference/retrieved context IDs."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if callable(stdout_reconfigure):
    stdout_reconfigure(encoding="utf-8")

from app.core.rag.langchain_engine import langchain_engine
from app.core.rag.context_ids import enrich_context_identity


BACKEND = Path(__file__).resolve().parents[1]
DEFAULT_GT = BACKEND / "data" / "ground_truth_spbe_ragas_canonical.jsonl"
DEFAULT_REPORT = BACKEND / "data" / "eval_retrieval_ids_report.json"
DEFAULT_K = [1, 3, 5, 10]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9À-ÿ]+", normalize_space(text).lower()))


def doc_slug_from_metadata(meta: dict[str, Any]) -> str:
    blob = " ".join(str(meta.get(k, "")) for k in ("filename", "document", "document_short", "document_title", "judul_dokumen", "tentang"))
    low = blob.lower()
    if "95" in low and "2018" in low and ("perpres" in low or "presiden" in low):
        return "perpres95_2018"
    if "59" in low and "2020" in low:
        return "permenpan59_2020"
    if "82" in low and "2023" in low:
        return "perpres82_2023"
    if "bssn" in low and "8" in low and "2024" in low:
        return "bssn8_2024"
    if "71" in low and "2019" in low:
        return "pp71_2019"
    if "bssn" in low and "2" in low and "2023" in low:
        return "bssn2_2023"
    if "laporan" in low and "2024" in low:
        return "lap_spbe2024"
    return re.sub(r"[^a-z0-9]+", "_", low).strip("_")[:60] or "unknown"


def retrieved_context_id(meta: dict[str, Any]) -> str:
    meta = enrich_context_identity(meta)
    if meta.get("canonical_context_id"):
        return str(meta["canonical_context_id"])
    if meta.get("chunk_id"):
        return f"dbchunk:{meta['chunk_id']}"
    if meta.get("document_id") and meta.get("chunk_index") is not None:
        return f"doc{meta['document_id']}:idx{meta['chunk_index']}"
    if meta.get("doc_id") and meta.get("chunk_index") is not None:
        return f"doc{meta['doc_id']}:idx{meta['chunk_index']}"
    slug = doc_slug_from_metadata(meta)
    section = meta.get("context_header") or meta.get("hierarchy") or meta.get("pasal") or ""
    section_slug = re.sub(r"[^a-z0-9]+", "_", str(section).lower()).strip("_")[:80]
    return f"{slug}:{section_slug or 'unknown'}"


def context_aliases(meta: dict[str, Any]) -> set[str]:
    """Return all known aliases for a retrieved/reference chunk.

    Retrieval paths are heterogeneous: vector hits often include `chunk_id`,
    BM25 hits may only include `doc_id` plus metadata hierarchy. ID-based
    evaluation should treat these as aliases for the same chunk/location.
    """
    meta = enrich_context_identity(meta)
    aliases = {retrieved_context_id(meta)}
    if meta.get("canonical_context_id"):
        aliases.add(str(meta["canonical_context_id"]))
    if meta.get("citation_id"):
        aliases.add(str(meta["citation_id"]))
    if meta.get("chunk_id"):
        aliases.add(f"dbchunk:{meta['chunk_id']}")
    if meta.get("document_id") and meta.get("chunk_index") is not None:
        aliases.add(f"doc{meta['document_id']}:idx{meta['chunk_index']}")
    if meta.get("doc_id") and meta.get("chunk_index") is not None:
        aliases.add(f"doc{meta['doc_id']}:idx{meta['chunk_index']}")
    slug = doc_slug_from_metadata(meta)
    section = meta.get("context_header") or meta.get("hierarchy") or meta.get("pasal") or ""
    section_slug = re.sub(r"[^a-z0-9]+", "_", str(section).lower()).strip("_")[:80]
    if section_slug:
        aliases.add(f"{slug}:{section_slug}")
    pasal_no = first_number(meta.get("pasal"))
    ayat_numbers = legal_numbers(meta.get("ayat"))
    if pasal_no:
        aliases.add(f"{slug}:p{pasal_no}")
        for ayat_no in ayat_numbers:
            aliases.add(f"{slug}:p{pasal_no}:ay{ayat_no}")
            aliases.add(f"{slug}:p{pasal_no}:a{ayat_no}")
    return {alias for alias in aliases if alias and not alias.endswith(":unknown")}


def first_number(value: Any) -> str:
    match = re.search(r"\d+", str(value or ""))
    return match.group(0) if match else ""


def legal_numbers(value: Any) -> list[str]:
    text = str(value or "")
    range_match = re.search(r"\(?\s*(\d+)\s*\)?\s*[-–]\s*\(?\s*(\d+)\s*\)?", text)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        if 0 < start <= end <= start + 20:
            return [str(num) for num in range(start, end + 1)]
    return re.findall(r"\d+", text)


def expand_reference_id_aliases(context_id: str) -> set[str]:
    aliases = {context_id}
    text = str(context_id or "")
    aliases.add(re.sub(r":hal\d+(?:[-–]\d+)?$", "", text))
    aliases.add(text.replace(":a", ":ay"))
    aliases.add(text.replace(":ay", ":a"))
    aliases.add(re.sub(r":hal\d+(?:[-–]\d+)?$", "", text.replace(":a", ":ay")))
    aliases.add(re.sub(r":hal\d+(?:[-–]\d+)?$", "", text.replace(":ay", ":a")))
    pasal_match = re.match(r"^([^:]+):p(\d+)", text)
    if pasal_match:
        aliases.add(f"{pasal_match.group(1)}:p{pasal_match.group(2)}")
    return {alias for alias in aliases if alias}


def reference_alias_groups(item: dict[str, Any]) -> list[set[str]]:
    groups: list[set[str]] = []
    for match in item.get("reference_chunk_matches") or []:
        meta = dict(match.get("metadata") or {})
        if match.get("context_id"):
            meta["chunk_id"] = str(match["context_id"]).replace("dbchunk:", "")
        if match.get("document_id") is not None:
            meta["document_id"] = match.get("document_id")
        if match.get("doc_id") is not None:
            meta["doc_id"] = match.get("doc_id")
        if match.get("chunk_index") is not None:
            meta["chunk_index"] = match.get("chunk_index")
        aliases = context_aliases(meta)
        if aliases:
            groups.append(aliases)

    if groups:
        return groups
    return [expand_reference_id_aliases(rid) for rid in item.get("reference_context_ids") or []]


def source_hit(expected_slug: str, retrieved_meta: list[dict[str, Any]], k: int) -> int:
    return int(any(doc_slug_from_metadata(meta) == expected_slug for meta in retrieved_meta[:k]))


def citation_hit(expected: dict[str, Any], retrieved_meta: list[dict[str, Any]], k: int) -> int:
    expected_parts = [
        str(expected.get(key, "")).lower()
        for key in ("pasal", "ayat", "angka", "tabel", "halaman")
        if expected.get(key)
    ]
    if not expected_parts:
        return 0
    for meta in retrieved_meta[:k]:
        blob = normalize_space(" ".join(str(v) for v in meta.values())).lower()
        if all(part in blob for part in expected_parts if part):
            return 1
    return 0


def context_overlap(reference_contexts: list[str], retrieved_contexts: list[str], k: int) -> float:
    ref_tokens = tokens(" ".join(reference_contexts))
    if not ref_tokens:
        return 0.0
    ret_tokens = tokens(" ".join(retrieved_contexts[:k]))
    return round(len(ref_tokens & ret_tokens) / len(ref_tokens), 4)


def reference_text_match(reference_context: str, retrieved_context: str) -> bool:
    """Conservative fallback for legacy chunks missing legal metadata.

    Some OCR-derived chunks predate Pasal/Ayat metadata extraction. If the
    retrieved chunk contains almost all tokens from a reference quote, count it
    as the same evidence instead of penalizing missing aliases.
    """
    ref_tokens = tokens(reference_context)
    if len(ref_tokens) < 8:
        return False
    retrieved_tokens = tokens(retrieved_context)
    return len(ref_tokens & retrieved_tokens) / len(ref_tokens) >= 0.9


def add_reference_text_aliases(
    reference_contexts: list[str],
    retrieved_contexts: list[str],
    reference_groups: list[set[str]],
    retrieved_alias_groups: list[set[str]],
) -> None:
    for ref_idx, reference_context in enumerate(reference_contexts):
        if ref_idx >= len(reference_groups):
            continue
        alias = f"reftext:{ref_idx}"
        matched = False
        for retrieved_idx, retrieved_context in enumerate(retrieved_contexts):
            if reference_text_match(reference_context, retrieved_context):
                retrieved_alias_groups[retrieved_idx].add(alias)
                matched = True
        if matched:
            reference_groups[ref_idx].add(alias)


def metrics_for_k(reference_groups: list[set[str]], retrieved_alias_groups: list[set[str]], k: int) -> dict[str, float | int]:
    top = retrieved_alias_groups[:k]
    matched_doc_count = 0
    matched_reference_indices: set[int] = set()
    for retrieved_aliases in top:
        matched_this_doc = False
        for idx, reference_aliases in enumerate(reference_groups):
            if retrieved_aliases & reference_aliases:
                matched_reference_indices.add(idx)
                matched_this_doc = True
        if matched_this_doc:
            matched_doc_count += 1

    hit = int(bool(matched_reference_indices))
    precision = matched_doc_count / max(len(top), 1)
    recall = len(matched_reference_indices) / max(len(reference_groups), 1)
    mrr = 0.0
    for rank, retrieved_aliases in enumerate(top, 1):
        if any(retrieved_aliases & reference_aliases for reference_aliases in reference_groups):
            mrr = 1.0 / rank
            break
    return {
        f"hit@{k}": hit,
        f"precision@{k}": round(precision, 4),
        f"recall@{k}": round(recall, 4),
        f"mrr@{k}": round(mrr, 4),
    }


def evaluate_item(item: dict[str, Any], top_k: int, k_values: list[int]) -> dict[str, Any]:
    retrieval = langchain_engine.retrieve_context(item["user_input"], top_k=top_k, use_rag=True)
    docs = retrieval.get("raw_docs", [])
    retrieved_ids = [retrieved_context_id(doc.metadata or {}) for doc in docs]
    retrieved_meta = [doc.metadata or {} for doc in docs]
    retrieved_alias_groups = [context_aliases(meta) for meta in retrieved_meta]
    retrieved_contexts = [doc.page_content or "" for doc in docs]
    reference_groups = [set(group) for group in reference_alias_groups(item)]
    add_reference_text_aliases(item.get("reference_contexts") or [], retrieved_contexts, reference_groups, retrieved_alias_groups)
    reference_ids = set().union(*reference_groups) if reference_groups else set(item.get("reference_context_ids") or [])
    expected_citation = (item.get("expected_citations") or [{}])[0]
    expected_slug = (item.get("metadata") or {}).get("sumber_slug", "")

    scores: dict[str, float | int] = {}
    for k in k_values:
        scores.update(metrics_for_k(reference_groups, retrieved_alias_groups, k))
        scores[f"source_doc_hit@{k}"] = source_hit(expected_slug, retrieved_meta, k)
        scores[f"citation_match@{k}"] = citation_hit(expected_citation, retrieved_meta, k)
        scores[f"reference_context_overlap@{k}"] = context_overlap(item.get("reference_contexts") or [], retrieved_contexts, k)

    return {
        "id": item.get("id"),
        "question": item.get("user_input"),
        "reference_context_ids": list(reference_ids),
        "retrieved_context_ids": retrieved_ids,
        "retrieved_context_aliases": [sorted(aliases) for aliases in retrieved_alias_groups],
        "retrieved_sources": [
            {
                "rank": idx + 1,
                "context_id": retrieved_ids[idx],
                "source_slug": doc_slug_from_metadata(meta),
                "metadata": meta,
                "text_preview": normalize_space(retrieved_contexts[idx])[:240],
            }
            for idx, meta in enumerate(retrieved_meta)
        ],
        "scores": scores,
    }


def average(values: list[float | int]) -> float | None:
    finite = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(float(v))]
    return round(sum(finite) / len(finite), 4) if finite else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval with ID-based non-LLM metrics")
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GT)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--k", type=int, nargs="*", default=DEFAULT_K)
    parser.add_argument("--sample", type=int, default=None)
    args = parser.parse_args()

    items = load_jsonl(args.ground_truth)
    if args.sample:
        items = items[: args.sample]

    results = [evaluate_item(item, args.top_k, args.k) for item in items]
    metric_names = sorted({name for result in results for name in result["scores"]})
    summary = {name: average([result["scores"].get(name) for result in results]) for name in metric_names}

    report = {
        "framework": "ID-based retrieval evaluation (non-LLM)",
        "total_evaluated": len(results),
        "top_k": args.top_k,
        "k_values": args.k,
        "summary": summary,
        "per_question": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Evaluated {len(results)} questions")
    for key in sorted(summary):
        if key.startswith(("hit@", "precision@", "recall@", "mrr@")) or key in {"source_doc_hit@5", "citation_match@5", "reference_context_overlap@5"}:
            print(f"{key}: {summary[key]}")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
