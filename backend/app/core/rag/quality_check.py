import re
import json
from typing import List, Dict, Any
from loguru import logger

HARD_UNAVAILABLE_CLAIM_PATTERNS = (
    "tidak tercantum",
    "tidak tersedia",
    "tidak ditemukan",
    "tidak ada informasi",
    "belum tersedia",
    "tidak secara eksplisit",
    "belum dijelaskan",
)

CONTEXTUAL_PARTIAL_CLAIM_PATTERNS = (
    "hanya mencantumkan",
    "hanya memuat",
)

CONTEXTUAL_PARTIAL_NEGATION_PATTERN = re.compile(
    r"hanya\s+(?:mencantumkan|memuat)[^\n\r\.;:]{0,140}\b(?:tanpa|tidak|belum|sementara)\b",
    re.IGNORECASE,
)

LOCAL_EVIDENCE_PATTERNS = (
    re.compile(r"\b\d+(?:[.,]\d+)?\b"),
    re.compile(r"tahap\s+(?:persiapan|pelaksanaan|pelaporan)", re.IGNORECASE),
    re.compile(r"indikator\s*\d", re.IGNORECASE),
    re.compile(r"aspek\s*\d", re.IGNORECASE),
    re.compile(r"domain\s*\d", re.IGNORECASE),
    re.compile(r"\b(?:sangat\s+baik|baik|cukup|kurang|memuaskan)\b", re.IGNORECASE),
    re.compile(r"bobot[^\n]{0,40}\d", re.IGNORECASE),
    re.compile(r"\[\d+\]"),
)

LOCAL_EVIDENCE_WINDOW = 140

GENERIC_STOPWORDS = {
    "yang", "dan", "atau", "dari", "pada", "untuk", "dalam", "dengan", "sebagai", 
    "adalah", "agar", "maka", "karena", "apa", "siapa", "bagaimana", "kapan", 
    "dimana", "berdasarkan", "menurut", "tolong", "jelaskan", "sebutkan", "isi", 
    "tentang", "nomor", "tahun", "pasal", "ayat", "dokumen", "peraturan", 
    "tersebut", "itu", "ini", "dapat", "jika", "mohon",
}

LIST_INTENT_PATTERN = re.compile(
    r"\b(?:apa saja|sebutkan|daftar|rincian|langkah|tahap|komponen|indikator|poin)\b",
    re.IGNORECASE,
)

LIST_ITEM_PATTERN = re.compile(r"(?m)^\s*(?:\d+[\.)]|[-*])\s+")

TABLE_QUERY_PATTERN = re.compile(
    r"\b(?:tabel|table)\s*(?:ke[-\s]*)?\d{1,3}\b",
    re.IGNORECASE,
)

def _has_local_evidence(window: str) -> bool:
    if not window:
        return False
    return any(pat.search(window) for pat in LOCAL_EVIDENCE_PATTERNS)

def find_unavailable_triggers(text: str) -> List[Dict[str, Any]]:
    content = str(text or "")
    if not content:
        return []
    content_l = content.lower()
    triggers: List[Dict[str, Any]] = []

    for phrase in HARD_UNAVAILABLE_CLAIM_PATTERNS:
        start = 0
        while True:
            pos = content_l.find(phrase, start)
            if pos < 0:
                break
            wstart = max(0, pos - LOCAL_EVIDENCE_WINDOW)
            wend = min(len(content), pos + len(phrase) + LOCAL_EVIDENCE_WINDOW)
            window = content[wstart:wend]
            suppressed = _has_local_evidence(window)
            triggers.append({
                "phrase": phrase,
                "pattern_type": "hard",
                "position": pos,
                "window": window,
                "local_evidence_present": suppressed,
                "suppressed": suppressed,
            })
            start = pos + len(phrase)

    for match in CONTEXTUAL_PARTIAL_NEGATION_PATTERN.finditer(content_l):
        pos = match.start()
        wstart = max(0, pos - LOCAL_EVIDENCE_WINDOW)
        wend = min(len(content), match.end() + LOCAL_EVIDENCE_WINDOW)
        window = content[wstart:wend]
        suppressed = _has_local_evidence(window)
        triggers.append({
            "phrase": match.group(0),
            "pattern_type": "contextual",
            "position": pos,
            "window": window,
            "local_evidence_present": suppressed,
            "suppressed": suppressed,
        })
    return triggers

def contains_unavailable_signal(text: str) -> bool:
    return any(not t["suppressed"] for t in find_unavailable_triggers(text))

def extract_focus_terms(query: str, max_terms: int = 8) -> List[str]:
    tokens = re.findall(r"[a-zA-Z0-9]{2,}", str(query or "").lower())
    focus_terms: List[str] = []
    for token in tokens:
        if token in GENERIC_STOPWORDS: continue
        if token.isdigit() and len(token) < 2: continue
        if not token.isdigit() and len(token) < 3: continue
        if token not in focus_terms:
            focus_terms.append(token)
        if len(focus_terms) >= max_terms: break
    return focus_terms

def build_answer_quality_report(query: str, context: str, answer: str, source_count: int) -> Dict[str, Any]:
    answer_text = str(answer or "").strip()
    answer_lower = answer_text.lower()
    context_lower = str(context or "").lower()

    query_focus_terms = extract_focus_terms(query)
    context_focus_terms = [t for t in query_focus_terms if bool(re.search(rf"\b{re.escape(t)}\b", context_lower))]
    answer_focus_terms = [t for t in context_focus_terms if bool(re.search(rf"\b{re.escape(t)}\b", answer_lower))]

    focus_coverage = len(answer_focus_terms) / len(context_focus_terms) if context_focus_terms else 1.0
    
    triggers = find_unavailable_triggers(answer_text)
    active_triggers = [t for t in triggers if not t["suppressed"]]
    has_unavailable = bool(active_triggers)
    conflicting = has_unavailable and bool(context_focus_terms)

    list_intent = bool(LIST_INTENT_PATTERN.search(str(query or ""))) or bool(TABLE_QUERY_PATTERN.search(str(query or "")))
    
    # Check list structure
    has_list = bool(LIST_ITEM_PATTERN.search(answer_text))
    if not has_list:
        ordinal_hits = len(re.findall(r"\b(?:pertama|kedua|ketiga|keempat|kelima|keenam)\b", answer_lower))
        has_list = ordinal_hits >= 2
    
    list_structure_ok = (not list_intent) or has_list
    citations = len(re.findall(r"\[(\d+)\]", answer_text))
    
    score = 0
    score += min(12, len(answer_text) // 120)
    score += int(10 * focus_coverage)
    score += 4 if citations > 0 else -4
    score += 3 if list_structure_ok else -4
    score += 2 if source_count > 0 else -8
    if has_unavailable: score -= 4
    if conflicting: score -= 6

    retry_reasons = []
    if conflicting: retry_reasons.append("klaim tidak tersedia bertentangan dengan konteks")
    if focus_coverage < 0.45 and context_focus_terms: retry_reasons.append("cakupan istilah inti pertanyaan masih rendah")
    if not list_structure_ok: retry_reasons.append("format rincian/daftar belum lengkap")
    if citations == 0: retry_reasons.append("sitasi [n] belum muncul")
    if len(answer_text) < 180: retry_reasons.append("jawaban terlalu ringkas")

    return {
        "score": score,
        "needs_retry": bool(retry_reasons),
        "retry_reasons": retry_reasons,
        "focus_coverage": round(focus_coverage, 4),
        "query_focus_terms": query_focus_terms,
        "context_focus_terms": context_focus_terms,
        "answer_focus_terms": answer_focus_terms,
        "has_unavailable_claim": has_unavailable,
        "conflicting_unavailable_claim": conflicting,
        "list_intent": list_intent,
        "list_structure_ok": list_structure_ok,
        "citation_count": citations,
        "source_count": source_count,
        "answer_length": len(answer_text),
        "unavailable_triggers_active": active_triggers,
        "unavailable_triggers_suppressed": [t for t in triggers if t["suppressed"]],
    }
