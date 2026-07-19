# PRODUCT REQUIREMENTS DOCUMENT (PRD)

## Fitur: Pemeriksaan Integritas Konteks pada Pipeline RAG

**Produk:** SPBE Asisten  
**Jenis perubahan:** Penambahan lapisan keamanan pada pipeline retrieval dan context assembly  
**Cakupan penelitian:** OWASP LLM08 Vector and Embedding Weaknesses  
**Prioritas:** Tinggi  
**Strategi implementasi:** Adaptasi pipeline context-assembly ke arsitektur yang sudah ada, tanpa mengganti arsitektur RAG, rumusan masalah, nama metode penelitian, model embedding, model generator, atau mekanisme retrieval utama.

---

## 1. Instruksi untuk Coding Agent

Anda adalah senior backend engineer dan AI/RAG security engineer. Lakukan implementasi secara bertahap, konservatif, dapat diuji, dan kompatibel dengan sistem yang sudah ada.

Sebelum menulis kode:

1. Audit struktur repository.
2. Temukan modul berikut:
   - document ingestion dan chunking;
   - embedding;
   - Qdrant vector retrieval;
   - BM25 retrieval;
   - literal search;
   - Reciprocal Rank Fusion;
   - reranking;
   - context stitching;
   - prompt construction;
   - role-based access filtering;
   - citation/source-card generation;
   - configuration dan logging;
   - test suite.
3. Dokumentasikan call graph pipeline saat ini.
4. Jangan menghapus atau mengganti komponen yang sudah ada.
5. Jangan mengubah hasil baseline tanpa feature flag.
6. Jangan menyalin istilah atau nama metode khusus dari paper sumber ke nama class, function, endpoint, tabel, log, atau dokumentasi produk.
7. Gunakan istilah generik:
   - `context integrity`
   - `local context consistency`
   - `context anomaly`
   - `secure context assembly`
   - padanan bahasa Indonesia pada dokumentasi pengguna.
8. Jangan mengubah mekanisme LLM01 dan LLM09.
9. Jangan mengubah role-based access control. Lapisan baru hanya boleh memperketat context assembly dan tidak boleh memperluas akses.
10. Jika terdapat ketidakjelasan repository, buat asumsi minimal, catat asumsi tersebut, lalu implementasikan dengan interface yang mudah diganti.

---

## 2. Latar Belakang

Pipeline SPBE Asisten saat ini menggunakan:

- vector search melalui Qdrant;
- BM25;
- literal search;
- Reciprocal Rank Fusion;
- reranking;
- context stitching;
- prompt construction;
- validasi jawaban dan sitasi;
- pembatasan akses berdasarkan role dan metadata.

Konten berbahaya atau faktual yang telah dimanipulasi dapat memiliki relevansi tinggi terhadap query sehingga tetap masuk ke hasil retrieval. Filter hak akses tidak menyelesaikan masalah tersebut apabila dokumen memang boleh diakses tetapi integritas isinya telah terganggu.

Fitur ini menambahkan pemeriksaan pada tahap setelah reranking dan sebelum konteks final dikirim ke LLM. Tujuannya bukan membuktikan kebenaran faktual secara universal, melainkan mengurangi kemungkinan unit konteks yang menyimpang dari lingkungan dokumennya mendominasi prompt.

---

## 3. Tujuan

### 3.1 Tujuan utama

Menambahkan lapisan pemeriksaan integritas konteks yang:

1. Memeriksa konsistensi semantik unit hasil retrieval terhadap unit di sekitarnya.
2. Memberi penalti pada unit yang sangat menyimpang.
3. Mengendalikan ekspansi konteks agar tidak memasukkan tetangga berisiko hanya karena berdekatan.
4. Menyusun konteks final berdasarkan relevansi, konsistensi lokal, risiko anomali, dan anggaran token.
5. Menjaga seluruh filter akses berbasis role tetap berlaku.
6. Menyediakan audit trail untuk menjelaskan mengapa suatu unit dipilih atau dibuang.
7. Dapat dinyalakan dan dimatikan untuk eksperimen baseline.

### 3.2 Hasil yang diharapkan

- Berkurangnya konten manipulatif yang masuk ke final prompt.
- Tidak ada regresi kontrol akses LLM08 yang sudah ada.
- Penurunan kualitas retrieval pada query normal tetap minimal.
- Overhead latensi dapat diukur dan dikendalikan.
- Implementasi mudah dievaluasi secara akademik melalui baseline, ablation, dan skenario poisoning terkontrol.

---

## 4. Non-Goals

Fitur ini tidak bertujuan untuk:

1. Mengganti vector search, BM25, literal search, RRF, atau reranking.
2. Mengganti model embedding atau LLM.
3. Mengubah seluruh corpus menjadi indeks sentence-level baru pada fase pertama.
4. Membuktikan bahwa suatu klaim benar secara hukum atau faktual.
5. Mendeteksi seluruh jenis data poisoning.
6. Menjamin ketahanan terhadap penyerang adaptif atau white-box.
7. Mengatasi prompt injection.
8. Mengubah mekanisme misinformation atau answer verification.
9. Mengubah rumusan masalah penelitian.
10. Menamai sistem atau fitur dengan nama metode dari paper sumber.

---

## 5. Terminologi Produk

Gunakan istilah berikut secara konsisten:

| Istilah | Definisi |
|---|---|
| Unit konteks | Potongan teks terkecil yang dinilai; dapat berupa kalimat, ayat, paragraf pendek, atau baris tabel |
| Kandidat konteks | Unit atau span yang berasal dari hasil retrieval dan reranking |
| Tetangga lokal | Unit sebelum dan sesudah kandidat dalam dokumen dan struktur yang sama |
| Konsistensi lokal | Kemiripan semantik kandidat terhadap tetangga lokal |
| Risiko anomali | Derajat penyimpangan kandidat dibanding distribusi konsistensi unit dalam kelompok lokal |
| Span konteks | Gabungan beberapa unit yang berdekatan dan memenuhi aturan ekspansi |
| Konteks final | Span terpilih yang dikirim ke prompt generator |
| Konten uji manipulatif | Unit sintetis berlabel khusus yang hanya digunakan oleh evaluator |

Jangan gunakan nama atau singkatan algoritma baru yang tidak diperlukan.

---

## 6. Arsitektur Target

### 6.1 Pipeline sebelum perubahan

```text
Query
→ Query classification/expansion
→ Qdrant + BM25 + literal search
→ Role and metadata filtering
→ RRF
→ Reranking
→ Context stitching
→ Prompt construction
→ LLM
→ Answer/citation validation
```

### 6.2 Pipeline setelah perubahan

```text
Query
→ Query classification/expansion
→ Qdrant + BM25 + literal search
→ Role and metadata filtering
→ RRF
→ Reranking
→ Context Integrity Processing
    → unit segmentation
    → neighbor loading
    → local consistency calculation
    → robust anomaly estimation
    → secure span expansion
    → final context selection
→ Prompt construction
→ LLM
→ Existing answer/citation validation
```

### 6.3 Aturan integrasi

1. Lapisan baru ditempatkan setelah reranking.
2. Context stitching lama tidak langsung dihapus.
3. Refactor context stitching lama menjadi bagian dari secure span expansion.
4. Role filtering harus dijalankan sebelum dan selama pengambilan tetangga.
5. Unit dari dokumen yang tidak berwenang tidak boleh digunakan untuk perhitungan skor, ekspansi, prompt, sitasi, atau debug response.
6. Jika fitur dimatikan, pipeline harus menghasilkan perilaku baseline.
7. Jika pemeriksaan integritas gagal secara teknis, sistem boleh kembali ke hasil reranking lama, tetapi tidak boleh melewati role filter. Kegagalan harus dicatat.

---

## 7. Functional Requirements

### FR-01 — Feature flag

Tambahkan konfigurasi:

```env
CONTEXT_INTEGRITY_ENABLED=false
CONTEXT_INTEGRITY_MODE=balanced
CONTEXT_INTEGRITY_DEBUG=false
```

Mode yang didukung:

- `off`
- `utility`
- `balanced`
- `security`

Default produksi pada tahap awal: `off`.  
Default eksperimen: `balanced`.

### FR-02 — Unit segmentation

Sistem harus dapat mengubah setiap chunk kandidat menjadi unit konteks.

Aturan:

1. Dokumen regulasi:
   - pertahankan ayat sebagai unit jika struktur ayat tersedia;
   - gunakan kalimat hanya di dalam ayat;
   - jangan memecah nomor pasal, nomor ayat, atau butir daftar secara buta.
2. Dokumen laporan/pedoman:
   - gunakan paragraf pendek atau kalimat.
3. Tabel:
   - perlakukan satu baris logis sebagai unit;
   - jangan gunakan sentence splitter umum.
4. Heading:
   - simpan sebagai metadata;
   - jangan nilai sebagai kalimat mandiri.
5. Unit terlalu pendek, boilerplate, nomor halaman, header/footer, dan tanda tangan harus ditandai atau dikeluarkan berdasarkan aturan yang sudah ada.

Interface yang disarankan:

```python
class ContextUnit:
    unit_id: str
    document_id: str
    chunk_id: str
    unit_index: int
    text: str
    structure_type: str
    section_id: str | None
    article_id: str | None
    paragraph_id: str | None
    table_id: str | None
    token_count: int
    allowed_roles: list[str]
    classification: str | None
    source_metadata: dict
```

### FR-03 — Neighbor loading

Untuk setiap unit kandidat, sistem harus dapat mengambil unit sebelum dan sesudahnya.

Aturan keamanan:

- dokumen harus sama;
- role harus diizinkan;
- klasifikasi harus kompatibel;
- jangan melewati batas dokumen;
- default jangan melewati batas pasal atau section;
- jangan menghubungkan tabel dengan paragraf naratif kecuali ada aturan eksplisit;
- jumlah tetangga dapat dikonfigurasi.

Konfigurasi:

```env
CONTEXT_NEIGHBOR_RADIUS=2
CONTEXT_ALLOW_CROSS_SECTION=false
```

### FR-04 — Embedding unit

Gunakan model embedding yang sudah digunakan sistem.

Prioritas implementasi:

1. Gunakan cache embedding unit jika tersedia.
2. Jika belum tersedia, hitung secara lazy dan simpan cache berdasarkan:
   - document hash;
   - chunk ID;
   - unit index;
   - embedding model version.
3. Jangan membuat model embedding baru.
4. Cache harus invalid jika isi dokumen atau model embedding berubah.

### FR-05 — Local context consistency

Hitung kemiripan kosinus antara unit kandidat dan tetangga yang valid.

Contoh:

```python
left_similarity = aggregate_similarity(unit, left_neighbors)
right_similarity = aggregate_similarity(unit, right_neighbors)
local_consistency = max(left_similarity, right_similarity)
```

Aturan:

- gunakan sisi yang tersedia;
- jika tidak ada tetangga valid, beri status `insufficient_neighbors`;
- unit tanpa tetangga tidak otomatis dianggap berbahaya;
- agregasi harus configurable: `mean` atau `max`;
- default awal: `max`, karena lebih toleran pada transisi dokumen.

### FR-06 — Robust anomaly estimation

Gunakan metode statistik robust dalam kelompok lokal, bukan threshold global tunggal.

Kelompok lokal:

- pasal atau section;
- jika tidak tersedia, chunk;
- jika masih tidak tersedia, dokumen.

Perhitungan awal:

```text
threshold = median(local_consistency_group) - k * MAD(local_consistency_group)
risk = max(0, threshold - local_consistency)
```

Konfigurasi:

```env
CONTEXT_ANOMALY_K_UTILITY=3.5
CONTEXT_ANOMALY_K_BALANCED=2.5
CONTEXT_ANOMALY_K_SECURITY=1.5
```

Catatan:

- angka merupakan konfigurasi awal untuk eksperimen, bukan konstanta ilmiah;
- semua nilai harus dapat diubah tanpa mengubah kode;
- simpan nilai median, MAD, threshold, dan risk untuk audit;
- jika MAD nol atau jumlah unit terlalu sedikit, gunakan fallback yang terdokumentasi, misalnya percentile atau neutral risk.

### FR-07 — Candidate span expansion

Bangun span dari unit yang diretrieve dan tetangga lokal.

Neighbor hanya ditambahkan jika:

1. hak akses valid;
2. struktur sesuai;
3. menambah relevansi atau melengkapi konteks;
4. risiko anomali tidak melewati batas keras;
5. token budget belum terlampaui;
6. unit belum digunakan dalam span lain atau dapat dideduplicasi.

Konfigurasi:

```env
CONTEXT_MAX_SPAN_UNITS=5
CONTEXT_MAX_SPAN_TOKENS=900
CONTEXT_HARD_RISK_THRESHOLD=0.35
```

### FR-08 — Span scoring

Gunakan skor transparan dan dapat diaudit:

```text
final_span_score =
    rerank_score
  + query_relevance_weight * query_relevance
  + consistency_weight * span_consistency
  - anomaly_weight * span_risk
  - token_weight * normalized_token_cost
```

Default awal:

```env
CONTEXT_QUERY_WEIGHT=0.35
CONTEXT_CONSISTENCY_WEIGHT=0.20
CONTEXT_ANOMALY_WEIGHT=0.35
CONTEXT_TOKEN_WEIGHT=0.10
```

Persyaratan:

- bobot harus configurable;
- log komponen skor;
- jangan menggunakan skor tunggal tanpa breakdown;
- `span_risk` default menggunakan risiko maksimum unit di dalam span;
- sediakan opsi eksperimen `mean` dan `max`.

### FR-09 — Final context selection

Pilih span berdasarkan skor per token sampai anggaran konteks terpenuhi.

Aturan:

- deduplicate unit yang sama;
- pertahankan urutan dokumen di dalam span;
- jangan mencampur source metadata;
- citation mapping harus tetap benar;
- konteks final harus tetap berbentuk data yang kompatibel dengan prompt constructor lama;
- source card hanya dibentuk dari unit yang benar-benar masuk final context.

Konfigurasi:

```env
CONTEXT_FINAL_TOKEN_BUDGET=3500
CONTEXT_MIN_SPANS=1
CONTEXT_MAX_SPANS=8
```

### FR-10 — Safe fallback

Jika seluruh kandidat dibuang:

1. jangan mengarang konteks;
2. gunakan fallback yang sudah tersedia pada sistem;
3. catat alasan:
   - `all_candidates_high_risk`;
   - `insufficient_authorized_context`;
   - `segmentation_failure`;
   - `embedding_failure`;
   - `assembly_budget_failure`.

Jangan mengubah teks fallback LLM09 kecuali diperlukan untuk kompatibilitas.

### FR-11 — Audit trail

Untuk setiap query, log terstruktur harus memuat:

```json
{
  "query_id": "...",
  "feature_enabled": true,
  "mode": "balanced",
  "user_role": "staff",
  "retrieved_chunk_ids": [],
  "candidate_unit_ids": [],
  "selected_unit_ids": [],
  "discarded_units": [
    {
      "unit_id": "...",
      "reason": "high_context_anomaly",
      "query_relevance": 0.0,
      "local_consistency": 0.0,
      "group_median": 0.0,
      "group_mad": 0.0,
      "risk": 0.0
    }
  ],
  "final_spans": [],
  "latency_ms": {
    "segmentation": 0,
    "embedding": 0,
    "scoring": 0,
    "assembly": 0,
    "total": 0
  }
}
```

Persyaratan:

- jangan kirim log debug ke frontend;
- jangan mencatat isi dokumen sensitif secara plaintext kecuali lingkungan pengujian yang disetujui;
- gunakan ID, hash, atau potongan tersanitasi;
- logging harus dapat dimatikan.

### FR-12 — Regression compatibility

Semua pengujian yang sudah ada harus tetap lulus:

- role parsing;
- fail-closed unknown role;
- Qdrant access filtering;
- BM25 access filtering;
- literal search filtering;
- context stitching role isolation;
- citation leak test;
- document API access test;
- malicious chunk isolation test;
- RAGAS pipeline;
- chat streaming;
- source card rendering.

---

## 8. Data Model dan Storage

### 8.1 Pendekatan fase pertama

Jangan membuat collection baru kecuali benar-benar diperlukan.

Simpan cache unit dan skor pada storage yang paling sesuai dengan repository:

- SQLite table baru;
- cache lokal persisten;
- atau payload tambahan yang tidak mengganggu collection lama.

Skema yang disarankan:

```sql
CREATE TABLE context_units (
    unit_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    unit_index INTEGER NOT NULL,
    structure_type TEXT NOT NULL,
    section_id TEXT,
    article_id TEXT,
    paragraph_id TEXT,
    table_id TEXT,
    text_hash TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_cache_key TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE(document_id, chunk_id, unit_index, text_hash)
);

CREATE TABLE context_integrity_cache (
    unit_id TEXT PRIMARY KEY,
    local_consistency REAL,
    group_median REAL,
    group_mad REAL,
    threshold_value REAL,
    risk_score REAL,
    scoring_version TEXT NOT NULL,
    computed_at DATETIME NOT NULL
);
```

Jangan simpan poison label pada tabel produksi. Label uji harus berada pada dataset evaluator terpisah.

---

## 9. API dan Interface Internal

Tidak diperlukan endpoint publik baru.

Buat service internal:

```python
class ContextIntegrityService:
    def process(
        self,
        query: str,
        query_embedding,
        ranked_chunks: list,
        user_context,
        token_budget: int
    ) -> ContextAssemblyResult:
        ...
```

Result:

```python
class ContextAssemblyResult:
    final_contexts: list
    selected_spans: list
    discarded_units: list
    metrics: dict
    fallback_reason: str | None
```

Komponen internal yang disarankan:

```text
ContextUnitSegmenter
AuthorizedNeighborLoader
UnitEmbeddingCache
LocalConsistencyScorer
RobustAnomalyEstimator
SecureSpanBuilder
ContextBudgetSelector
ContextIntegrityAuditLogger
```

Ikuti pola dependency injection yang sudah digunakan repository. Jangan membuat singleton global baru tanpa alasan.

---

## 10. Security Requirements

### SR-01

Neighbor loading wajib menggunakan filter role yang sama atau lebih ketat daripada retrieval utama.

### SR-02

Unit dari dokumen restricted tidak boleh digunakan untuk menghitung centroid, median, MAD, atau skor unit authorized.

### SR-03

Metadata kosong atau role tidak dikenal tidak boleh memperluas akses.

### SR-04

Context integrity processing tidak boleh mengubah `allowed_roles`, `classification`, `document_id`, atau metadata sumber.

### SR-05

Source card dan citation mapping harus dibentuk setelah final context selection.

### SR-06

Debug endpoint atau debug response tidak boleh mengungkap unit yang dibuang dari dokumen restricted.

### SR-07

Dataset poisoning harus sintetis dan terisolasi dari knowledge base produksi.

### SR-08

Jangan menambahkan eksekusi instruksi dari dokumen. Seluruh konten retrieval tetap diperlakukan sebagai data.

---

## 11. Performance Requirements

Target engineering awal:

- tambahan p95 latency context processing ≤ 15% dibanding baseline;
- cache hit embedding unit ≥ 90% setelah warm-up;
- penggunaan memori harus dibatasi dan terukur;
- tidak ada embedding ulang untuk unit yang hash dan modelnya tidak berubah;
- proses scoring harus dapat dibatalkan jika request timeout;
- token budget final tidak boleh melebihi konfigurasi prompt yang sudah ada.

Jika target tidak tercapai, agent harus menyertakan profiling dan rekomendasi optimasi.

---

## 12. Evaluation Dataset

Buat dataset pengujian terpisah dari produksi.

### 12.1 Clean set

Gunakan pertanyaan SPBE normal yang telah tersedia. Tujuannya mengukur regresi.

### 12.2 Poison set

Buat salinan sintetis dokumen publik atau dokumen dummy. Jangan mengubah dokumen resmi asli.

Kategori:

1. **Single obvious inconsistency**
   - satu unit faktual palsu yang tidak konsisten dengan konteks sekitar.
2. **Single context-matching inconsistency**
   - satu unit palsu dengan gaya dan terminologi yang menyerupai dokumen.
3. **Multi-unit context-matching inconsistency**
   - dua atau tiga unit palsu yang saling mendukung.
4. **Neighbor expansion contamination**
   - unit manipulatif tidak menjadi seed retrieval, tetapi berada di sebelah seed.
5. **High-query-similarity contamination**
   - unit manipulatif sengaja memuat istilah query target.
6. **Legitimate abrupt transition**
   - unit sah dengan istilah teknis atau perpindahan struktur untuk mengukur false positive.

Setiap kasus memuat:

```json
{
  "case_id": "...",
  "query": "...",
  "target_document_id": "...",
  "manipulated_unit_ids": [],
  "attacker_target": "...",
  "scenario_type": "...",
  "expected_authorized_roles": [],
  "notes": "..."
}
```

Label hanya digunakan evaluator.

---

## 13. Evaluation Metrics

Implementasikan laporan berikut.

### 13.1 Initial Manipulated Retrieval Rate

Persentase kasus ketika unit manipulatif masuk initial top-k retrieval.

### 13.2 Expansion Contamination Rate

Persentase kasus ketika unit manipulatif masuk kandidat karena neighbor expansion.

### 13.3 Final Context Inclusion Rate

Persentase kasus ketika unit manipulatif masuk final prompt context.

### 13.4 Conditional Survival Rate

Persentase unit manipulatif yang tetap masuk final context setelah sebelumnya diretrieve.

### 13.5 Targeted Attack Success Rate

Persentase jawaban yang mengadopsi target salah yang telah ditentukan pada dataset uji.

Jawaban salah yang tidak mengikuti target penyerang tidak dihitung sebagai keberhasilan serangan.

### 13.6 Clean utility

Bandingkan feature off dan feature on menggunakan:

- context precision;
- context recall;
- faithfulness;
- answer relevancy;
- citation/source mapping correctness;
- false fallback rate;
- latency.

### 13.7 Access-control regression

Harus tetap:

- unauthorized retrieval count = 0;
- citation leak count = 0;
- document leak count = 0;
- unknown role fail-closed = PASS.

---

## 14. Experiment Matrix

Agent harus menyediakan command atau script untuk menjalankan:

| ID | Pipeline |
|---|---|
| E0 | Existing pipeline, feature off |
| E1 | Unit segmentation + span assembly, anomaly penalty off |
| E2 | Full context integrity processing, utility mode |
| E3 | Full context integrity processing, balanced mode |
| E4 | Full context integrity processing, security mode |

Semua eksperimen harus menggunakan:

- query yang sama;
- corpus snapshot yang sama;
- embedding model yang sama;
- generator yang sama;
- prompt yang sama;
- top-k yang sama;
- token budget yang sama;
- random seed yang dicatat;
- versi kode yang dicatat.

---

## 15. Acceptance Criteria

### Wajib

1. Feature dapat dinyalakan/dimatikan tanpa perubahan kode.
2. Baseline lama tetap dapat dijalankan.
3. Semua regression test kontrol akses lulus.
4. Tidak ada context, citation, source card, atau debug leak lintas role.
5. Final context selection menyediakan breakdown skor.
6. Audit trail tersedia.
7. Dataset poisoning dan script evaluasi tersedia.
8. Feature tidak menggunakan poison label pada runtime.
9. Source card hanya berasal dari konteks final.
10. Dokumentasi menjelaskan keterbatasan.

### Target eksperimen awal

Target berikut adalah target engineering yang dapat dikalibrasi setelah baseline:

- Final Context Inclusion Rate pada poison set turun minimal 30% relatif terhadap E0.
- Targeted Attack Success Rate tidak lebih buruk daripada E0.
- Penurunan context recall clean ≤ 5% relatif.
- Peningkatan false fallback clean ≤ 5 poin persentase.
- Tambahan p95 latency ≤ 15%.
- Unauthorized retrieval, citation leak, dan document leak tetap 0.

Jangan memanipulasi threshold agar hanya memenuhi test set. Gunakan development set untuk konfigurasi dan holdout untuk hasil akhir.

---

## 16. Test Plan

### 16.1 Unit tests

- sentence/ayat/table segmentation;
- neighbor boundary;
- no cross-document expansion;
- no cross-role expansion;
- cosine consistency calculation;
- median/MAD calculation;
- zero-MAD fallback;
- span score breakdown;
- token-budget selection;
- deduplication;
- cache invalidation;
- feature flag off;
- failure fallback.

### 16.2 Integration tests

- Qdrant result → integrity processing;
- BM25 result → integrity processing;
- literal result → integrity processing;
- RRF/rerank score preservation;
- context selection → prompt constructor;
- context selection → citation mapper;
- context selection → source card;
- document deletion → cache invalidation;
- document re-index → score recalculation;
- streaming chat response.

### 16.3 Security tests

- staff cannot load admin-only neighbor;
- unknown role cannot load neighbor;
- restricted unit is not included in statistics for authorized public units;
- discarded restricted unit does not appear in debug;
- malicious unit as seed;
- malicious unit as neighbor;
- malicious unit in table;
- manipulated metadata;
- missing metadata;
- stale index after document deletion;
- cross-session and cross-role regression.

### 16.4 Evaluation tests

- E0–E4 experiment runner;
- clean dataset runner;
- poison dataset runner;
- absolute counts and percentages;
- per-scenario breakdown;
- failure analysis report;
- CSV/JSON export.

---

## 17. Observability

Tambahkan metrik internal:

```text
context_integrity_requests_total
context_integrity_failures_total
context_integrity_fallbacks_total
context_units_scored_total
context_units_discarded_total
context_units_selected_total
context_embedding_cache_hit_ratio
context_integrity_latency_ms
final_context_tokens
```

Jangan menambahkan dependency monitoring baru jika repository tidak menggunakannya. Gunakan logging atau metrics framework yang sudah tersedia.

---

## 18. Rollout Plan

### Tahap 1 — Shadow mode

- feature melakukan scoring;
- hasil belum memengaruhi final context;
- bandingkan keputusan baseline dan keputusan baru;
- kumpulkan latency dan false-positive candidates.

### Tahap 2 — Experiment mode

- feature memengaruhi final context hanya pada test environment;
- jalankan E0–E4;
- kalibrasi menggunakan development set.

### Tahap 3 — Limited enablement

- aktifkan `balanced` pada lingkungan demonstrasi;
- log audit aktif;
- rollback melalui feature flag.

### Tahap 4 — Final evaluation

- bekukan konfigurasi;
- jalankan holdout;
- ekspor hasil;
- jangan mengubah threshold setelah melihat hasil holdout.

---

## 19. Deliverables

Coding agent harus menghasilkan:

1. Laporan audit repository dan call graph awal.
2. Dokumen desain singkat.
3. Implementasi service context integrity.
4. Feature flags dan konfigurasi.
5. Migration/cache storage jika diperlukan.
6. Unit tests.
7. Integration tests.
8. Security regression tests.
9. Poisoning dataset generator atau fixture.
10. Experiment runner E0–E4.
11. Export CSV/JSON hasil.
12. Dokumentasi konfigurasi.
13. Dokumentasi keterbatasan.
14. Daftar file yang diubah.
15. Instruksi rollback.
16. Ringkasan hasil test dan profiling.

---

## 20. Definition of Done

Fitur dinyatakan selesai apabila:

- pipeline baseline tetap tersedia;
- feature baru terintegrasi setelah reranking;
- context stitching telah menggunakan aturan struktur, role, risiko, dan token budget;
- seluruh test wajib lulus;
- eksperimen baseline dan feature-on dapat direproduksi;
- hasil dapat diekspor;
- tidak ada perubahan pada rumusan masalah atau nama pendekatan utama sistem;
- dokumentasi menggunakan istilah generik;
- paper sumber hanya diposisikan sebagai inspirasi desain context-assembly;
- klaim implementasi dibatasi pada pengurangan propagasi konten manipulatif dalam skenario yang diuji.

---

## 21. Output Format yang Diharapkan dari Coding Agent

Pada akhir pekerjaan, berikan:

1. **Repository analysis**
2. **Implementation plan**
3. **Files changed**
4. **Architecture before/after**
5. **Configuration**
6. **Database/schema changes**
7. **Tests added**
8. **Commands to run**
9. **Evaluation procedure**
10. **Known limitations**
11. **Rollback steps**
12. **Open questions**

Jangan menyatakan implementasi selesai apabila test, evaluasi, atau audit trail belum tersedia.
