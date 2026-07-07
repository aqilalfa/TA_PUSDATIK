#!/usr/bin/env python3
"""
Evaluasi RAG pipeline menggunakan ground truth.

Fase 1 — Collect: jalankan semua pertanyaan ke RAG pipeline, simpan ke file.
Fase 2 — Score: hitung metrik dari hasil Fase 1.

Penggunaan:
  # Jalankan keduanya sekaligus
  python scripts/evaluate_rag.py

  # Hanya fase 1 (collect)
  python scripts/evaluate_rag.py --phase collect

  # Hanya fase 2 (score, pakai hasil yang sudah ada)
  python scripts/evaluate_rag.py --phase score

  # Gunakan subset N pertanyaan (untuk tes cepat)
  python scripts/evaluate_rag.py --sample 5
"""

import sys
import json
import asyncio
import argparse
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if callable(stdout_reconfigure):
    stdout_reconfigure(encoding="utf-8")

from loguru import logger
from app.core.rag.langchain_engine import langchain_engine
from app.config import settings
from app.core.rag.context_ids import enrich_context_identity


GROUND_TRUTH_PATH = Path(__file__).parent.parent / "data" / "ground_truth.json"
RESULTS_PATH      = Path(__file__).parent.parent / "data" / "eval_results.json"
REPORT_PATH       = Path(__file__).parent.parent / "data" / "eval_report.json"

DEFAULT_MODEL = "qwen3.5:4b"


def _slug_text(text: str, max_len: int = 80) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")[:max_len]


def build_context_id(metadata: dict) -> str:
    """Build a traceable ID for a retrieved context from best available metadata."""
    metadata = enrich_context_identity(metadata)
    if metadata.get("canonical_context_id"):
        return str(metadata["canonical_context_id"])
    if metadata.get("chunk_id"):
        return f"dbchunk:{metadata['chunk_id']}"
    if metadata.get("document_id") is not None and metadata.get("chunk_index") is not None:
        return f"doc{metadata['document_id']}:idx{metadata['chunk_index']}"
    if metadata.get("doc_id") and metadata.get("chunk_index") is not None:
        return f"doc{metadata['doc_id']}:idx{metadata['chunk_index']}"

    blob = " ".join(
        str(metadata.get(k, ""))
        for k in ("filename", "document_title", "judul_dokumen", "tentang")
    )
    section = metadata.get("context_header") or metadata.get("hierarchy") or metadata.get("pasal") or "unknown"
    return f"{_slug_text(blob, 50)}:{_slug_text(str(section), 80)}"


def build_retrieved_source(rank: int, doc) -> dict:
    metadata = enrich_context_identity(dict(doc.metadata or {}))
    return {
        "rank": rank,
        "context_id": build_context_id(metadata),
        "document_id": metadata.get("document_id"),
        "doc_id": metadata.get("doc_id"),
        "chunk_id": metadata.get("chunk_id"),
        "chunk_index": metadata.get("chunk_index"),
        "source_doc": metadata.get("filename") or metadata.get("document_title") or metadata.get("judul_dokumen"),
        "section": metadata.get("context_header") or metadata.get("hierarchy") or metadata.get("pasal"),
        "metadata": metadata,
    }


def _infer_doc_type(source_doc: str, fallback: str = "unknown") -> str:
    source = (source_doc or "").lower()
    if "laporan" in source:
        return "laporan"
    if source:
        return "peraturan"
    return fallback


def _normalize_ground_truth_item(item: dict) -> dict:
    """Normalize supported ground-truth schemas into the evaluator schema."""
    metadata = item.get("metadata") or {}
    question = item.get("question") or item.get("pertanyaan") or item.get("user_input")
    ground_truth = item.get("ground_truth") or item.get("answer") or item.get("jawaban") or item.get("reference")
    source_doc = (
        item.get("source_doc")
        or item.get("sumber_dokumen")
        or metadata.get("sumber_dokumen")
        or item.get("sitasi")
        or metadata.get("sitasi")
        or "unknown"
    )
    doc_type = (
        item.get("doc_type")
        or metadata.get("jenis_dokumen")
        or _infer_doc_type(source_doc, item.get("jenis") or metadata.get("jenis", "unknown"))
    )

    if not question or not ground_truth:
        raise ValueError(f"Invalid ground truth item, missing question/answer fields: {item}")

    return {
        "id": item.get("id") or item.get("nomor"),
        "source_doc": source_doc,
        "doc_type": doc_type,
        "question": question,
        "ground_truth": ground_truth,
    }


def load_ground_truth(path: Path) -> list:
    """Load JSON or JSONL ground truth and normalize field names."""
    if path.suffix.lower() == ".jsonl":
        items = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        items = json.loads(path.read_text(encoding="utf-8"))

    return [_normalize_ground_truth_item(item) for item in items]


# ---------------------------------------------------------------------------
# Fase 1: Collect — jalankan tiap pertanyaan ke RAG pipeline
# ---------------------------------------------------------------------------

async def collect_one(question: str, model: str) -> dict:
    """Kirim satu pertanyaan ke RAG pipeline, kembalikan answer + contexts."""
    import asyncio
    from functools import partial

    # Retrieve context (sync, jalankan di thread pool)
    retrieval = await asyncio.get_event_loop().run_in_executor(
        None,
        partial(langchain_engine.retrieve_context, query=question, top_k=5, use_rag=True, doc_id=None),
    )
    context    = retrieval["context"]
    query_type = retrieval.get("query_type", "general")
    raw_docs = retrieval.get("raw_docs", [])
    history    = []

    # Collect streaming answer
    answer = ""
    async for token in langchain_engine.stream_answer(
        query=question,
        context=context,
        history=history,
        model_name=model,
        query_type=query_type,
    ):
        answer += token

    # Use full page_content from raw_docs so RAGAS gets complete chunk text, not 150-char snippets
    contexts = [doc.page_content for doc in raw_docs if doc.page_content]
    retrieved_sources = [build_retrieved_source(i, doc) for i, doc in enumerate(raw_docs, 1)]
    retrieved_context_ids = [source["context_id"] for source in retrieved_sources]
    return {
        "answer": answer,
        "contexts": contexts,
        "retrieved_context_ids": retrieved_context_ids,
        "retrieved_sources": retrieved_sources,
    }


async def phase_collect(ground_truth: list, model: str, sample: int | None = None) -> list:
    """Jalankan semua pertanyaan ke RAG pipeline dan simpan hasilnya."""
    if not langchain_engine._initialized:
        logger.info("Initializing RAG engine...")
        langchain_engine.initialize()

    items = ground_truth[:sample] if sample else ground_truth
    results = []

    for i, gt in enumerate(items, 1):
        logger.info(f"[{i}/{len(items)}] {gt['question'][:70]}...")
        t0 = time.perf_counter()
        try:
            out = await collect_one(gt["question"], model)
            elapsed = time.perf_counter() - t0
            results.append({
                "id":           gt["id"],
                "source_doc":   gt["source_doc"],
                "doc_type":     gt["doc_type"],
                "question":     gt["question"],
                "ground_truth": gt["ground_truth"],
                "answer":       out["answer"],
                "contexts":     out["contexts"],
                "retrieved_context_ids": out.get("retrieved_context_ids", []),
                "retrieved_sources": out.get("retrieved_sources", []),
                "latency_s":    round(elapsed, 2),
            })
            logger.success(f"  answer {len(out['answer'])} chars, {len(out['contexts'])} contexts, {elapsed:.1f}s")
        except Exception as e:
            logger.error(f"  FAILED: {e}")
            results.append({
                "id":           gt["id"],
                "source_doc":   gt["source_doc"],
                "doc_type":     gt["doc_type"],
                "question":     gt["question"],
                "ground_truth": gt["ground_truth"],
                "answer":       "",
                "contexts":     [],
                "latency_s":    -1,
                "error":        str(e),
            })

    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.success(f"Saved {len(results)} results → {RESULTS_PATH}")
    return results


# ---------------------------------------------------------------------------
# Fase 2: Score — hitung metrik dari hasil Fase 1
# ---------------------------------------------------------------------------

def _cosine(a, b) -> float:
    import numpy as np
    a, b = np.array(a), np.array(b)
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0


def score_semantic_similarity(answer: str, ground_truth: str) -> float:
    """
    Cosine similarity antara embedding jawaban RAG vs ground truth.
    Menggunakan HuggingFaceEmbeddings yang sudah diload di langchain_engine.
    Rentang: 0.0 – 1.0, semakin tinggi semakin mirip.
    """
    if not langchain_engine._initialized:
        langchain_engine.initialize()
    embeddings = langchain_engine.embeddings
    if embeddings is None:
        raise RuntimeError("RAG embeddings are not initialized")
    emb_a = embeddings.embed_query(answer)
    emb_b = embeddings.embed_query(ground_truth)
    return _cosine(emb_a, emb_b)


def score_context_recall(ground_truth: str, contexts: list) -> float:
    """
    Berapa banyak fakta kunci dari ground truth yang muncul di contexts.
    Pendekatan sederhana: cek overlap token penting.
    Rentang: 0.0 – 1.0.
    """
    import re
    def tokens(text):
        return set(re.findall(r'\b\w{4,}\b', text.lower()))

    gt_tokens = tokens(ground_truth)
    if not gt_tokens:
        return 0.0
    ctx_tokens = tokens(" ".join(contexts))
    return len(gt_tokens & ctx_tokens) / len(gt_tokens)


def score_answer_coverage(answer: str, ground_truth: str) -> float:
    """
    Berapa banyak token kunci ground truth yang muncul di answer.
    Mengukur apakah jawaban menyebut fakta yang sama.
    Rentang: 0.0 – 1.0.
    """
    import re
    def tokens(text):
        return set(re.findall(r'\b\w{4,}\b', text.lower()))

    gt_tokens = tokens(ground_truth)
    if not gt_tokens:
        return 0.0
    ans_tokens = tokens(answer)
    return len(gt_tokens & ans_tokens) / len(gt_tokens)


def phase_score(results: list) -> dict:
    """Hitung semua metrik untuk setiap hasil dan buat laporan."""
    if not langchain_engine._initialized:
        langchain_engine.initialize()

    scored = []
    for r in results:
        if not r.get("answer") or r.get("error"):
            scored.append({**r, "scores": None})
            continue

        sem_sim    = score_semantic_similarity(r["answer"], r["ground_truth"])
        ctx_recall = score_context_recall(r["ground_truth"], r["contexts"])
        ans_cov    = score_answer_coverage(r["answer"], r["ground_truth"])

        scores = {
            "semantic_similarity": round(sem_sim, 4),
            "context_recall":      round(ctx_recall, 4),
            "answer_coverage":     round(ans_cov, 4),
        }
        scored.append({**r, "scores": scores})
        logger.info(
            f"[{r['id']}] sim={sem_sim:.3f} ctx_recall={ctx_recall:.3f} cov={ans_cov:.3f}"
        )

    # Agregasi per metrik
    valid = [s for s in scored if s.get("scores")]
    def avg(key):
        vals = [s["scores"][key] for s in valid]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    # Agregasi per doc_type
    by_type: dict = {}
    for s in valid:
        dt = s["doc_type"]
        if dt not in by_type:
            by_type[dt] = []
        by_type[dt].append(s["scores"])

    type_summary = {}
    for dt, scores_list in by_type.items():
        type_summary[dt] = {
            k: round(sum(s[k] for s in scores_list) / len(scores_list), 4)
            for k in ["semantic_similarity", "context_recall", "answer_coverage"]
        }

    report = {
        "generated_at":    datetime.now().isoformat(),
        "total_questions": len(results),
        "evaluated":       len(valid),
        "failed":          len(results) - len(valid),
        "avg_latency_s":   round(sum(r.get("latency_s", 0) for r in results if r.get("latency_s", 0) > 0) / max(len(valid), 1), 2),
        "metrics": {
            "semantic_similarity": {
                "avg":   avg("semantic_similarity"),
                "description": "Cosine similarity embedding jawaban vs ground truth (0–1, lebih tinggi lebih baik)",
            },
            "context_recall": {
                "avg":   avg("context_recall"),
                "description": "Fraksi token kunci ground truth yang muncul di context yang di-retrieve (0–1)",
            },
            "answer_coverage": {
                "avg":   avg("answer_coverage"),
                "description": "Fraksi token kunci ground truth yang muncul di jawaban (0–1)",
            },
        },
        "by_doc_type": type_summary,
        "per_question": scored,
    }

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.success(f"Report saved → {REPORT_PATH}")
    return report


# ---------------------------------------------------------------------------
# Cetak ringkasan ke terminal
# ---------------------------------------------------------------------------

def print_summary(report: dict):
    print("\n" + "=" * 60)
    print("HASIL EVALUASI RAG")
    print("=" * 60)
    print(f"Total pertanyaan : {report['total_questions']}")
    print(f"Berhasil dievaluasi : {report['evaluated']}")
    print(f"Gagal            : {report['failed']}")
    print(f"Rata-rata latency : {report['avg_latency_s']}s/pertanyaan")
    print()
    print("── Metrik Keseluruhan ──────────────────────────────")
    for name, data in report["metrics"].items():
        bar_len = int(data["avg"] * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"  {name:25s} {data['avg']:.4f}  [{bar}]")
    print()
    print("── Per Tipe Dokumen ────────────────────────────────")
    for dt, scores in report["by_doc_type"].items():
        print(f"  {dt:15s}  sim={scores['semantic_similarity']:.3f}  recall={scores['context_recall']:.3f}  cov={scores['answer_coverage']:.3f}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main(phase: str, sample: int | None, model: str):
    ground_truth = load_ground_truth(GROUND_TRUTH_PATH)
    logger.info(f"Ground truth: {len(ground_truth)} pertanyaan dari {GROUND_TRUTH_PATH.name}")

    if phase in ("collect", "both"):
        results = await phase_collect(ground_truth, model, sample)
    else:
        if not RESULTS_PATH.exists():
            logger.error(f"File hasil tidak ditemukan: {RESULTS_PATH}. Jalankan fase collect dulu.")
            sys.exit(1)
        results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        logger.info(f"Loaded {len(results)} hasil dari {RESULTS_PATH.name}")

    if phase in ("score", "both"):
        report = phase_score(results)
        print_summary(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluasi RAG pipeline dengan ground truth")
    parser.add_argument("--phase",  default="both", choices=["collect", "score", "both"],
                        help="Fase yang dijalankan (default: both)")
    parser.add_argument("--sample", type=int, default=None,
                        help="Jumlah pertanyaan untuk tes cepat (default: semua)")
    parser.add_argument("--model",  default=DEFAULT_MODEL,
                        help=f"Model Ollama yang digunakan (default: {DEFAULT_MODEL})")
    parser.add_argument("--ground-truth-path", type=Path, default=GROUND_TRUTH_PATH,
                        help=f"Path ground truth JSON/JSONL (default: {GROUND_TRUTH_PATH})")
    parser.add_argument("--results-path", type=Path, default=RESULTS_PATH,
                        help=f"Path output hasil collect (default: {RESULTS_PATH})")
    parser.add_argument("--report-path", type=Path, default=REPORT_PATH,
                        help=f"Path output laporan score (default: {REPORT_PATH})")
    args = parser.parse_args()

    GROUND_TRUTH_PATH = args.ground_truth_path
    RESULTS_PATH = args.results_path
    REPORT_PATH = args.report_path

    asyncio.run(main(args.phase, args.sample, args.model))
