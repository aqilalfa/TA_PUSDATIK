"""
Audit jawaban tabel Permenpan RB 59/2020 (Tabel 1-14) via SSE endpoint.

Tujuan:
- Menanyakan isi Tabel 1 s.d. 14.
- Menilai apakah jawaban "benar" dan "lengkap" dengan heuristik yang konsisten.
- Menghasilkan kesimpulan otomatis jika ada tabel yang gagal.
"""

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


NEGATIVE_PHRASES = [
    "tidak tercantum",
    "tidak tersedia",
    "tidak ditemukan",
    "tidak ada informasi",
    "belum tersedia",
]

# Keyword inti dipakai sebagai sanity check tambahan untuk tabel yang sudah jelas targetnya.
EXPECTED_KEYWORDS: Dict[int, List[str]] = {
    8: ["aspek", "bobot"],
    10: ["domain", "indikator"],
    12: ["indeks", "predikat"],
    13: ["sangat baik", "baik", "cukup", "memuaskan"],
    14: ["tahap persiapan", "tahap pelaksanaan", "tahap pelaporan"],
}

TABLE_REF_PATTERN = re.compile(r"\btabel\s+(\d{1,2})\b", re.IGNORECASE)
LIST_ITEM_PATTERN = re.compile(r"(?m)^\s*(?:\d+[\.)]|[-*])\s+")


def extract_complete_payload(sse_text: str) -> Dict[str, Any] | None:
    """Ambil payload JSON dari event SSE 'complete'."""
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


def is_permenpan_59_source(source: Dict[str, Any]) -> bool:
    document = str(source.get("document", ""))
    section = str(source.get("section", ""))
    text = f"{document} {section}".lower()

    if "59 tahun 2020" in text and ("permenpan" in text or "peraturan" in text):
        return True

    return "pemantauan dan evaluasi sistem pemerintahan berbasis elektronik" in text


def build_query(table_no: int) -> str:
    return (
        f"Pada Permenpan RB Nomor 59 Tahun 2020, apa isi dari Tabel {table_no}? "
        "Jelaskan poin utamanya secara ringkas namun lengkap."
    )


def post_json(url: str, payload: Dict[str, Any], timeout: int) -> str:
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {details}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc


def evaluate_answer(
    table_no: int,
    query: str,
    complete_payload: Dict[str, Any],
    min_answer_len: int,
    min_sources: int,
    min_list_items: int,
) -> Dict[str, Any]:
    answer = str(complete_payload.get("answer", ""))
    answer_lower = answer.lower()
    sources = list(complete_payload.get("sources") or [])
    quality = complete_payload.get("quality_check") or {}
    active_triggers = list(quality.get("unavailable_triggers_active") or [])
    trigger_phrases = sorted({str(t.get("phrase", "")) for t in active_triggers if t.get("phrase")})

    # Gunakan active triggers dari quality gate sebagai sumber authoritative.
    # Raw scan NEGATIVE_PHRASES sengaja tidak dipakai karena quality gate sudah
    # membedakan frasa deskriptif (disupress) vs klaim absen genuine (aktif).
    # Fallback ke raw scan hanya jika backend tidak mengembalikan quality_check.
    if quality and "unavailable_triggers_active" in quality:
        negative_hits = trigger_phrases
    else:
        negative_hits = [phrase for phrase in NEGATIVE_PHRASES if phrase in answer_lower]

    table_refs = [int(x) for x in TABLE_REF_PATTERN.findall(answer_lower)]
    has_target_table = table_no in table_refs or f"tabel {table_no}" in answer_lower
    other_table_refs = sorted({x for x in table_refs if x != table_no})

    list_items = len(LIST_ITEM_PATTERN.findall(answer))
    if list_items == 0:
        list_items = len(
            re.findall(r"\b(?:pertama|kedua|ketiga|keempat|kelima|keenam)\b", answer_lower)
        )

    expected_keywords = EXPECTED_KEYWORDS.get(table_no, [])
    expected_hit_list = [kw for kw in expected_keywords if kw in answer_lower]
    expected_ok = True
    if expected_keywords:
        min_expected_hits = max(1, (len(expected_keywords) + 1) // 2)
        expected_ok = len(expected_hit_list) >= min_expected_hits

    permenpan_source_count = sum(1 for source in sources if is_permenpan_59_source(source))

    is_correct = has_target_table and permenpan_source_count > 0 and not negative_hits

    detail_ok = list_items >= min_list_items or expected_ok
    is_complete = (
        len(answer) >= min_answer_len
        and len(sources) >= min_sources
        and detail_ok
        and not negative_hits
    )

    notes: List[str] = []
    if not has_target_table:
        notes.append("jawaban tidak menyebut tabel target")
    if permenpan_source_count == 0:
        notes.append("sources tidak mengarah ke Permenpan 59/2020")
    if negative_hits:
        notes.append("jawaban memuat frasa unavailable")
    if len(answer) < min_answer_len:
        notes.append(f"jawaban terlalu pendek (<{min_answer_len} karakter)")
    if len(sources) < min_sources:
        notes.append(f"sources kurang dari {min_sources}")
    if not detail_ok:
        notes.append("rincian tabel belum cukup")
    if expected_keywords and not expected_ok:
        notes.append("keyword penting tabel belum cukup terpenuhi")
    if other_table_refs and not has_target_table:
        notes.append(f"indikasi salah rujuk tabel: {other_table_refs}")

    verdict = "PASS" if (is_correct and is_complete) else "FAIL"

    return {
        "table": table_no,
        "query": query,
        "verdict": verdict,
        "is_correct": is_correct,
        "is_complete": is_complete,
        "has_target_table": has_target_table,
        "answer_len": len(answer),
        "source_count": len(sources),
        "permenpan_source_count": permenpan_source_count,
        "list_items": list_items,
        "negative_hits": negative_hits,
        "expected_hits": len(expected_hit_list),
        "expected_total": len(expected_keywords),
        "other_table_refs": other_table_refs,
        "quality_score": quality.get("score"),
        "focus_coverage": quality.get("focus_coverage"),
        "unavailable_triggers_active": active_triggers,
        "unavailable_trigger_phrases": trigger_phrases,
        "notes": notes,
        "preview": answer.replace("\n", " ").replace("\r", " ")[:240],
    }


def summarize_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    passed = sum(1 for row in results if row.get("verdict") == "PASS")
    failed_rows = [row for row in results if row.get("verdict") == "FAIL"]

    notes_counter: Counter[str] = Counter()
    for row in failed_rows:
        for note in row.get("notes", []):
            notes_counter[note] += 1

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "correct_failed": sum(1 for row in results if not row.get("is_correct")),
        "complete_failed": sum(1 for row in results if not row.get("is_complete")),
        "failed_tables": [row.get("table") for row in failed_rows],
        "top_failure_reasons": notes_counter.most_common(5),
    }


def build_conclusion(summary: Dict[str, Any]) -> str:
    if summary["failed"] == 0:
        return (
            "Semua jawaban Tabel 1-14 dinilai benar dan lengkap berdasarkan kriteria audit yang dipakai. "
            "Tidak ada anomali mayor yang perlu tindakan lanjutan."
        )

    reason_parts = [f"{reason} ({count}x)" for reason, count in summary["top_failure_reasons"]]
    reasons_text = "; ".join(reason_parts) if reason_parts else "indikator error umum"
    failed_tables = ", ".join(f"T{n}" for n in summary["failed_tables"])

    return (
        "Sebagian jawaban tabel belum konsisten benar dan lengkap. "
        f"Tabel yang perlu follow-up: {failed_tables}. "
        f"Penyebab dominan: {reasons_text}. "
        "Kesimpulan: masih perlu tuning retrieval/ranking/format jawaban pada tabel gagal "
        "sebelum dapat dianggap stabil penuh."
    )


def save_reports(
    results: List[Dict[str, Any]],
    summary: Dict[str, Any],
    conclusion: str,
    url: str,
    model: str,
) -> Dict[str, str]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    repo_root = Path(__file__).resolve().parents[2]
    out_dir = repo_root / "data" / "evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"permenpan59_tabel_1_14_audit_{timestamp}.json"
    md_path = out_dir / f"permenpan59_tabel_1_14_audit_{timestamp}.md"

    payload = {
        "generated_at": datetime.now().isoformat(),
        "endpoint": url,
        "model": model,
        "summary": summary,
        "conclusion": conclusion,
        "results": results,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Audit Tabel 1-14 Permenpan RB 59/2020",
        "",
        f"Generated at: {payload['generated_at']}",
        f"Endpoint: {url}",
        f"Model: {model}",
        "",
        "## Ringkasan",
        f"- Total tabel diuji: {summary['total']}",
        f"- PASS: {summary['passed']}",
        f"- FAIL: {summary['failed']}",
        f"- Gagal aspek benar: {summary['correct_failed']}",
        f"- Gagal aspek lengkap: {summary['complete_failed']}",
        f"- Failed tables: {', '.join('T'+str(n) for n in summary['failed_tables']) or '-'}",
        "",
        "## Hasil per Tabel",
        "",
        "| Tabel | Verdict | Benar | Lengkap | HasTabel | Sources | AnswerLen | Score | Triggers | Notes |",
        "|---|---|---|---|---|---:|---:|---:|---|---|",
    ]

    for row in results:
        note_text = "; ".join(row["notes"]) if row["notes"] else "-"
        trigger_text = (
            ", ".join(row.get("unavailable_trigger_phrases") or [])
            or "-"
        )
        score = row.get("quality_score")
        score_text = str(score) if score is not None else "-"
        has_tabel = row.get("has_target_table", "?")
        lines.append(
            f"| {row['table']} | {row['verdict']} | {row['is_correct']} | {row['is_complete']} | "
            f"{has_tabel} | {row['source_count']} | {row['answer_len']} | {score_text} | {trigger_text} | {note_text} |"
        )

    lines.extend(["", "## Kesimpulan", "", conclusion, ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {"json": str(json_path), "md": str(md_path)}


def run_audit(args: argparse.Namespace) -> int:
    table_numbers = list(range(args.start_table, args.end_table + 1))
    if not table_numbers:
        print("ERROR=NO_TABLES_TO_TEST")
        return 1

    results: List[Dict[str, Any]] = []

    print("TABLE_AUDIT_1_14_START")
    print(f"URL={args.url}")
    print(f"MODEL={args.model}")
    print(f"TABLE_RANGE={args.start_table}-{args.end_table}")
    print("---")

    for table_no in table_numbers:
        query = build_query(table_no)
        payload = {
            "message": query,
            "session_id": None,
            "use_rag": True,
            "top_k": args.top_k,
            "model": args.model,
        }

        try:
            raw_response = post_json(
                url=args.url,
                payload=payload,
                timeout=args.request_timeout,
            )
            complete_payload = extract_complete_payload(raw_response)

            if not complete_payload:
                row = {
                    "table": table_no,
                    "query": query,
                    "verdict": "FAIL",
                    "is_correct": False,
                    "is_complete": False,
                    "answer_len": 0,
                    "source_count": 0,
                    "permenpan_source_count": 0,
                    "list_items": 0,
                    "negative_hits": [],
                    "expected_hits": 0,
                    "expected_total": len(EXPECTED_KEYWORDS.get(table_no, [])),
                    "other_table_refs": [],
                    "notes": ["SSE complete event tidak ditemukan"],
                    "preview": "",
                }
            else:
                row = evaluate_answer(
                    table_no=table_no,
                    query=query,
                    complete_payload=complete_payload,
                    min_answer_len=args.min_answer_len,
                    min_sources=args.min_sources,
                    min_list_items=args.min_list_items,
                )

        except Exception as exc:
            row = {
                "table": table_no,
                "query": query,
                "verdict": "FAIL",
                "is_correct": False,
                "is_complete": False,
                "answer_len": 0,
                "source_count": 0,
                "permenpan_source_count": 0,
                "list_items": 0,
                "negative_hits": [],
                "expected_hits": 0,
                "expected_total": len(EXPECTED_KEYWORDS.get(table_no, [])),
                "other_table_refs": [],
                "notes": [f"Request error: {exc}"],
                "preview": "",
            }

        results.append(row)
        notes_text = "; ".join(row["notes"]) if row["notes"] else "-"
        neg_text = ", ".join(row["negative_hits"]) if row["negative_hits"] else "-"

        print(
            f"T{table_no} VERDICT={row['verdict']} "
            f"BENAR={row['is_correct']} LENGKAP={row['is_complete']} "
            f"NEG={neg_text} SOURCES={row['source_count']} LEN={row['answer_len']}"
        )
        print(f"NOTES={notes_text}")
        if row["preview"]:
            print(f"PREVIEW={row['preview']}")
        print("---")

    summary = summarize_results(results)
    conclusion = build_conclusion(summary)
    report_paths = save_reports(
        results=results,
        summary=summary,
        conclusion=conclusion,
        url=args.url,
        model=args.model,
    )

    print("TABLE_AUDIT_1_14_SUMMARY")
    print(f"TOTAL={summary['total']}")
    print(f"PASS={summary['passed']}")
    print(f"FAIL={summary['failed']}")
    print(f"FAILED_TABLES={summary['failed_tables']}")
    print(f"TOP_FAILURE_REASONS={summary['top_failure_reasons']}")
    print(f"REPORT_JSON={report_paths['json']}")
    print(f"REPORT_MD={report_paths['md']}")
    print(f"KESIMPULAN={conclusion}")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit jawaban isi tabel Permenpan RB 59/2020 untuk Tabel 1-14."
    )
    parser.add_argument("--url", default="http://localhost:8000/api/chat/stream")
    parser.add_argument("--model", default="qwen3.5:4b")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--request-timeout", type=int, default=420)
    parser.add_argument("--start-table", type=int, default=1)
    parser.add_argument("--end-table", type=int, default=14)
    parser.add_argument("--min-answer-len", type=int, default=500)
    parser.add_argument("--min-sources", type=int, default=3)
    parser.add_argument("--min-list-items", type=int, default=3)
    args = parser.parse_args()

    if args.start_table < 1 or args.end_table < args.start_table:
        parser.error("Rentang tabel tidak valid. Contoh valid: --start-table 1 --end-table 14")
    return args


if __name__ == "__main__":
    raise SystemExit(run_audit(parse_args()))
