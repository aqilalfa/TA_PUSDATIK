from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.request
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "ground_truth_evaluasi_chatbot.json"
BASE_URL = "http://localhost"

MODES = {
    "structured": {
        "title": "Hasil Evaluasi Structured Fact terhadap Ground Truth SPBE",
        "raw": ROOT / "hasil_evaluasi_chatbot_ground_truth_structured_raw.json",
        "report": ROOT / "HASIL_EVALUASI_CHATBOT_GROUND_TRUTH_STRUCTURED.md",
        "use_structured_fact": True,
        "methodology": (
            "Evaluasi ini mengizinkan `structured fact fallback`. Hasilnya mengukur kemampuan sistem "
            "mencocokkan pertanyaan benchmark ke indeks fakta terstruktur/curated, bukan kemampuan "
            "generalisasi RAG murni. Angka akurasi pada mode ini tidak boleh diklaim sebagai akurasi RAG umum."
        ),
    },
    "pure-rag": {
        "title": "Hasil Evaluasi Pure RAG terhadap Ground Truth SPBE",
        "raw": ROOT / "hasil_evaluasi_chatbot_ground_truth_pure_rag_raw.json",
        "report": ROOT / "HASIL_EVALUASI_CHATBOT_GROUND_TRUTH_PURE_RAG.md",
        "use_structured_fact": False,
        "methodology": (
            "Evaluasi ini menonaktifkan `structured fact fallback` melalui payload "
            "`use_structured_fact=false`, sehingga jawaban harus melewati retrieval RAG generik dan LLM. "
            "Mode ini lebih tepat untuk mengukur kemampuan generalisasi RAG terhadap pertanyaan ground truth."
        ),
    },
}


def token() -> str:
    code = "from app.auth.jwt_manager import jwt_manager; print(jwt_manager.create_access_token({'sub':'admin@bssn.go.id'}))"
    out = subprocess.check_output(["docker", "exec", "spbe-backend-prod", "python", "-c", code], text=True, stderr=subprocess.STDOUT)
    return out.strip().splitlines()[-1]


def post_json(path: str, bearer: str, payload: dict[str, Any], timeout: int = 60) -> dict[str, Any]:
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ask(bearer: str, q: str, no: int, *, use_structured_fact: bool) -> dict[str, Any]:
    session = post_json("/api/sessions/", bearer, {"user_id": 2, "title": f"Evaluasi Ground Truth #{no}"})
    payload = {
        "session_id": session["id"],
        "message": q,
        "use_rag": True,
        "use_structured_fact": use_structured_fact,
        "top_k": 6,
        "max_tokens": 512,
        "max_quality_retries": 0,
    }
    req = urllib.request.Request(
        BASE_URL + "/api/chat/stream",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
        method="POST",
    )
    start = time.time()
    with urllib.request.urlopen(req, timeout=420) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    current = None
    complete = None
    for line in raw.splitlines():
        if line.startswith("event: "):
            current = line[7:].strip()
        elif line.startswith("data: ") and current == "complete":
            complete = json.loads(line[6:])
            break
    if complete is None:
        complete = {"answer": "", "sources": [], "error": "complete event not found", "raw_tail": raw[-2000:]}
    complete["latency_wall_ms"] = int((time.time() - start) * 1000)
    return complete


STOP = {"yang","dan","dengan","untuk","dalam","adalah","atau","pada","oleh","secara","serta","dari","ke","di","atas","guna","melalui","yaitu","apa","siapa","saja","tahun","nomor","pasal","ayat","halaman","huruf"}


def toks(s: str) -> set[str]:
    return {x for x in re.findall(r"[a-zA-Z0-9]+", (s or "").lower()) if len(x) > 2 and x not in STOP}


def cite_ok(sitasi: str, answer: str, sources: list[dict[str, Any]]) -> bool:
    text = " ".join([answer] + [str(v) for src in sources for v in [src.get("document"), src.get("document_short"), src.get("section"), src.get("hierarchy")]]).lower()
    s = sitasi.lower()
    checks: list[str] = []
    if "perpres nomor 95" in s: checks = ["95", "2018"]
    elif "permenpan" in s: checks = ["59", "2020"]
    elif "perpres nomor 82" in s: checks = ["82", "2023"]
    elif "peraturan bssn nomor 8" in s: checks = ["8", "2024"]
    elif "pp nomor 71" in s: checks = ["71", "2019"]
    elif "peraturan bssn nomor 2" in s: checks = ["2", "2023"]
    elif "laporan evaluasi spbe tahun 2024" in s: checks = ["laporan", "2024"]
    return all(c in text for c in checks) if checks else bool(sources)


def judge(item: dict[str, Any], comp: dict[str, Any]) -> dict[str, Any]:
    answer = comp.get("answer", "") or ""
    sources = comp.get("sources", []) or []
    overlap = len(toks(item["jawaban"]) & toks(answer)) / max(1, len(toks(item["jawaban"])))
    citation = cite_ok(item["sitasi"], answer, sources)
    unavailable = any(x in answer.lower() for x in ["tidak tersedia", "tidak ditemukan", "tidak dapat", "maaf"])
    if unavailable or overlap < 0.35:
        verdict = "SALAH"
    elif overlap >= 0.75 and citation:
        verdict = "BENAR"
    elif overlap >= 0.55:
        verdict = "SEBAGIAN"
    else:
        verdict = "SALAH"
    notes = []
    if unavailable: notes.append("jawaban menyatakan informasi tidak tersedia")
    if overlap < 0.75: notes.append(f"cakupan kata kunci {overlap:.0%}")
    if not citation: notes.append("sitasi/dokumen sumber tidak cocok")
    if not notes: notes.append("substansi dan sumber utama sesuai")
    return {"verdict": verdict, "answer_overlap": round(overlap, 4), "citation_match": citation, "source_count": len(sources), "notes": "; ".join(notes)}


def esc(x: Any) -> str:
    return str(x or "").replace("|", "\\|").replace("\n", "<br>")


def source_summary(sources: list[dict[str, Any]]) -> str:
    if not sources: return "-"
    return "<br>".join(f"[{i+1}] {s.get('document_short') or s.get('document')} — {s.get('section','-')}" for i, s in enumerate(sources[:3]))


def report(results: list[dict[str, Any]], *, mode: str, metadata: dict[str, Any]) -> str:
    counts = {k: sum(1 for r in results if r["evaluation"]["verdict"] == k) for k in ["BENAR", "SEBAGIAN", "SALAH"]}
    total = len(results)
    lines = [
        f"# {metadata['title']}", "",
        f"Tanggal eksekusi: {datetime.now():%Y-%m-%d %H:%M:%S}", "",
        "## Ringkasan", "",
        f"- Mode evaluasi: `{mode}`",
        f"- Structured fact fallback: {'aktif' if metadata['use_structured_fact'] else 'nonaktif'}",
        f"- Total pertanyaan: {total}",
        f"- BENAR: {counts['BENAR']}",
        f"- SEBAGIAN: {counts['SEBAGIAN']}",
        f"- SALAH: {counts['SALAH']}",
        f"- Akurasi ketat: {(counts['BENAR']/total*100 if total else 0):.2f}%",
        f"- Akurasi toleran: {((counts['BENAR']+counts['SEBAGIAN'])/total*100 if total else 0):.2f}%", "",
        "## Metodologi Singkat", "",
        "Setiap pertanyaan ground truth dikirim ke endpoint `POST /api/chat/stream`. Jawaban akhir diambil dari event SSE `complete`, lalu dinilai berdasarkan kesesuaian substansi dan sitasi sumber.", "",
        metadata["methodology"], "",
        "## Tabel Hasil Evaluasi", "",
        "| No | Pertanyaan | Ground Truth | Jawaban Chatbot | Sitasi Ground Truth | Sumber Chatbot | Verdict | Catatan |",
        "|---:|---|---|---|---|---|---|---|",
    ]
    for r in results:
        gt = r["ground_truth"]; comp = r["chatbot"]; ev = r["evaluation"]
        lines.append(f"| {gt['nomor']} | {esc(gt['pertanyaan'])} | {esc(gt['jawaban'])} | {esc((comp.get('answer') or '')[:1200])} | {esc(gt['sitasi'])} | {esc(source_summary(comp.get('sources', []) or []))} | **{ev['verdict']}** | {esc(ev['notes'])} |")
    lines += ["", "## File Pendukung", "", f"- Dataset: `{DATASET.name}`", f"- Raw output: `{metadata['raw'].name}`"]
    return "\n".join(lines) + "\n"


def parse_args() -> Any:
    parser = ArgumentParser(description="Evaluasi chatbot terhadap ground truth SPBE.")
    parser.add_argument(
        "--mode",
        choices=sorted(MODES),
        default="pure-rag",
        help="Mode evaluasi. Default pure-rag agar tidak mencampur akurasi RAG dengan structured fact lookup.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata = MODES[args.mode]
    raw_path = metadata["raw"]
    report_path = metadata["report"]
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    results = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else []
    done = {r["ground_truth"]["nomor"] for r in results}
    bearer = token()
    for item in dataset:
        no = item["nomor"]
        if no in done:
            continue
        print(f"[{no:02d}/{len(dataset)}] {item['pertanyaan']}", flush=True)
        try:
            comp = ask(
                bearer,
                item["pertanyaan"],
                no,
                use_structured_fact=bool(metadata["use_structured_fact"]),
            )
        except Exception as exc:
            comp = {"answer": "", "sources": [], "error": repr(exc)}
        results.append({"ground_truth": item, "chatbot": comp, "evaluation": judge(item, comp)})
        raw_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path.write_text(report(results, mode=args.mode, metadata=metadata), encoding="utf-8")
    print(f"Wrote {raw_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
