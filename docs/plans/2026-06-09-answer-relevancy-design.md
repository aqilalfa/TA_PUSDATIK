# Design: Peningkatan Answer Relevancy SPBE RAG

**Tanggal:** 2026-06-09  
**Status:** Draft  
**Masalah:** Answer Relevancy RAGAS = 0.6672 (dari 40 pertanyaan)

---

## 1. Root Cause Analysis

Berdasarkan inspeksi jawaban aktual dari `eval_results_spbe_rag_after_precision_tuning_round2.json`:

### Pola A — "Tidak Ditemukan" Meski Ada (AR = 0.0)

**GT-007:** "Apa tujuan diadakannya Tata Kelola SPBE?"
- GT: *"Memastikan penerapan unsur-unsur SPBE dilaksanakan secara terpadu."*
- Jawaban aktual: "...informasi mengenai definisi spesifik atau "tujuan" diadakannya Tata Kelola SPBE secara eksplisit **tidak tercantum** dalam konteks referensi... Dokumen hanya mendefinisikan Tata Kelola SPBE sebagai kerangka kerja untuk **memastikan** terlaksananya... penerapan SPBE secara **terpadu**..."
- **Root cause:** Model mendeteksi jawaban tidak *eksplisit* berbentuk "Tujuan X adalah..." sehingga mendeklarasikan keterbatasan, lalu menjawab sebagian di kalimat berikutnya. RAGAS judge menganggap jawaban tidak langsung = tidak relevan.

**GT-021:** "Apa yang dimaksud dengan Aplikasi SPBE Prioritas?"  
- GT: *"Aplikasi SPBE berdampak luas yang merupakan wujud nyata layanan SPBE berkualitas dan tepercaya."*
- Jawaban aktual: "...definisi spesifik mengenai 'Aplikasi SPBE Prioritas' **tidak ditemukan**... Dokumen hanya mendefinisikan Aplikasi SPBE secara umum..."
- **Root cause:** Retrieval gagal (CP=0, CR=0) — chunk definisi Perpres 82/2023 tidak masuk top-5. Masalah retrieval, bukan prompt.

### Pola B — Jawaban Benar + Intro Panjang + Header Sektoral (AR ≈ 0.43–0.48)

**GT-032:** "Apa sanksi administratif...?"
- GT: 1 kalimat list sederhana
- Jawaban: Mulai dengan "1. **Jenis Sanksi Administratif**" → panjang 1191 chars
- **Root cause:** Classifier `_classify_question_type` sudah benar mengembalikan `"list"`, tapi model menambahkan sub-header numbered "1. Jenis... 2. Pelaksana..." yang tidak diminta

**GT-028:** "Aspek apa saja yang harus dipenuhi..."?  
- GT: "kecukupan dan ketepatan" (6 kata)
- Jawaban: 870 chars dengan nested bullet + elaborasi setiap aspek
- **Root cause:** Tipe `"list"` masih memberi ruang untuk elaborasi setiap item

### Pola C — Jawaban Inti Benar + Tambahan Tidak Diminta (AR ≈ 0.47–0.58)

**GT-033, GT-037:** Jawab inti di kalimat pertama ✅, lalu tambahkan paragraf kedua yang tidak diminta
- **Root cause:** Aturan `"Jika jawaban inti sudah cukup, berhenti"` tidak dipatuhi oleh model

### Pola D — Format List Panjang tanpa "Stop Signal" (GT-008, AR ≈ 0.43)

- Daftar disertai prefix "sebagaimana diatur dalam Pasal 4..." yang tidak perlu
- **Root cause:** Tidak ada instruksi eksplisit untuk **tidak** menambahkan pasal prefix jika jawaban adalah list murni

---

## 2. Distribusi Skor Saat Ini

```
Mean: 0.6672 | Median: 0.6720 | Stdev: 0.2154
< 0.50 (kritis):    6 items  (GT-007, GT-021, GT-008, GT-032, GT-033, GT-028)
0.50 – 0.70 (sedang): 17 items
>= 0.70 (baik):    17 items
>= 0.90 (sangat baik): 6 items
```

Target setelah perbaikan: **>= 0.75** (kenaikan +0.08)

---

## 3. Strategi yang Dipilih

### Strategi 1: Tighter System + User Prompt Constraints

**Apa yang berubah di `prompts.py`:**

1. **Hapus "Berdasarkan dokumen yang diberikan" sebagai pembuka** — ini memakan token dan memberi sinyal ke model untuk mendeklarasikan keterbatasan lebih dulu.

2. **Ganti frasa "Jika jawaban inti sudah cukup, berhenti"** dengan constraint yang lebih operasional:
   - `"STOP: Setelah menjawab inti, JANGAN tulis kalimat berikutnya."`  
   - `"Kalimat pertama = seluruh jawaban untuk tipe actor/definition/value/purpose."`

3. **Tambah rule anti-disclaimer**: "DILARANG memulai dengan 'Berdasarkan dokumen... tidak ditemukan' jika frasa kunci tersedia di konteks."

4. **Tambah hard constraint per tipe:**
   - `actor/value_or_time`: max 1 kalimat, STOP
   - `purpose`: 1 kalimat STOP, tidak boleh ada "selain itu"  
   - `list`: bullet saja, DILARANG sub-header bernomor ("1. Jenis...", "2. Pelaksana...")
   - `direct_fact`: 1 kalimat, tambahkan detail HANYA jika ada ambiguitas

5. **Ganti contoh format jawaban** di `build_rag_prompt()` dengan few-shot examples per tipe yang menunjukkan "benar" vs "salah":

```
CONTOH ACTOR (BENAR):
Q: Siapa yang bertanggung jawab atas Audit Keamanan Internal di BSSN?
A: Tim Auditor Keamanan SPBE BSSN [1].

CONTOH ACTOR (SALAH — JANGAN LAKUKAN):
A: Berdasarkan dokumen, Tim Auditor Keamanan SPBE BSSN [1] bertanggung jawab. Pelaksanaan mencakup pengujian kontrol keamanan infrastruktur PDN, SPLS, dan Jaringan Intra [3][4].
```

### Strategi 2: Post-Processing Rule-Based Trimmer

**Komponen baru:** `answer_trimmer.py` di `backend/app/core/rag/`

**Logic:**
```python
def trim_answer_by_type(answer: str, question_type: str) -> str:
    """
    Trim verbose answer to core response based on question type.
    Applied AFTER model generation, BEFORE sending to user.
    """
```

**Rules:**
- `actor` / `value_or_time` / `purpose` / `definition`: Ambil **kalimat pertama** yang mengandung sitasi `[n]` dan tidak dimulai dengan disclaimer
- `list`: Ambil semua bullet item, buang paragraf penjelasan setelah bullet terakhir
- `direct_fact`: Ambil kalimat pertama + kalimat kedua jika ada sitasi berbeda
- `general` / `explanation`: Tidak di-trim (boleh lebih panjang)

**Disclaimer detection:**
```python
DISCLAIMER_PREFIXES = [
    "berdasarkan dokumen yang diberikan, informasi mengenai",
    "definisi spesifik mengenai",
    "tidak ditemukan dalam konteks",
    "tidak dapat diidentifikasi",
]
```
Jika terdeteksi disclaimer di kalimat pertama → cari kalimat berikutnya yang mengandung jawaban inti dan sitasi → jadikan pembuka.

### Strategi 3: Few-Shot Examples di Prompt

**Lokasi:** Tambah ke `build_rag_prompt()` sebagai blok `CONTOH FORMAT JAWABAN` yang type-aware.

**Untuk tipe `list`:**
```
CONTOH LIST (BENAR):
Q: Apa sanksi administratif...?
A:
- Teguran tertulis [2].
- Denda administratif [2].
- Penghentian sementara [2].
- Pemutusan Akses [2].
- Dikeluarkan dari daftar [2].

CONTOH LIST (SALAH):
A: Berikut sanksi administratif:
1. **Jenis Sanksi:** teguran tertulis...
   - Detail: ...
2. **Pelaksana:** ...
```

---

## 4. Rencana Implementasi

### Task 1: Perbaikan `prompts.py`
- [ ] Update `build_answer_style_instructions()` dengan hard-stop rules per tipe
- [ ] Update shared_rules: hapus "jika cukup berhenti" → ganti dengan "STOP setelah inti"
- [ ] Tambah anti-disclaimer rules ke `SYSTEM_PROMPT_SPBE` 
- [ ] Update `build_rag_prompt()`: ganti contoh format jawaban dengan few-shot per tipe

### Task 2: Buat `answer_trimmer.py`
- [ ] Implementasi `trim_answer_by_type(answer, question_type) -> str`
- [ ] Implementasi `_detect_disclaimer_start(text) -> bool`
- [ ] Implementasi `_extract_first_core_sentence(text) -> str`
- [ ] Implementasi `_trim_list_type(text) -> str`

### Task 3: Integrasi Trimmer ke Pipeline
- [ ] Panggil trimmer di `langchain_engine.py` setelah `_generate_answer()`
- [ ] Pastikan trimmer tidak merusak faithfulness (harus trim, bukan regenerate)
- [ ] Buat unit test trimmer dengan kasus GT-007, GT-033, GT-037

### Task 4: Fix Retrieval GT-021
- [ ] Tambah query expansion khusus untuk "Aplikasi SPBE Prioritas"
- [ ] Cek apakah chunk Perpres 82/2023 Pasal 1 (definisi Aplikasi SPBE Prioritas) ada di Qdrant
- [ ] Jika ada, tambahkan keyword anchor di `expand_query()`

### Task 5: Verifikasi
- [ ] Jalankan ulang collect pada 12 ID dengan AR terendah (tanpa full 40)
- [ ] Jalankan RAGAS pada subset 12 ID tersebut
- [ ] Bandingkan AR sebelum vs sesudah

---

## 5. Risiko

| Risiko | Mitigasi |
|---|---|
| Trimmer terlalu agresif → jawaban terpotong ditengah | Unit test untuk kalimat dengan nested citation |
| Few-shot examples membingungkan model → hallucination | Few-shot hanya contoh format, bukan contoh konten |
| Prompt lebih panjang → latency naik | Ukur token count sebelum-sesudah |
| Faithfulness turun karena trimmer hapus kalimat grounded | Hitung faithfulness pada kalimat yang dipertahankan saja |

---

## 6. Target

| Metrik | Sekarang | Target |
|---|:---:|:---:|
| Answer Relevancy | 0.6672 | >= 0.75 |
| Faithfulness | 0.8116 | >= 0.80 (dijaga) |
| Context Recall | 0.9500 | >= 0.95 (dijaga) |
| Items < 0.5 AR | 6 | <= 2 |
