"""
Sanity check quality gate lintas konteks (non-table) via SSE chat endpoint.

Fokus:
- Query definisi
- Query daftar/rincian
- Query perbandingan
- Query indikator

Output:
- Ringkasan PASS/FAIL per query
- Report JSON + Markdown di data/evaluation
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


URL = "http://localhost:8000/api/chat/stream"
MODEL = "qwen3.5:4b"
REQUEST_TIMEOUT = 420
TOP_K = 8

NEGATIVE_PHRASES = (
    "tidak tercantum",
    "tidak tersedia",
    "tidak ditemukan",
    "tidak ada informasi",
    "belum tersedia",
)

QUERIES = [
    (
        "Q1_DEFINISI_SPBE",
        "Apa definisi SPBE menurut Peraturan Menteri PAN RB Nomor 59 Tahun 2020?",
    ),
    (
        "Q2_DAFTAR_DOMAIN",
        "Sebutkan domain-domain dalam evaluasi SPBE berdasarkan dokumen yang tersedia.",
    ),
    (
        "Q3_PERBANDINGAN",
        "Jelaskan perbedaan utama antara pemantauan SPBE dan evaluasi SPBE.",
    ),
    (
        "Q4_INDIKATOR_KEBIJAKAN",
        "Sebutkan indikator pada Domain Kebijakan SPBE secara ringkas.",
    ),
]


def post_json(url: str, payload: Dict[str, Any], timeout: int) -> str:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc


def extract_complete_payload(sse_text: str) -> Dict[str, Any] | None:
    blocks = re.split(r"\r?\n\r?\n", str(sse_text or "").strip())
    for block in blocks:
        event_type = "message"
        data_lines: List[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip().lower()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())

        if event_type != "complete" or not data_lines:
            continue

        payload_text = "\n".join(data_lines)
        try:
            return json.loads(payload_text)
        except json.JSONDecodeError:
            return None
    return None


def evaluate_result(query_id: str, query_text: str, complete: Dict[str, Any]) -> Dict[str, Any]:
    answer = str(complete.get("answer") or "")
    answer_lower = answer.lower()
    sources = list(complete.get("sources") or [])
    quality = dict(complete.get("quality_check") or {})

    negative_hits = [phrase for phrase in NEGATIVE_PHRASES if phrase in answer_lower]
    citation_count = len(re.findall(r"\[(\d+)\]", answer))
    answer_len = len(answer)
    source_count = len(sources)

    conflicting_unavailable = bool(quality.get("has_unavailable_claim")) and bool(
        quality.get("focus_coverage", 0.0)
    )

    passed = (
        answer_len >= 180
        and source_count > 0
        and citation_count > 0
        and not negative_hits
        and not conflicting_unavailable
    )

    notes: List[str] = []
    if answer_len < 180:
        notes.append("jawaban terlalu pendek")
    if source_count == 0:
        notes.append("sources kosong")
    if citation_count == 0:
        notes.append("sitasi [n] tidak muncul")
    if negative_hits:
        notes.append("frasa unavailable terdeteksi")
    if conflicting_unavailable:
        notes.append("klaim unavailable bertentangan dengan coverage konteks")

    return {
        "id": query_id,
        "query": query_text,
        "verdict": "PASS" if passed else "FAIL",
        "answer_len": answer_len,
        "source_count": source_count,
        "citation_count": citation_count,
        "negative_hits": negative_hits,
        "quality_score": quality.get("score"),
        "needs_retry": quality.get("needs_retry"),
        "retry_reasons": quality.get("retry_reasons"),
        "focus_coverage": quality.get("focus_coverage"),
        "notes": notes,
        "preview": answer.replace("\n", " ").replace("\r", " ")[:220],
    }


def save_report(results: List[Dict[str, Any]]) -> Dict[str, str]:
    now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    repo_root = Path(__file__).resolve().parents[2]
    out_dir = repo_root / "data" / "evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "total": len(results),
        "pass": sum(1 for row in results if row.get("verdict") == "PASS"),
        "fail": sum(1 for row in results if row.get("verdict") == "FAIL"),
        "failed_ids": [row.get("id") for row in results if row.get("verdict") == "FAIL"],
    }

    payload = {
        "generated_at": now.isoformat(),
        "endpoint": URL,
        "model": MODEL,
        "summary": summary,
        "results": results,
    }

    json_path = out_dir / f"generic_quality_sanity_{ts}.json"
    md_path = out_dir / f"generic_quality_sanity_{ts}.md"

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Generic Quality Sanity",
        "",
        f"Generated at: {payload['generated_at']}",
        f"Endpoint: {URL}",
        f"Model: {MODEL}",
        "",
        "## Summary",
        f"- Total: {summary['total']}",
        f"- PASS: {summary['pass']}",
        f"- FAIL: {summary['fail']}",
        f"- Failed IDs: {', '.join(summary['failed_ids']) if summary['failed_ids'] else '-'}",
        "",
        "## Results",
        "",
        "| ID | Verdict | Score | Focus | Sources | Citations | AnswerLen | Notes |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]

    for row in results:
        note_text = "; ".join(row.get("notes") or []) or "-"
        lines.append(
            f"| {row['id']} | {row['verdict']} | {row.get('quality_score', 0)} | "
            f"{row.get('focus_coverage', 0)} | {row['source_count']} | {row['citation_count']} | "
            f"{row['answer_len']} | {note_text} |"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {"json": str(json_path), "md": str(md_path)}


def main() -> int:
    print("GENERIC_QUALITY_SANITY_START")
    print(f"URL={URL}")
    print(f"MODEL={MODEL}")
    print("---")

    results: List[Dict[str, Any]] = []

    for query_id, query_text in QUERIES:
        payload = {
            "message": query_text,
            "session_id": None,
            "use_rag": True,
            "top_k": TOP_K,
            "model": MODEL,
        }

        try:
            raw = post_json(URL, payload, REQUEST_TIMEOUT)
            complete = extract_complete_payload(raw)
            if not complete:
                row = {
                    "id": query_id,
                    "query": query_text,
                    "verdict": "FAIL",
                    "answer_len": 0,
                    "source_count": 0,
                    "citation_count": 0,
                    "negative_hits": [],
                    "quality_score": None,
                    "needs_retry": None,
                    "retry_reasons": ["SSE complete event tidak ditemukan"],
                    "focus_coverage": 0,
                    "notes": ["SSE complete event tidak ditemukan"],
                    "preview": "",
                }
            else:
                row = evaluate_result(query_id, query_text, complete)
        except Exception as exc:
            row = {
                "id": query_id,
                "query": query_text,
                "verdict": "FAIL",
                "answer_len": 0,
                "source_count": 0,
                "citation_count": 0,
                "negative_hits": [],
                "quality_score": None,
                "needs_retry": None,
                "retry_reasons": [f"Request error: {exc}"],
                "focus_coverage": 0,
                "notes": [f"Request error: {exc}"],
                "preview": "",
            }

        results.append(row)
        notes_text = "; ".join(row.get("notes") or []) or "-"
        print(
            f"{row['id']} VERDICT={row['verdict']} SCORE={row.get('quality_score')} "
            f"FOCUS={row.get('focus_coverage')} SOURCES={row['source_count']} "
            f"CIT={row['citation_count']} LEN={row['answer_len']}"
        )
        print(f"NOTES={notes_text}")
        if row.get("preview"):
            print(f"PREVIEW={row['preview']}")
        print("---")

    report_paths = save_report(results)
    total = len(results)
    passed = sum(1 for row in results if row.get("verdict") == "PASS")
    failed = total - passed

    print("GENERIC_QUALITY_SANITY_SUMMARY")
    print(f"TOTAL={total}")
    print(f"PASS={passed}")
    print(f"FAIL={failed}")
    print(f"REPORT_JSON={report_paths['json']}")
    print(f"REPORT_MD={report_paths['md']}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())