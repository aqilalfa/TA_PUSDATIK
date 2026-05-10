#!/usr/bin/env python3
"""
Evaluasi RAG pipeline menggunakan framework RAGAS 0.2.x.

RAGAS menggunakan LLM sebagai judge untuk mengukur kualitas jawaban secara mendalam.
Script ini mengkonfigurasi RAGAS dengan Ollama (lokal) sehingga tidak butuh API key.

Alur:
  1. Load hasil collect dari eval_results.json  (dihasilkan oleh evaluate_rag.py --phase collect)
  2. Format data ke struktur RAGAS 0.2.x (SingleTurnSample / EvaluationDataset)
  3. Konfigurasi RAGAS agar pakai ChatOllama + indo-sentence-bert (bukan OpenAI)
  4. Jalankan evaluasi → cetak dan simpan laporan

Penggunaan:
  # Jalankan evaluasi RAGAS penuh
  python scripts/evaluate_ragas.py

  # Gunakan subset N pertanyaan (untuk tes cepat)
  python scripts/evaluate_ragas.py --sample 5

  # Ganti model judge
    python scripts/evaluate_ragas.py --model qwen3.5:4b

Prasyarat:
  - eval_results.json sudah ada (jalankan evaluate_rag.py --phase collect dulu)
  - Ollama berjalan di localhost:11434
    - Model tersedia di Ollama (qwen3.5:4b)
"""

import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

# Ragas must be imported before langchain_ollama to avoid import-order crash
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas import evaluate, EvaluationDataset, SingleTurnSample
from ragas import RunConfig

from loguru import logger


RESULTS_PATH = Path(__file__).parent.parent / "data" / "eval_results.json"
RAGAS_REPORT_PATH = Path(__file__).parent.parent / "data" / "eval_ragas_report.json"

DEFAULT_MODEL = "qwen3.5:4b"
EMBED_MODEL   = "firqaaa/indo-sentence-bert-base"

METRICS = [faithfulness, answer_relevancy, context_precision, context_recall]


# ---------------------------------------------------------------------------
# Setup RAGAS dengan Ollama (tidak butuh OpenAI)
# ---------------------------------------------------------------------------

def build_ragas_config(model: str):
    """Buat LLM judge dan embeddings untuk RAGAS menggunakan model lokal."""
    from langchain_ollama import ChatOllama
    from langchain_huggingface import HuggingFaceEmbeddings
    from app.config import settings

    logger.info(f"Configuring RAGAS with LLM={model}, embed={EMBED_MODEL}")

    llm = ChatOllama(
        base_url=settings.OLLAMA_BASE_URL,
        model=model,
        temperature=0.0,
        timeout=600,
    )
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )

    return LangchainLLMWrapper(llm), LangchainEmbeddingsWrapper(embeddings)


# ---------------------------------------------------------------------------
# Load dan format data
# ---------------------------------------------------------------------------

def load_results(sample: int = None) -> list:
    if not RESULTS_PATH.exists():
        logger.error(f"File {RESULTS_PATH} tidak ditemukan.")
        logger.error("Jalankan dulu: python scripts/evaluate_rag.py --phase collect")
        sys.exit(1)

    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    valid = [r for r in results if r.get("answer") and not r.get("error")]

    if len(valid) < len(results):
        logger.warning(f"{len(results) - len(valid)} pertanyaan gagal — dilewati")

    if sample:
        valid = valid[:sample]

    logger.info(f"Loaded {len(valid)} hasil untuk evaluasi RAGAS")
    return valid


def _clean_text(text: str) -> str:
    """Strip citation markers and non-printable characters that confuse the LLM judge."""
    text = re.sub(r'\[\d+\]', '', text)          # remove [1], [2], ...
    text = re.sub(r'<br\s*/?>', ' ', text)        # HTML line breaks → space
    text = re.sub(r'[^\x09\x0a\x0d\x20-\x7e\x80-\xff]', '', text)  # strip non-printable
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text


def to_ragas_dataset(results: list) -> EvaluationDataset:
    """Konversi eval_results ke EvaluationDataset RAGAS 0.2.x."""
    samples = [
        SingleTurnSample(
            user_input=r["question"],
            response=_clean_text(r["answer"]),
            retrieved_contexts=[_clean_text(c) for c in r["contexts"]],
            reference=r["ground_truth"],
        )
        for r in results
    ]
    return EvaluationDataset(samples=samples)


# ---------------------------------------------------------------------------
# Jalankan evaluasi
# ---------------------------------------------------------------------------

def run_ragas(dataset: EvaluationDataset, ragas_llm, ragas_embed) -> object:
    logger.info(f"Menjalankan RAGAS pada {len(dataset.samples)} pertanyaan...")
    logger.info("Metrik: faithfulness, answer_relevancy, context_precision, context_recall")
    logger.warning("Setiap pertanyaan memanggil LLM beberapa kali — ini akan lambat (~5–15 menit)")

    run_config = RunConfig(
        timeout=600,      # 10 menit per LLM call — Ollama lokal bisa lambat
        max_retries=3,
        max_workers=1,    # serial execution — GPU lokal tidak bisa handle concurrent calls
    )

    return evaluate(
        dataset,
        metrics=METRICS,
        llm=ragas_llm,
        embeddings=ragas_embed,
        run_config=run_config,
        raise_exceptions=False,
    )


# ---------------------------------------------------------------------------
# Simpan dan cetak laporan
# ---------------------------------------------------------------------------

def save_report(result, results: list) -> dict:
    scores_df = result.to_pandas()

    metric_names = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]

    per_question = []
    for i, r in enumerate(results):
        row = scores_df.iloc[i].to_dict() if i < len(scores_df) else {}
        per_question.append({
            "id":           r["id"],
            "source_doc":   r["source_doc"],
            "doc_type":     r["doc_type"],
            "question":     r["question"],
            "answer":       r["answer"][:300] + "..." if len(r["answer"]) > 300 else r["answer"],
            "ground_truth": r["ground_truth"][:200] + "..." if len(r["ground_truth"]) > 200 else r["ground_truth"],
            "scores": {
                m: float(row.get(m, 0) or 0)
                for m in metric_names
            },
        })

    averages = {}
    for m in metric_names:
        if m in scores_df.columns:
            col = scores_df[m].dropna()
            averages[m] = round(float(col.mean()), 4) if len(col) else None
        else:
            averages[m] = None

    by_type: dict = {}
    for item in per_question:
        dt = item["doc_type"]
        if dt not in by_type:
            by_type[dt] = {m: [] for m in metric_names}
        for m in metric_names:
            val = item["scores"].get(m)
            if val is not None:
                by_type[dt][m].append(val)

    type_summary = {
        dt: {m: round(sum(vs) / len(vs), 4) if vs else None for m, vs in mdict.items()}
        for dt, mdict in by_type.items()
    }

    report = {
        "generated_at":      datetime.now().isoformat(),
        "framework":         "RAGAS 0.2.x",
        "llm_judge":         DEFAULT_MODEL,
        "embed_model":       EMBED_MODEL,
        "total_evaluated":   len(per_question),
        "averages":          averages,
        "by_doc_type":       type_summary,
        "metric_descriptions": {
            "faithfulness":      "Apakah jawaban hanya berdasarkan context? (0=hallucination, 1=fully grounded)",
            "answer_relevancy":  "Apakah jawaban relevan dengan pertanyaan? (0=tidak relevan, 1=sangat relevan)",
            "context_precision": "Apakah context yang di-retrieve relevan? (0=banyak noise, 1=presisi)",
            "context_recall":    "Apakah context mencakup informasi yang dibutuhkan? (0=miss, 1=lengkap)",
        },
        "per_question":      per_question,
    }

    RAGAS_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.success(f"Laporan RAGAS disimpan → {RAGAS_REPORT_PATH}")
    return report


def print_summary(report: dict):
    print("\n" + "=" * 60)
    print("HASIL EVALUASI RAGAS")
    print("=" * 60)
    print(f"Framework   : {report['framework']}")
    print(f"LLM Judge   : {report['llm_judge']}")
    print(f"Embed Model : {report['embed_model']}")
    print(f"Dievaluasi  : {report['total_evaluated']} pertanyaan")
    print()
    print("── Metrik Rata-Rata ────────────────────────────────")

    desc_short = {
        "faithfulness":      "Jawaban setia pada context (anti-halusinasi)",
        "answer_relevancy":  "Jawaban relevan dengan pertanyaan",
        "context_precision": "Context yang diambil relevan",
        "context_recall":    "Context mencakup fakta yang dibutuhkan",
    }
    for name, val in report["averages"].items():
        if val is None:
            continue
        bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
        print(f"  {name:22s} {val:.4f}  [{bar}]  {desc_short[name]}")

    print()
    print("── Per Tipe Dokumen ────────────────────────────────")
    for dt, scores in report["by_doc_type"].items():
        vals = " | ".join(f"{k[:4]}={v:.3f}" for k, v in scores.items() if v is not None)
        print(f"  {dt:15s}  {vals}")
    print("=" * 60)
    print(f"\nLaporan lengkap: data/eval_ragas_report.json")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluasi RAG dengan RAGAS + Ollama")
    parser.add_argument("--sample", type=int, default=None,
                        help="Jumlah pertanyaan (default: semua)")
    parser.add_argument("--model",  default=DEFAULT_MODEL,
                        help=f"Model Ollama untuk judge (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    results = load_results(args.sample)
    dataset = to_ragas_dataset(results)

    ragas_llm, ragas_embed = build_ragas_config(args.model)

    ragas_result = run_ragas(dataset, ragas_llm, ragas_embed)

    report = save_report(ragas_result, results)
    print_summary(report)
