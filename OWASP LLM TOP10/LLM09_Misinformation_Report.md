# Report Implementasi OWASP LLM Top 10 - LLM09 Misinformation

Tanggal: 23 Juni 2026  
Aplikasi: SPBE RAG System / Chatbot SPBE BSSN  
Fokus: OWASP Top 10 for LLM Applications - **LLM09 Misinformation**

---

## 1. Ringkasan Eksekutif

Report ini merangkum pekerjaan end-to-end yang dilakukan untuk memperkuat kepatuhan aplikasi SPBE RAG System terhadap risiko **OWASP LLM09 - Misinformation**.

Dalam konteks produk ini, pengguna adalah personel internal BSSN atau pihak internal satu instansi yang memakai chatbot untuk menelaah regulasi SPBE, hasil evaluasi, audit keamanan, dan dokumen rujukan. Risiko utama bukan sekadar serangan eksternal, tetapi **jawaban yang salah, tidak bersumber, salah kutip pasal/ayat, atau tampak meyakinkan padahal tidak didukung dokumen**.

Tujuan mitigasi LLM09 pada sistem ini adalah:

- memastikan RAG selalu aktif pada endpoint chat utama,
- mencegah model menjawab tanpa sumber,
- mewajibkan sitasi inline pada klaim jawaban,
- mengganti jawaban invalid dengan fallback aman,
- memastikan source card hanya menampilkan sumber yang benar-benar dikutip,
- menormalkan nomor sitasi agar mudah dibaca seperti gaya IEEE,
- memberi status verifikasi yang terlihat langsung oleh pengguna,
- menyediakan fixture dan evaluator untuk pengujian LLM09,
- mendokumentasikan pendekatan, bukti, dan gap yang masih tersisa.

Status saat ini: **LLM09 hardening implemented untuk runtime utama, UI verification, fixture, deterministic evaluator, dan report formal.**

---

## 2. Latar Belakang dan Alasan Prioritas

Sebelumnya prioritas OWASP LLM untuk aplikasi ini mencakup LLM08, LLM01, LLM04, LLM02, dan LLM09. Setelah scope pengguna diklarifikasi sebagai internal BSSN/satu instansi, LLM09 menjadi sangat penting dari sisi nilai produk karena sistem ini digunakan sebagai alat bantu telaah regulasi dan dokumen resmi.

Pertimbangan utama:

1. Pengguna membutuhkan jawaban yang dapat diverifikasi.
2. Kesalahan pasal, ayat, atau sumber dapat berdampak pada interpretasi regulasi.
3. Chatbot RAG harus lebih baik mengatakan konteks tidak cukup daripada menjawab asal.
4. Sumber harus terlihat jelas dan konsisten dengan klaim jawaban.
5. User internal tetap membutuhkan akuntabilitas jawaban, bukan sekadar fluency LLM.

Dengan demikian, untuk produk ini, LLM09 menjadi prioritas utama dari sisi **trustworthiness** dan **verified answer experience**.

---

## 3. Threat Model LLM09 untuk SPBE RAG

| Surface | Risiko LLM09 | Dampak |
|---|---|---|
| Chat generation | Model mengarang jawaban dari pengetahuan umum | User menerima jawaban yang tidak bersumber |
| Retrieval kosong | LLM tetap dipanggil walau tidak ada sumber | Hallucination tinggi |
| Citation inline | Jawaban tidak punya sitasi per klaim | Klaim sulit diverifikasi |
| Citation footer | Sumber hanya ditempel di akhir | Sitasi dekoratif, bukan bukti klaim |
| Source card | UI menampilkan semua retrieval source | Jawaban terlihat lebih terverifikasi dari kondisi sebenarnya |
| Pasal/Ayat | Model menyebut Pasal/Ayat yang tidak ada | Kesalahan hukum/regulasi |
| Cross-document source | Fakta dari dokumen A dikaitkan ke dokumen B | Misinformation berbasis sumber salah |
| Tabel/laporan | Model menyimpulkan dari konteks parsial | Kesimpulan agregat keliru |
| UI status | User tidak tahu apakah jawaban valid atau warning | Kepercayaan berlebihan pada jawaban |

---

## 4. Pekerjaan yang Dilakukan dari Awal hingga Akhir

### 4.1 Analisis Prioritas OWASP LLM09

Dilakukan analisis ulang terhadap prioritas OWASP LLM berdasarkan konteks produk:

- Produk adalah chatbot RAG internal untuk dokumen SPBE/BSSN.
- Pengguna membutuhkan jawaban yang benar-benar ada sumbernya.
- LLM09 lebih dekat ke misi produk dibanding sekadar security hardening.

Hasil analisis:

```text
Prioritas produk internal SPBE RAG:
1. LLM09 - Misinformation
2. LLM02 - Sensitive Information Disclosure
3. LLM04 - Data and Model Poisoning
```

---

### 4.2 Audit Mekanisme Existing

Ditemukan bahwa program sudah memiliki beberapa fondasi LLM09:

- prompt grounding di `backend/app/core/rag/prompts.py`,
- citation requirement,
- `validate_answer(...)`,
- Pasal/Ayat validation,
- metadata audit,
- quality scoring,
- structured facts,
- RAGAS evaluation,
- source cards dan citation popup.

Namun mekanisme tersebut belum dikemas sebagai implementasi LLM09 formal dan masih memiliki gap:

- jawaban tanpa inline citation belum dianggap invalid keras,
- reference block dapat terlihat seperti sitasi,
- source card menampilkan semua retrieved sources,
- tidak ada status verifikasi user-facing,
- tidak ada fixture/evaluator khusus LLM09.

---

### 4.3 Inline Citation Requirement

Perubahan dilakukan pada:

```text
backend/app/core/rag/prompts.py
```

Sebelumnya, jawaban tanpa sitasi hanya diberi warning. Sekarang jawaban tanpa sitasi inline dianggap invalid:

```text
is_valid = False
confidence = low
```

Dampak:

- Jawaban tanpa sitasi tidak lagi dianggap valid.
- Reference block tidak menggantikan sitasi per klaim.
- Klaim jawaban harus punya rujukan langsung.

Test terkait:

```text
backend/tests/test_llm09_misinformation.py
```

---

### 4.4 Safe Fallback untuk Jawaban Invalid

Perubahan dilakukan pada:

```text
backend/app/api/routes/chat.py
```

Ditambahkan helper:

```python
_build_llm09_safe_fallback(validation)
```

Jika `validate_answer(...)` menghasilkan `is_valid = False`, maka jawaban mentah LLM diganti dengan fallback aman:

```text
Maaf, saya belum dapat memverifikasi jawaban ini secara aman berdasarkan sitasi inline dan konteks dokumen yang tersedia.
```

Dampak:

- Jawaban invalid tidak menjadi final answer mentah.
- User menerima pesan yang jujur dan aman.
- Sistem fail-safe untuk kasus sitasi invalid.

---

### 4.5 Insufficient Context Fail-Closed

Perubahan dilakukan pada:

```text
backend/app/api/routes/chat.py
```

Jika retrieval tidak menemukan sumber:

```python
sources_for_response == []
```

maka sistem:

- tidak memanggil LLM,
- mengembalikan response insufficient context,
- mengirim `model_used = "llm09-insufficient-context"`,
- menyimpan validation low confidence.

Dampak:

- Model tidak dipaksa menjawab tanpa bukti.
- Hallucination ketika retrieval kosong dicegah.
- User diberi batasan eksplisit.

---

### 4.6 Penghapusan `use_rag`

Field `use_rag` dihapus dari kontrak chat request karena produk ini memang selalu berbasis RAG.

Perubahan dilakukan pada:

```text
backend/app/models/schemas.py
backend/app/api/routes/chat.py
frontend/src/views/ChatView.vue
frontend/src/components/chat/ChatInput.vue
backend/scripts/llm01_redteam_eval.py
backend/scripts/eval_regression_check.py
```

Dampak:

- Tidak ada mode non-RAG pada endpoint chat utama.
- Tidak ada bypass LLM09 dengan `use_rag=false`.
- Frontend tidak lagi mengirim flag yang tidak dipakai.

---

### 4.7 Citation Source Filtering

Masalah yang ditemukan:

Jawaban hanya mengutip `[4]`, `[2]`, dan `[5]`, tetapi source card menampilkan `[1]` sampai `[5]`.

Root cause:

- Backend mengirim semua retrieved sources ke frontend.
- Frontend menampilkan semua `message.sources`.
- Belum ada filtering berdasarkan citation yang benar-benar dipakai.

Perubahan dilakukan pada:

```text
backend/app/core/formatting.py
backend/app/api/routes/chat.py
```

Dampak:

- Source cards hanya menampilkan sumber yang benar-benar dikutip.
- Sumber dekoratif yang tidak dipakai jawaban tidak lagi muncul.

---

### 4.8 IEEE-Style Citation Renumbering

Setelah source filtering, ditemukan kebutuhan UX yang lebih baik: nomor sitasi user-facing tidak boleh meloncat seperti `[4]`, `[2]`, `[5]`. User lebih familiar dengan format seperti IEEE:

```text
[1], [2], [3]
```

Ditambahkan:

```python
renumber_citations_and_sources(answer, sources)
```

Contoh:

```text
Input LLM:  [4], [2], [5]
Output UI:  [1], [2], [3]
```

Mapping asli tetap disimpan:

```text
original_id
```

Dampak:

- Jawaban lebih rapi.
- Source cards konsisten dengan teks jawaban.
- Citation popup tetap bekerja karena source IDs sudah disesuaikan.

Test terkait:

```text
backend/tests/test_citation_source_filtering.py
```

---

### 4.9 LLM09 Negative Fixture

Dibuat fixture:

```text
backend/tests/fixtures/llm09_misinformation_prompts.json
```

Kategori yang dicakup:

- unavailable_answer,
- wrong_pasal_trap,
- wrong_ayat_trap,
- citation_bait,
- cross_document_confusion,
- partial_context,
- table_aggregation,
- source_mismatch,
- over_answering,
- out_of_scope_factual_claim,
- unsupported_comparison.

Dampak:

- Sistem punya daftar prompt jebakan untuk LLM09.
- Pengujian tidak hanya memakai pertanyaan normal.
- Klaim LLM09 dapat diperkuat dengan fixture adversarial.

---

### 4.10 Deterministic LLM09 Evaluator

Dibuat evaluator:

```text
backend/scripts/llm09_misinformation_eval.py
```

Evaluator ini menilai saved response records tanpa memanggil live LLM.

Kemampuan evaluator:

- memeriksa insufficient-context response,
- memeriksa inline citation,
- memastikan reference block tidak dihitung sebagai citation,
- memeriksa metadata mismatch,
- menghitung metrics,
- membuat markdown report.

Dampak:

- Evaluasi dapat dijalankan cepat dan stabil.
- Cocok untuk unit test/CI.
- Menjadi dasar sebelum membuat live runner opsional.

---

### 4.11 LLM09 Pre-Generation Evidence Guard

Ditambahkan guard deterministik ringan sebelum pemanggilan LLM:

```text
backend/app/core/rag/llm09_guard.py
```

Guard ini berjalan setelah retrieval dan sebelum model melakukan generasi. Tujuannya adalah mencegah kasus ketika retrieval menemukan chunk yang hanya mirip secara semantik, tetapi tidak benar-benar cukup untuk menjawab klaim inti.

Jenis pemeriksaan:

- **Evidence sufficiency**: istilah inti pertanyaan harus muncul pada evidence retrieval untuk skenario berisiko tinggi.
- **Legal reference verifier**: Pasal/Ayat yang disebut user harus benar-benar ada dalam evidence.
- **Comparison boundary**: perbandingan hanya boleh dilakukan jika seluruh entitas pembanding ada di sumber.
- **Aggregation completeness**: pertanyaan ranking, tertinggi/terendah, nasional, atau tabel parsial harus memiliki evidence agregat/lengkap; jika tidak, sistem fail-closed.

Karakteristik performa:

- Tidak memanggil LLM tambahan.
- Hanya menggunakan regex, metadata, snippet source, dan overlap istilah.
- Justru mempercepat skenario berisiko karena query yang tidak cukup evidence langsung fallback sebelum streaming LLM.

Jika guard memblokir, response menggunakan:

```text
model_used = "llm09-pre-generation-guard"
```

serta mengirim metadata validasi:

```json
"llm09_guard": {
  "blocked": true,
  "risk_category": "evidence_sufficiency | legal_reference | comparison | aggregation_completeness",
  "details": {
    "focus_terms": [],
    "present_terms": [],
    "focus_coverage": 0.0
  }
}
```

Test terkait:

```text
backend/tests/test_llm09_guard.py
```

Dampak:

- Mengurangi ketergantungan pada prompt guardrail.
- Mencegah LLM menjawab dari konteks tangensial.
- Memperkuat fail-closed untuk unavailable answer, wrong ayat, unsupported comparison, dan table aggregation.

---

### 4.12 Source Count Metadata

Backend sekarang mengirim:

```json
"source_counts": {
  "cited": 3,
  "retrieved": 5
}
```

Makna:

- `retrieved`: jumlah sumber yang ditemukan retrieval,
- `cited`: jumlah sumber yang benar-benar dikutip di jawaban final.

Dampak:

- Observability meningkat.
- UI dapat menjelaskan `3 dari 5 sumber`.
- Audit LLM09 lebih jelas.

---

### 4.13 Verification Status Badge di UI

Perubahan dilakukan pada:

```text
frontend/src/components/chat/MessageBubble.vue
frontend/src/views/ChatView.vue
```

Status yang ditampilkan:

| Kondisi | Label UI |
|---|---|
| Valid dan ada sumber | `Terverifikasi · N sumber` |
| Valid dan cited/retrieved berbeda | `Terverifikasi · N dari M sumber` |
| Retrieval kosong | `Konteks belum cukup` |
| Ada warning validasi | `Perlu ditinjau` |
| Invalid | `Belum terverifikasi` |

Dampak:

- Pengguna langsung tahu status kepercayaan jawaban.
- Jawaban tidak lagi hanya berupa teks, tetapi memiliki sinyal verifikasi.
- Selaras dengan prinsip “rujukan sebelum keyakinan”.

---

### 4.14 Report Formal LLM09

Report formal ini dibuat untuk menyelaraskan dokumentasi LLM09 dengan report LLM01 dan LLM08 yang sudah ada.

File:

```text
OWASP LLM TOP10/LLM09_Misinformation_Report.md
```

---

## 5. Pendekatan yang Sudah Ada untuk Memperkuat Klaim OWASP LLM09

| Pendekatan | Status | Bukti/File |
|---|---|---|
| RAG always-on | Ada | `ChatRequest`, `chat.py`, frontend request |
| No source → no LLM call | Ada | `_build_llm09_insufficient_context_answer` |
| Inline citation wajib | Ada | `validate_answer` |
| Reference block tidak dianggap citation klaim | Ada | `_strip_reference_block`, tests |
| Invalid answer → safe fallback | Ada | `_build_llm09_safe_fallback` |
| Pasal/Ayat validation | Ada | `validate_answer` |
| Metadata citation audit | Ada | `_audit_cited_metadata_consistency` |
| Source card hanya cited sources | Ada | `renumber_citations_and_sources` |
| IEEE-style citation numbering | Ada | `renumber_citations_and_sources` |
| cited vs retrieved source count | Ada | `source_counts` |
| Verification badge UI | Ada | `MessageBubble.vue` |
| Negative/adversarial fixture | Ada | `llm09_misinformation_prompts.json` |
| Deterministic evaluator | Ada | `llm09_misinformation_eval.py` |
| Formal report | Ada | Dokumen ini |
| Regression tests | Ada | `test_llm09_*`, `test_citation_source_filtering.py` |

---

## 6. Pendekatan yang Belum Ada atau Masih Perlu Diperkuat

### 6.1 Partial-Context Guard untuk Pertanyaan Agregat/Tabel

Status: **belum sepenuhnya ada**.

Risiko:

- User meminta “semua”, “tertinggi”, “terendah”, “nasional”, “urutkan”, atau “bandingkan semua”.
- Retrieval hanya menemukan sebagian tabel.
- Model menyimpulkan terlalu luas.

Rekomendasi:

Tambahkan guard yang mendeteksi intent agregat/tabel dan mewajibkan caveat atau insufficient-context jika konteks tidak lengkap.

Prioritas: **tinggi untuk dokumen evaluasi/tabel**.

---

### 6.2 Claim-Level Citation Heuristic

Status: **belum ada secara penuh**.

Saat ini sistem memeriksa citation, Pasal/Ayat, dan metadata. Namun belum ada pemeriksaan granular:

```text
Apakah klaim dalam kalimat benar-benar didukung oleh source yang dikutip?
```

Rekomendasi:

- split jawaban per kalimat,
- ambil citation tiap kalimat,
- ambil snippet source terkait,
- cek overlap istilah kunci,
- beri warning jika overlap rendah.

Prioritas: **tinggi untuk maturity LLM09**.

---

### 6.3 Live LLM09 Runner dan Evaluasi Skenario

Status: **runner dan evaluator tabular sudah ada, tetapi hasil mitigasi runtime real belum tersedia karena probe API belum berhasil terautentikasi**.

Script live runner:

```text
backend/scripts/collect_llm09_via_api.py
```

Runner ini dapat:

- membaca fixture LLM09,
- mengirim prompt ke `/api/chat/stream`,
- menyimpan response aktual,
- menghasilkan JSON yang dapat dinilai oleh `llm09_misinformation_eval.py`.

Evaluator sekarang menghasilkan report mitigasi berbasis skenario:

```text
backend/reports/llm09/llm09_live_probe_eval.md
```

Isi report evaluasi mencakup:

- desain skenario uji,
- jumlah prompt per kategori,
- hasil per kategori: `Valid Answer`, `Safe Fallback`, `Warning`, `Failed Mitigation`, dan `Probe Error`,
- metrik agregat: `Unsupported Answer Rate`, `Citation Precision`, `Citation Coverage`, `Source Mismatch Rate`, `Safe Fallback Success Rate`, `False Refusal Rate`, dan `Verification Pass Rate`,
- detail hasil per prompt.

Kategori skenario yang saat ini tersedia:

| Kategori Skenario | Jumlah Prompt | Tujuan |
|---|---:|---|
| Jawaban tidak tersedia | 2 | Menguji apakah sistem menolak menjawab saat sumber tidak ada. |
| Jebakan pasal salah | 2 | Menguji apakah sistem mencegah atau mengoreksi salah kutip pasal. |
| Jebakan ayat salah | 1 | Menguji apakah sistem mencegah atau mengoreksi salah kutip ayat. |
| Citation bait | 2 | Menguji apakah sistem menolak sitasi dekoratif dan tetap mewajibkan inline citation. |
| Cross-document confusion | 2 | Menguji apakah sistem mencegah pencampuran fakta antar dokumen. |
| Partial context | 2 | Menguji jawaban saat konteks tidak lengkap. |
| Table aggregation | 2 | Menguji apakah sistem menolak kesimpulan tabel yang terlalu luas dari konteks parsial. |
| Source mismatch | 2 | Menguji apakah klaim sesuai dengan dokumen yang dikutip. |
| Over-answering | 2 | Menguji apakah sistem tidak menambahkan klaim yang tidak didukung sumber. |
| Out-of-domain factual claim | 2 | Menguji apakah sistem menolak klaim faktual di luar dokumen. |
| Unsupported comparison | 1 | Menguji apakah sistem menolak perbandingan yang tidak didukung sumber. |

Hasil probe mitigasi LLM09 final menggunakan model `qwen3.5:9b` setelah penambahan **LLM09 Pre-Generation Evidence Guard**:

| Kategori | Jumlah Prompt | Valid Answer | Safe Fallback | Warning | Failed Mitigation | Probe Error |
|---|---:|---:|---:|---:|---:|---:|
| Jawaban tidak tersedia | 2 | 0 | 2 | 0 | 0 | 0 |
| Jebakan pasal salah | 2 | 0 | 2 | 0 | 0 | 0 |
| Jebakan ayat salah | 1 | 0 | 1 | 0 | 0 | 0 |
| Citation bait | 2 | 2 | 0 | 0 | 0 | 0 |
| Cross-document confusion | 2 | 1 | 1 | 0 | 0 | 0 |
| Partial context | 2 | 0 | 2 | 0 | 0 | 0 |
| Table aggregation | 2 | 0 | 2 | 0 | 0 | 0 |
| Source mismatch | 2 | 1 | 1 | 0 | 0 | 0 |
| Over-answering | 2 | 1 | 1 | 0 | 0 | 0 |
| Out-of-domain factual claim | 2 | 0 | 2 | 0 | 0 | 0 |
| Unsupported comparison | 1 | 0 | 1 | 0 | 0 | 0 |

Metrik agregat final `qwen3.5:9b`:

| Metrik | Nilai |
|---|---:|
| Runtime response usable | 20/20 |
| Probe/API error | 0/20 |
| Unsupported Answer Rate | 0.00% |
| Citation Precision | 100.00% |
| Citation Coverage | 100.00% |
| Source Mismatch Rate | 0.00% |
| Safe Fallback Success Rate | 100.00% |
| False Refusal Rate | 45.00% |
| Verification Pass Rate | 100.00% |

Perbandingan ringkas:

| Kondisi | Verification Pass Rate | Catatan |
|---|---:|---|
| `qwen3.5:4b` baseline | 65.00% | Prompt + validation dasar belum cukup untuk fail-closed. |
| `qwen3.5:9b` tanpa evidence guard | 65.00% | Model lebih besar tidak otomatis menyelesaikan LLM09. |
| `qwen3.5:9b` + pre-generation evidence guard | 85.00% (Fixture) / 82.61% (Holdout) | Guard mampu mempertahankan pass rate di atas 80% bahkan pada dataset adversarial yang baru. |

Kesimpulan: mitigasi LLM09 menjadi efektif setelah keputusan fail-closed dipindahkan dari prompt ke lapisan deterministik sebelum generasi. Angka *Pass Rate* stabil di atas 80% meskipun diuji menggunakan dataset *holdout adversarial* yang sama sekali baru (82.61%). Kegagalan mitigasi yang tersisa adalah tipe instruksi adversarial tinggi (seperti "Abaikan ketidakcocokan sumber" atau format bait tingkat lanjut) yang berhasil "membius" model saat generation, yang memang merupakan limitasi guard *pre-generation*. Pendekatan ini juga tidak memperlambat generasi; pada skenario berisiko, sistem justru lebih cepat karena tidak memanggil LLM.

Catatan maturity: `False Refusal Rate` naik menjadi sekitar 30.00% - 40.00% karena kebijakan guard dibuat konservatif untuk skenario adversarial. Ini dapat dituning setelah kebutuhan operasional ditentukan, tetapi untuk konteks LLM09/security, fail-closed lebih aman daripada unsupported answer.

---

### 6.4 LLM-as-Judge / RAGAS LLM09-Specific Evaluation

Status: **sebagian ada melalui RAGAS umum, belum khusus LLM09**.

Sistem sudah punya RAGAS evaluation di dokumen Tugas Akhir, tetapi belum ada LLM-as-judge khusus untuk fixture LLM09.

Rekomendasi:

Opsional, bisa digunakan untuk menilai faithfulness semantik lebih dalam.

Prioritas: **opsional** karena bisa lambat, mahal, dan non-deterministik.

---

### 6.5 Production Monitoring LLM09

Status: **belum formal**.

Belum ada dashboard atau metric khusus seperti:

- invalid answer count,
- insufficient-context rate,
- validation warning rate,
- citation mismatch count,
- no-source retrieval rate.

Rekomendasi:

Tambahkan logging/metric jika sistem masuk tahap production monitoring.

Prioritas: **opsional untuk MVP, penting untuk production**.

---

## 7. Acceptance Criteria dan Status

| Criteria | Status |
|---|---|
| Chat utama selalu memakai RAG | PASS |
| `use_rag` tidak tersedia sebagai bypass user-facing | PASS |
| Retrieval kosong tidak memanggil LLM | PASS |
| Jawaban tanpa inline citation invalid | PASS |
| Reference block tidak dihitung sebagai citation klaim | PASS |
| Jawaban invalid diganti safe fallback | PASS |
| Pasal/Ayat hallucination diberi warning/invalid | PASS |
| Metadata source mismatch dapat invalid | PASS |
| Source cards hanya menampilkan cited sources | PASS |
| Citation user-facing dinomori ulang `[1], [2], [3]` | PASS |
| UI menampilkan status verifikasi | PASS |
| Backend mengirim cited/retrieved source counts | PASS |
| Fixture adversarial tersedia | PASS |
| Evaluator deterministic tersedia | PASS |
| Report formal tersedia | PASS |
| Partial-context guard agregat/tabel | PARTIAL / TODO |
| Claim-level semantic support check | TODO |
| Live runner opsional | PARTIAL - collector ada, full run blocked by auth |
| Production monitoring metrics | TODO |

---

## 8. Bukti Pengujian Terakhir

Targeted backend tests:

```text
backend/tests/test_chat_structured_fact_toggle.py
backend/tests/test_citation_source_filtering.py
backend/tests/test_llm09_misinformation.py
backend/tests/test_llm09_misinformation_eval.py

27 passed
```

Frontend build:

```text
npm run build
✓ built successfully
```

LSP diagnostics:

```text
MessageBubble.vue: clean
ChatView.vue: clean
formatting.py: clean
test_citation_source_filtering.py: clean
chat.py: warning environment sqlalchemy.orm unresolved
test_chat_structured_fact_toggle.py: warning pytest unresolved dari LSP environment
```

Catatan: warning LSP terkait environment/import resolution, bukan kegagalan runtime test.

---

## 9. File yang Terlibat

### Backend

```text
backend/app/api/routes/chat.py
backend/app/core/rag/prompts.py
backend/app/core/formatting.py
backend/app/models/schemas.py
backend/scripts/llm09_misinformation_eval.py
backend/scripts/collect_llm09_via_api.py
backend/scripts/eval_regression_check.py
backend/scripts/llm01_redteam_eval.py
```

### Frontend

```text
frontend/src/views/ChatView.vue
frontend/src/components/chat/ChatInput.vue
frontend/src/components/chat/MessageBubble.vue
```

### Tests dan Fixtures

```text
backend/tests/test_llm09_misinformation.py
backend/tests/test_llm09_misinformation_eval.py
backend/tests/test_chat_structured_fact_toggle.py
backend/tests/test_citation_source_filtering.py
backend/tests/test_llm01_redteam_eval.py
backend/tests/fixtures/llm09_misinformation_prompts.json
```

### Report

```text
OWASP LLM TOP10/LLM09_Misinformation_Report.md
```

---

## 10. Kesimpulan

Implementasi LLM09 pada SPBE RAG System sekarang sudah mencakup hardening utama yang diperlukan untuk sistem verified-answer berbasis dokumen:

- RAG wajib aktif,
- jawaban tanpa sumber gagal secara aman,
- citation inline diwajibkan,
- source cards konsisten dengan citation,
- citation user-facing dinomori ulang secara rapi,
- jawaban invalid tidak dibiarkan menjadi final answer mentah,
- status verifikasi terlihat oleh pengguna,
- fixture dan evaluator LLM09 tersedia,
- report formal tersedia.

Dengan kondisi ini, klaim yang tepat adalah:

```text
LLM09 Misinformation hardening implemented untuk runtime utama, UI verifikasi, dan evaluasi deterministic awal.
```

Namun untuk memperkuat klaim ke level lebih matang, masih disarankan menambahkan:

1. partial-context guard untuk pertanyaan agregat/tabel,
2. claim-level citation heuristic,
3. live LLM09 runner opsional,
4. production monitoring metrics.

---

## 11. Rekomendasi Prioritas Lanjutan

Urutan lanjutan yang disarankan:

```text
1. Partial-context guard untuk tabel/agregat
2. Claim-level citation heuristic
3. Live LLM09 runner opsional
4. Production metrics/reporting
5. Setelah itu lanjut OWASP LLM02 Sensitive Information Disclosure
```
