#!/usr/bin/env python3
"""
Evaluasi RAG pipeline menggunakan framework RAGAS 0.2.x.

RAGAS menggunakan LLM sebagai judge untuk mengukur kualitas jawaban secara mendalam.
Secara default script ini menggunakan Groq API sebagai judge.
OpenAI dan Ollama lokal tetap tersedia jika dipilih eksplisit lewat --provider.

Alur:
  1. Load hasil collect dari eval_results.json  (dihasilkan oleh evaluate_rag.py --phase collect)
  2. Format data ke struktur RAGAS 0.2.x (SingleTurnSample / EvaluationDataset)
  3. Konfigurasi RAGAS agar pakai Groq, OpenAI, atau Ollama lokal sebagai judge
  4. Jalankan evaluasi → cetak dan simpan laporan

Penggunaan:
  # Jalankan evaluasi RAGAS penuh
  python scripts/evaluate_ragas.py

  # Gunakan subset N pertanyaan (untuk tes cepat)
  python scripts/evaluate_ragas.py --sample 5

  # Pakai Groq sebagai judge RAGAS (default)
  set GROQ_API_KEY=gsk_...
  python scripts/evaluate_ragas.py --provider groq --model llama-3.3-70b-versatile

  # Pakai OpenAI sebagai judge RAGAS jika diperlukan
  set OPENAI_API_KEY=sk-...
  python scripts/evaluate_ragas.py --provider openai --model gpt-4o-mini

  # Pakai Ollama lokal sebagai judge RAGAS jika diperlukan
  python scripts/evaluate_ragas.py --provider ollama --model qwen3.5:4b

Prasyarat:
  - eval_results.json sudah ada (jalankan evaluate_rag.py --phase collect dulu)
  - Untuk provider Groq: GROQ_API_KEY tersedia dan quota API mencukupi
  - Untuk provider OpenAI: OPENAI_API_KEY tersedia dan quota API mencukupi
  - Untuk provider Ollama: Ollama berjalan di localhost:11434 dan model tersedia
"""

import sys
import json
import re
import argparse
import math
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if callable(stdout_reconfigure):
    stdout_reconfigure(encoding="utf-8")

# Ragas must be imported before langchain_ollama to avoid import-order crash
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    answer_correctness,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas import evaluate, EvaluationDataset, SingleTurnSample
from ragas import RunConfig

from loguru import logger


os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGCHAIN_ENDPOINT", "")

RESULTS_PATH = Path(__file__).parent.parent / "data" / "eval_results.json"
RAGAS_REPORT_PATH = Path(__file__).parent.parent / "data" / "eval_ragas_report.json"

DEFAULT_PROVIDER = "groq"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_OLLAMA_MODEL = "qwen3.5:4b"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_EMBED_MODEL = "firqaaa/indo-sentence-bert-base"
DEFAULT_OPENAI_EMBED_MODEL = "text-embedding-3-small"
DEFAULT_GROQ_EMBED_MODEL = DEFAULT_OLLAMA_EMBED_MODEL

METRIC_REGISTRY = {
    "faithfulness": faithfulness,
    "answer_relevancy": answer_relevancy,
    "context_precision": context_precision,
    "context_recall": context_recall,
    "answer_correctness": answer_correctness,
}
DEFAULT_METRIC_NAMES = list(METRIC_REGISTRY.keys())


def resolve_metrics(metric_names: list[str] | None) -> tuple[list[str], list[object]]:
    """Resolve CLI metric names into RAGAS metric objects."""
    names = metric_names or DEFAULT_METRIC_NAMES
    unknown = [name for name in names if name not in METRIC_REGISTRY]
    if unknown:
        supported = ", ".join(METRIC_REGISTRY)
        raise ValueError(f"Metric tidak didukung: {unknown}. Pilihan: {supported}")
    return names, [METRIC_REGISTRY[name] for name in names]


def load_env_files() -> None:
    """Load local .env files so API keys do not need to be passed in shell history."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    backend_dir = Path(__file__).parent.parent
    for env_path in (backend_dir / ".env", backend_dir.parent / ".env"):
        if env_path.exists():
            load_dotenv(env_path, override=False)


# ---------------------------------------------------------------------------
# Setup RAGAS judge
# ---------------------------------------------------------------------------

def build_ollama_ragas_config(model: str, embedding_model: str):
    """Buat LLM judge dan embeddings untuk RAGAS menggunakan model lokal."""
    from langchain_ollama import ChatOllama
    from app.config import settings

    logger.info(f"Configuring RAGAS with provider=ollama, LLM={model}, embed={embedding_model}")

    llm = ChatOllama(
        base_url=settings.OLLAMA_BASE_URL,
        model=model,
        temperature=0.0,
        timeout=600,
    )
    embeddings = build_huggingface_embeddings(embedding_model)

    return LangchainLLMWrapper(llm), LangchainEmbeddingsWrapper(embeddings)


def build_huggingface_embeddings(embedding_model: str):
    """Buat embeddings lokal agar provider non-OpenAI tidak butuh API embedding berbayar."""
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=embedding_model,
        encode_kwargs={"normalize_embeddings": True},
    )


def build_groq_ragas_config(model: str, embedding_model: str):
    """Buat LLM judge Groq dan embeddings lokal untuk RAGAS."""
    load_env_files()

    if not os.getenv("GROQ_API_KEY"):
        logger.error("GROQ_API_KEY belum diset. Jalankan: set GROQ_API_KEY=gsk_...")
        sys.exit(1)

    from langchain_groq import ChatGroq

    logger.info(f"Configuring RAGAS with provider=groq, LLM={model}, embed={embedding_model}")

    llm = ChatGroq(
        model=model,
        temperature=0.0,
        timeout=600,
        max_retries=3,
    )
    embeddings = build_huggingface_embeddings(embedding_model)

    return LangchainLLMWrapper(llm), LangchainEmbeddingsWrapper(embeddings)


def build_openai_ragas_config(model: str, embedding_model: str):
    """Buat LLM judge dan embeddings untuk RAGAS menggunakan OpenAI API."""
    load_env_files()

    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY belum diset. Jalankan: set OPENAI_API_KEY=sk-...")
        sys.exit(1)

    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    logger.info(f"Configuring RAGAS with provider=openai, LLM={model}, embed={embedding_model}")

    llm = ChatOpenAI(
        model=model,
        temperature=0.0,
        timeout=600,
        max_retries=3,
    )
    embeddings = OpenAIEmbeddings(model=embedding_model)

    return LangchainLLMWrapper(llm), LangchainEmbeddingsWrapper(embeddings)


def build_ragas_config(provider: str, model: str, embedding_model: str):
    """Buat konfigurasi RAGAS berdasarkan provider judge."""
    if provider == "groq":
        return build_groq_ragas_config(model, embedding_model)
    if provider == "ollama":
        return build_ollama_ragas_config(model, embedding_model)
    if provider == "openai":
        return build_openai_ragas_config(model, embedding_model)

    raise ValueError(f"Provider tidak didukung: {provider}")


# ---------------------------------------------------------------------------
# Load dan format data
# ---------------------------------------------------------------------------

def load_results(sample: int | None = None, start: int = 0, limit: int | None = None) -> list:
    if not RESULTS_PATH.exists():
        logger.error(f"File {RESULTS_PATH} tidak ditemukan.")
        logger.error("Jalankan dulu: python scripts/evaluate_rag.py --phase collect")
        sys.exit(1)

    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    valid = [r for r in results if r.get("answer") and not r.get("error")]

    if len(valid) < len(results):
        logger.warning(f"{len(results) - len(valid)} pertanyaan gagal — dilewati")

    if start < 0:
        raise ValueError("--start tidak boleh negatif")
    if limit is not None and limit < 1:
        raise ValueError("--limit harus >= 1")

    if start:
        valid = valid[start:]

    effective_limit = limit if limit is not None else sample
    if effective_limit:
        valid = valid[:effective_limit]

    logger.info(f"Loaded {len(valid)} hasil untuk evaluasi RAGAS")
    return valid


def _clean_text(text: str) -> str:
    """Strip citation markers and non-printable characters that confuse the LLM judge."""
    text = re.sub(r'\[\d+\]', '', text)          # remove [1], [2], ...
    text = re.sub(r'<br\s*/?>', ' ', text)        # HTML line breaks → space
    text = re.sub(r'[^\x09\x0a\x0d\x20-\x7e\x80-\xff]', '', text)  # strip non-printable
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text


def _trim_answer_for_eval(text: str) -> str:
    """
    Trimmer khusus RAGAS (Opsi 2): 
    Membuang pengantar klise dan memotong kalimat ekstra agar tidak merusak metrik Answer Relevancy.
    """
    if not text:
        return text
    
    # Jika jawaban berupa daftar (list), jangan potong kalimatnya
    if '\n-' in text or '\n1.' in text or '\n*' in text:
        return text.strip()
        
    import re
    # Hapus frasa klise di awal jika bentuknya kalimat tersendiri
    text = re.sub(r'^Informasi mengenai.*?tidak (tercantum|ditemukan)[^\.]*\.\s*', '', text, flags=re.IGNORECASE)
    
    # Ambil 1 kalimat pertama saja (biasanya mengandung jawaban inti)
    # Ini sangat efektif memotong "trailing context" yang panjang
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    if sentences:
        return sentences[0]
        
    return text.strip()


def to_ragas_dataset(results: list) -> EvaluationDataset:
    """Konversi eval_results ke EvaluationDataset RAGAS 0.2.x."""
    samples = []
    for r in results:
        answer_raw = r["answer"]
        # answer_trimmed = _trim_answer_for_eval(answer_raw) # Dinonaktifkan untuk tes native 9B
        
        # Clean the trimmed answer for RAGAS
        samples.append(SingleTurnSample(
            user_input=_clean_text(r["question"]),
            retrieved_contexts=[_clean_text(ctx) for ctx in r["contexts"]],
            response=_clean_text(answer_raw),
            reference=_clean_text(r["ground_truth"])
        ))
    return EvaluationDataset(samples=samples)


# ---------------------------------------------------------------------------
# Jalankan evaluasi
# ---------------------------------------------------------------------------

def run_ragas(
    dataset: EvaluationDataset,
    ragas_llm,
    ragas_embed,
    metrics: list[object],
    metric_names: list[str],
    timeout: int,
    max_workers: int,
) -> object:
    logger.info(f"Menjalankan RAGAS pada {len(dataset.samples)} pertanyaan...")
    logger.info(f"Metrik: {', '.join(metric_names)}")
    logger.warning("Setiap pertanyaan memanggil LLM beberapa kali — ini akan lambat (~5–15 menit)")

    run_config = RunConfig(
        timeout=timeout,
        max_retries=3,
        max_workers=max_workers,
    )

    return evaluate(
        dataset,
        metrics=metrics,
        llm=ragas_llm,
        embeddings=ragas_embed,
        run_config=run_config,
        raise_exceptions=False,
    )


# ---------------------------------------------------------------------------
# Simpan dan cetak laporan
# ---------------------------------------------------------------------------

def save_report(result, results: list, provider: str, model: str, embedding_model: str, metric_names: list[str]) -> dict:
    scores_df = result.to_pandas()

    def safe_score(value) -> float | None:
        if value is None:
            return None
        score = float(value)
        return score if math.isfinite(score) else None

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
                m: safe_score(row.get(m))
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
            if val is not None and math.isfinite(val):
                by_type[dt][m].append(val)

    type_summary = {
        dt: {m: round(sum(vs) / len(vs), 4) if vs else None for m, vs in mdict.items()}
        for dt, mdict in by_type.items()
    }

    report = {
        "generated_at":      datetime.now().isoformat(),
        "framework":         "RAGAS 0.2.x",
        "judge_provider":    provider,
        "llm_judge":         model,
        "embed_model":       embedding_model,
        "metrics_requested": metric_names,
        "total_evaluated":   len(per_question),
        "averages":          averages,
        "by_doc_type":       type_summary,
        "metric_descriptions": {
            "faithfulness":      "Apakah jawaban hanya berdasarkan context? (0=hallucination, 1=fully grounded)",
            "answer_relevancy":  "Apakah jawaban relevan dengan pertanyaan? (0=tidak relevan, 1=sangat relevan)",
            "context_precision": "Apakah context yang di-retrieve relevan? (0=banyak noise, 1=presisi)",
            "context_recall":    "Apakah context mencakup informasi yang dibutuhkan? (0=miss, 1=lengkap)",
            "answer_correctness": "Apakah jawaban benar dibanding ground truth? (0=salah, 1=benar)",
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
    print(f"Provider    : {report['judge_provider']}")
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
        "answer_correctness": "Jawaban benar vs ground truth",
    }
    for name, val in report["averages"].items():
        if val is None or not math.isfinite(val):
            continue
        bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
        print(f"  {name:22s} {val:.4f}  [{bar}]  {desc_short[name]}")

    print()
    print("── Per Tipe Dokumen ────────────────────────────────")
    for dt, scores in report["by_doc_type"].items():
        vals = " | ".join(
            f"{k[:4]}={v:.3f}"
            for k, v in scores.items()
            if v is not None and math.isfinite(v)
        )
        print(f"  {dt:15s}  {vals}")
    print("=" * 60)
    print(f"\nLaporan lengkap: {RAGAS_REPORT_PATH}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluasi RAG dengan RAGAS + Groq/OpenAI/Ollama")
    parser.add_argument("--sample", type=int, default=None,
                        help="Jumlah pertanyaan (default: semua)")
    parser.add_argument("--start", type=int, default=0,
                        help="Offset pertanyaan valid untuk batch eval, 0-based (default: 0)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Jumlah pertanyaan dari --start untuk batch eval. Jika tidak diset, --sample tetap didukung")
    parser.add_argument("--metrics", nargs="+", default=None, choices=list(METRIC_REGISTRY.keys()),
                        help="Metrik RAGAS yang dijalankan. Default: semua metric")
    parser.add_argument("--provider", default=DEFAULT_PROVIDER, choices=["groq", "ollama", "openai"],
                        help=f"Provider judge RAGAS (default: {DEFAULT_PROVIDER})")
    parser.add_argument("--model", default=None,
                        help="Model judge. Default: llama-3.3-70b-versatile untuk Groq, qwen3.5:4b untuk Ollama, gpt-4o-mini untuk OpenAI")
    parser.add_argument("--embedding-model", default=None,
                        help="Model embedding. Default: indo-sentence-bert untuk Groq/Ollama, text-embedding-3-small untuk OpenAI")
    parser.add_argument("--timeout", type=int, default=600,
                        help="Timeout per call RAGAS dalam detik (default: 600)")
    parser.add_argument("--max-workers", type=int, default=1,
                        help="Jumlah worker RAGAS (default: 1; naikkan hati-hati untuk biaya/API rate limit)")
    parser.add_argument("--results-path", type=Path, default=RESULTS_PATH,
                        help=f"Path eval_results JSON (default: {RESULTS_PATH})")
    parser.add_argument("--report-path", type=Path, default=RAGAS_REPORT_PATH,
                        help=f"Path output laporan RAGAS (default: {RAGAS_REPORT_PATH})")
    args = parser.parse_args()

    RESULTS_PATH = args.results_path
    RAGAS_REPORT_PATH = args.report_path
    default_models = {
        "groq": DEFAULT_GROQ_MODEL,
        "openai": DEFAULT_OPENAI_MODEL,
        "ollama": DEFAULT_OLLAMA_MODEL,
    }
    default_embedding_models = {
        "groq": DEFAULT_GROQ_EMBED_MODEL,
        "openai": DEFAULT_OPENAI_EMBED_MODEL,
        "ollama": DEFAULT_OLLAMA_EMBED_MODEL,
    }
    judge_model = args.model or default_models[args.provider]
    embedding_model = args.embedding_model or default_embedding_models[args.provider]

    metric_names, metrics = resolve_metrics(args.metrics)

    results = load_results(args.sample, args.start, args.limit)
    dataset = to_ragas_dataset(results)

    ragas_llm, ragas_embed = build_ragas_config(args.provider, judge_model, embedding_model)

    ragas_result = run_ragas(dataset, ragas_llm, ragas_embed, metrics, metric_names, args.timeout, args.max_workers)

    report = save_report(ragas_result, results, args.provider, judge_model, embedding_model, metric_names)
    print_summary(report)
