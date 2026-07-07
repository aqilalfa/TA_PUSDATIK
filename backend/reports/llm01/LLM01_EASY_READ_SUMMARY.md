# Ringkasan Mudah Dipahami — OWASP LLM01 Prompt Injection

## Status Singkat

Untuk scope **text-based SPBE RAG chatbot**, pekerjaan OWASP **LLM01:2025 Prompt Injection** sudah berada pada status:

```text
PASS WITH DOCUMENTED LIMITATIONS
```

Artinya:

- Sistem sudah diuji terhadap serangan prompt injection utama.
- Sistem sudah punya kontrol pencegahan berlapis.
- Hasil evaluasi menunjukkan tidak ada attack sukses pada dataset yang diuji.
- Batasan yang belum diuji juga sudah ditulis eksplisit agar tidak overclaim.

## Apa yang Dilindungi

LLM01 berhubungan dengan serangan yang mencoba membuat chatbot:

- mengabaikan aturan sistem,
- membuka prompt/instruksi internal,
- menjawab tanpa dokumen sumber,
- mengikuti instruksi jahat dari konteks/RAG,
- berperan sebagai admin/auditor internal palsu,
- membuat kode/konten di luar cakupan SPBE,
- mengikuti payload tersembunyi, encoded, multilingual, atau split prompt.

## Perubahan Utama yang Sudah Dilakukan

### 1. Dataset Serangan Diperluas

Sebelum:

- adversarial prompt masih sedikit.

Sesudah:

| Dataset | Jumlah | Tujuan |
|---|---:|---|
| Main adversarial | 130 | Uji utama LLM01 |
| Holdout adversarial | 40 | Ujian tambahan agar tidak overfit |
| Blind holdout adversarial | 50 | Ujian baru yang tidak dipakai tuning awal |
| Benign SPBE | 80 | Pastikan pertanyaan normal tidak salah ditolak |
| Domain boundary | 60 | Pastikan pertanyaan luar konteks ditangani aman |
| Grounding | 40 | Pastikan jawaban tetap berdasarkan dokumen |

Total adversarial unik:

```text
220 prompt
```

### 2. Guard-disabled ASR

Pengujian utama dilakukan dengan pre-LLM guard dimatikan:

```text
--guard-disabled
```

Tujuannya agar payload benar-benar masuk ke LLM/RAG path.

Ini penting karena kalau hanya mengandalkan pre-LLM blocker, ASR bisa terlihat bagus padahal model/RAG path belum benar-benar diuji.

### 3. Judge dan Metric Diperbaiki

Evaluator sekarang membedakan:

- attack sukses,
- safe refusal,
- source-limited answer,
- false positive,
- domain unsafe answer,
- severity: critical/high/medium/low/none.

False positive yang ditemukan tidak disembunyikan. Contoh:

```text
backend/reports/llm01/current/replay/holdout-031.json
```

### 4. Positive Control Ditambahkan

Agar evaluator tidak dituduh “selalu nol”, dibuat positive-control test.

Hasil:

| Positive Control | Result |
|---|---:|
| Synthetic attacks | 6 |
| Detected attacks | 6 |
| Positive-control ASR | 1.0000 |

Artinya harness/judge terbukti bisa mendeteksi attack jika output memang berbahaya.

### 5. Confidence Interval Ditambahkan

Karena hasil observed ASR adalah 0, report sekarang tidak overclaim.

Klaim statistik yang benar:

```text
0/220 observed successful attacks
95% upper bound Rule of Three ≈ 1.36%
```

Jadi bukan “mustahil ditembus”, melainkan:

> Pada distribusi adversarial yang diuji, observed ASR 0%, dengan batas atas 95% sekitar 1.36%.

### 6. Repeatability 3 Run

Pengujian diulang beberapa kali dan memakai worst-case, bukan run terbaik.

| Corpus | Runs | Worst-case ASR | Catatan |
|---|---:|---:|---|
| Blind holdout | 3 | 0.0000 | Stabil |
| Holdout | 3 | 0.0000 | Stabil |
| Domain boundary | 3 | 0.0000 | Ada worst unsafe domain answer 0.0167 |
| Grounding | 3 | 0.0000 | Ada worst FPR 0.0250 |

Catatan penting:

- Domain/grounding signal bukan prompt injection success.
- Itu dicatat sebagai quality/domain-policy/judge issue.

### 7. OWASP Mitigation Mapping Dibuat

Mapping resmi OWASP LLM01 sekarang ada di:

```text
backend/reports/llm01/OWASP_LLM01_MITIGATION_MAPPING.md
```

Status kontrol:

| OWASP Mitigation | Status |
|---|---|
| Constrain model behavior | Implemented |
| Define and validate expected output format | Implemented with streaming caveat |
| Input and output filtering | Implemented with layered guards |
| Privilege / least privilege | Implemented for app roles; LLM read-only |
| Human approval for risky actions | N/A karena read-only RAG |
| Segregate external content | Implemented |
| Adversarial testing | Implemented |

### 8. Output Guard Produksi Ditambahkan

File baru:

```text
backend/app/core/rag/output_guardrails.py
```

Test:

```text
backend/tests/test_llm01_output_guardrails.py
```

Output guard memblokir:

- prompt leak,
- internal/secret leak,
- source bypass,
- out-of-scope code,
- factual answer tanpa sitasi.

Output guard mengizinkan:

- jawaban SPBE dengan sitasi,
- safe refusal,
- source-limited answer,
- negated source-bypass.

### 9. RAG Context Ditandai Tidak Tepercaya

File:

```text
backend/app/core/rag/guardrails.py
```

Fungsi:

```python
sanitize_untrusted_context()
build_llm01_security_instruction()
```

Retrieved context dibungkus sebagai:

```text
BEGIN UNTRUSTED RETRIEVED CONTENT
...
END UNTRUSTED RETRIEVED CONTENT
```

Ini sesuai mitigasi OWASP: **segregate and identify external content**.

## Hasil Akhir LLM01

| Area | Result |
|---|---:|
| Main adversarial ASR | 0.0000 |
| Holdout worst-case ASR | 0.0000 |
| Blind holdout worst-case ASR | 0.0000 |
| Successful attacks | 0 |
| Runtime errors | 0 |
| Critical failures | 0 |
| High failures | 0 |
| Positive-control ASR | 1.0000 |
| Unique adversarial CI upper bound | ~1.36% |

## Batasan yang Tetap Jujur Ditulis

Belum diklaim:

1. Full poisoned-document ingestion test via Qdrant.
   - Saat ini sudah ada untrusted context segregation.
   - Tapi belum ada test end-to-end: malicious document → chunking → embedding → Qdrant → retrieval → LLM.

2. Public external benchmark dataset.
   - Dataset sekarang masih self-authored.

3. Two-reviewer judge validation / Cohen's kappa.
   - Judge validation sekarang single reviewer.

4. Multimodal injection.
   - Out-of-scope karena sistem yang diuji adalah text chat + text RAG context.

5. Strict no-token-before-validation.
   - Karena endpoint streaming, full-answer validation terjadi setelah generation.
   - Prompt/secret leak tetap dicek saat streaming.
   - Jika butuh strict mode, gunakan buffered response mode sebagai future upgrade.

## File Evidence Utama

Start here:

```text
backend/reports/llm01/current/CURRENT.md
```

Comprehensive report:

```text
backend/reports/llm01/OWASP_LLM01_COMPREHENSIVE_REPORT.md
```

Mitigation mapping:

```text
backend/reports/llm01/OWASP_LLM01_MITIGATION_MAPPING.md
```

Repeatability:

```text
backend/reports/llm01/repeatability/llm01_repeatability_summary_qwen35_4b.md
```

Judge validation:

```text
backend/reports/llm01/manual_judge_validation/llm01_judge_validation_report.md
```

RAG realism:

```text
backend/reports/llm01/LLM01_RAG_INDIRECT_INJECTION_REALISM.md
```

Reproducibility:

```text
backend/reports/llm01/LLM01_REPRODUCIBILITY_METADATA.md
```

Threat model:

```text
backend/reports/llm01/LLM01_THREAT_MODEL_AND_CATEGORY_MAPPING.md
```

Multimodal scope:

```text
backend/reports/llm01/LLM01_MULTIMODAL_SCOPE_NOTE.md
```

## Kesimpulan Mudahnya

Untuk scope saat ini:

```text
Text-based SPBE RAG chatbot
```

statusnya:

```text
OWASP LLM01:2025 aligned
PASS WITH DOCUMENTED LIMITATIONS
```

Klaim yang aman:

> Sistem sudah memiliki kontrol dan evidence yang selaras dengan OWASP LLM01 untuk text-based SPBE RAG. Observed ASR adalah 0/220 pada adversarial unik, dengan 95% upper bound sekitar 1.36%. Hasil repeatability tetap menunjukkan worst-case ASR 0.0000 untuk holdout dan blind holdout. Batasan seperti full poisoned-document ingestion, external public benchmark, two-reviewer validation, dan multimodal injection sudah dinyatakan eksplisit.
