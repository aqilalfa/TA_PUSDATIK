from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "ground_truth_evaluasi_chatbot.json"
BASE_URL = "http://localhost:8000"


def token(container: str) -> str:
    code = "from app.auth.jwt_manager import jwt_manager; print(jwt_manager.create_access_token({'sub':'admin@bssn.go.id'}))"
    out = subprocess.check_output(
        ["docker", "exec", container, "python3", "-c", code],
        text=True,
        stderr=subprocess.STDOUT,
    )
    return out.strip().splitlines()[-1]


def get_retrieval(query: str, bearer: str, base_url: str, timeout: int = 120) -> dict[str, Any]:
    params = urllib.parse.urlencode({"query": query})
    req = urllib.request.Request(
        f"{base_url}/api/chat/debug/retrieval?{params}",
        headers={"Authorization": f"Bearer {bearer}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def expected_from_citation(citation: str) -> dict[str, Any]:
    text = str(citation or "").lower()
    doc_checks: list[str] = []
    if "perpres nomor 95" in text or "perpres 95" in text:
        doc_checks = ["95", "2018"]
    elif "permenpan" in text or "permenpan rb" in text:
        doc_checks = ["59", "2020"]
    elif "perpres nomor 82" in text or "perpres 82" in text:
        doc_checks = ["82", "2023"]
    elif "peraturan bssn nomor 8" in text or "perka bssn nomor 8" in text:
        doc_checks = ["8", "2024"]
    elif "pp nomor 71" in text or "pp 71" in text:
        doc_checks = ["71", "2019"]
    elif "peraturan bssn nomor 2" in text or "perka bssn nomor 2" in text:
        doc_checks = ["2", "2023"]
    elif "laporan evaluasi spbe tahun 2024" in text:
        doc_checks = ["laporan", "2024"]

    pasal = None
    pasal_match = re.search(r"pasal\s+(\d+)", text)
    if pasal_match:
        pasal = pasal_match.group(1)

    ayat = None
    ayat_match = re.search(r"ayat\s*\(?\s*(\d+)\s*\)?", text)
    if ayat_match:
        ayat = ayat_match.group(1)

    angka = None
    angka_match = re.search(r"angka\s+(\d+)", text)
    if angka_match:
        angka = angka_match.group(1)

    return {"doc_checks": doc_checks, "pasal": pasal, "ayat": ayat, "angka": angka}


def doc_text(doc: dict[str, Any]) -> str:
    meta = doc.get("metadata") or {}
    parts = [doc.get("content", "")]
    parts.extend(str(v) for v in meta.values() if isinstance(v, (str, int, float)))
    return " ".join(parts).lower()


def doc_matches(doc: dict[str, Any], expected: dict[str, Any]) -> bool:
    checks = expected.get("doc_checks") or []
    if not checks:
        return False
    text = doc_text(doc)
    return all(str(check).lower() in text for check in checks)


def section_matches(doc: dict[str, Any], expected: dict[str, Any]) -> bool:
    pasal = expected.get("pasal")
    if not pasal:
        return False
    text = doc_text(doc)
    if not re.search(rf"\bpasal\s+{re.escape(str(pasal))}\b", text):
        return False
    ayat = expected.get("ayat")
    if ayat and f"ayat ({ayat})" not in text and f"ayat {ayat}" not in text and f"({ayat})" not in text:
        return False
    angka = expected.get("angka")
    if angka and f"angka {angka}" not in text and not re.search(rf"\b{re.escape(str(angka))}\.", text):
        return False
    return True


def at_k(docs: list[dict[str, Any]], expected: dict[str, Any], predicate, k: int) -> bool:
    return any(predicate(doc, expected) for doc in docs[:k])


def evaluate_item(item: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    docs = response.get("docs") or []
    expected = expected_from_citation(item.get("sitasi", ""))
    return {
        "expected": expected,
        "doc_at_1": at_k(docs, expected, doc_matches, 1),
        "doc_at_3": at_k(docs, expected, doc_matches, 3),
        "doc_at_6": at_k(docs, expected, doc_matches, 6),
        "section_at_1": at_k(docs, expected, section_matches, 1),
        "section_at_3": at_k(docs, expected, section_matches, 3),
        "section_at_6": at_k(docs, expected, section_matches, 6),
        "top_sections": [
            {
                "document": (doc.get("metadata") or {}).get("document_title")
                or (doc.get("metadata") or {}).get("judul_dokumen")
                or (doc.get("metadata") or {}).get("filename"),
                "section": (doc.get("metadata") or {}).get("context_header")
                or (doc.get("metadata") or {}).get("pasal")
                or (doc.get("metadata") or {}).get("hierarchy"),
                "boost": (doc.get("metadata") or {}).get("query_boost"),
                "score": (doc.get("metadata") or {}).get("rerank_score"),
            }
            for doc in docs[:6]
        ],
    }


def pct(count: int, total: int) -> str:
    return f"{(count / total * 100 if total else 0):.2f}%"


def report(results: list[dict[str, Any]], raw_path: Path) -> str:
    total = len(results)
    metrics = ["doc_at_1", "doc_at_3", "doc_at_6", "section_at_1", "section_at_3", "section_at_6"]
    counts = {m: sum(1 for r in results if r["retrieval_eval"].get(m)) for m in metrics}

    lines = [
        "# Evaluasi Retrieval Ground Truth SPBE", "",
        f"Tanggal eksekusi: {datetime.now():%Y-%m-%d %H:%M:%S}", "",
        "## Ringkasan", "",
        f"- Total pertanyaan: {total}",
        f"- Document@1: {counts['doc_at_1']}/{total} ({pct(counts['doc_at_1'], total)})",
        f"- Document@3: {counts['doc_at_3']}/{total} ({pct(counts['doc_at_3'], total)})",
        f"- Document@6: {counts['doc_at_6']}/{total} ({pct(counts['doc_at_6'], total)})",
        f"- Section@1: {counts['section_at_1']}/{total} ({pct(counts['section_at_1'], total)})",
        f"- Section@3: {counts['section_at_3']}/{total} ({pct(counts['section_at_3'], total)})",
        f"- Section@6: {counts['section_at_6']}/{total} ({pct(counts['section_at_6'], total)})", "",
        "## Metodologi", "",
        "Evaluasi ini hanya mengukur retrieval melalui endpoint debug retrieval. Tidak ada structured fact lookup dan tidak ada penilaian jawaban LLM.", "",
        "## Detail", "",
        "| No | Pertanyaan | Sitasi Target | Doc@3 | Section@6 | Top Retrieval |",
        "|---:|---|---|---|---|---|",
    ]

    for r in results:
        gt = r["ground_truth"]
        ev = r["retrieval_eval"]
        top = "<br>".join(
            f"{i+1}. {str(s.get('document') or '-')[:70]} — {str(s.get('section') or '-')[:90]}"
            for i, s in enumerate(ev.get("top_sections", [])[:3])
        )
        lines.append(
            "| {no} | {q} | {sitasi} | {doc3} | {sec6} | {top} |".format(
                no=gt.get("nomor"),
                q=str(gt.get("pertanyaan", "")).replace("|", "\\|"),
                sitasi=str(gt.get("sitasi", "")).replace("|", "\\|"),
                doc3="YA" if ev.get("doc_at_3") else "TIDAK",
                sec6="YA" if ev.get("section_at_6") else "TIDAK",
                top=top.replace("|", "\\|"),
            )
        )

    lines += ["", "## File Pendukung", "", f"- Raw output: `{raw_path.name}`"]
    return "\n".join(lines) + "\n"


def parse_args() -> Any:
    parser = ArgumentParser(description="Evaluate retrieval coverage for SPBE ground truth questions.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--container", default="spbe-backend")
    parser.add_argument("--raw", default="hasil_evaluasi_retrieval_ground_truth_first10_raw.json")
    parser.add_argument("--report", default="HASIL_EVALUASI_RETRIEVAL_GROUND_TRUTH_FIRST10.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    subset = dataset[args.offset : args.offset + args.limit]
    bearer = token(args.container)
    results: list[dict[str, Any]] = []

    for item in subset:
        no = item["nomor"]
        print(f"[{no:02d}] {item['pertanyaan']}", flush=True)
        start = time.time()
        try:
            response = get_retrieval(item["pertanyaan"], bearer, args.base_url)
        except Exception as exc:
            response = {"error": repr(exc), "docs": []}
        retrieval_eval = evaluate_item(item, response)
        retrieval_eval["latency_wall_ms"] = int((time.time() - start) * 1000)
        print(
            "  doc@3={doc3} section@6={sec6}".format(
                doc3=retrieval_eval["doc_at_3"],
                sec6=retrieval_eval["section_at_6"],
            ),
            flush=True,
        )
        results.append({"ground_truth": item, "retrieval": response, "retrieval_eval": retrieval_eval})

    raw_path = ROOT / args.raw
    report_path = ROOT / args.report
    raw_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(report(results, raw_path), encoding="utf-8")
    print(f"Wrote {raw_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
