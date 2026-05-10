# 🔍 Analisis Menyeluruh — Semua Masalah Saat Ini

> Dibuat: 2026-04-09
> Berdasarkan: review kode lengkap + log server + inspect Qdrant payload

---

## RINGKASAN EKSEKUTIF

Masalah **jawaban kosong** disebabkan LEBIH DARI SATU hal.
Timeout model bukan satu-satunya masalah. Ada **4 masalah aktif** dengan tingkat keparahan berbeda.

---

## MASALAH 1 — KRITIS ⛔
### Model `qwen3.5:4b` Timeout → 0 Tokens

**Lokasi:** `langchain_engine.py` baris 99–105

**Apa yang terjadi:**
```
17:32:04 → Streaming dimulai dengan qwen3.5:4b
17:37:52 → Done. Generated 0 tokens.
← 5 menit 48 detik, tidak ada output
```

**Kenapa terjadi:**
`qwen3.5` adalah model baru yang menggunakan format "thinking" (seperti reasoning mode). 
Saat `ChatOllama.astream()` memanggil model ini, Ollama mungkin mengembalikan event 
streaming dalam format baru (`reasoning_content` bukan `content`) yang tidak dikenali 
LangChain. Hasilnya `chunk.content` selalu `None`/kosong → 0 tokens.

Bukti: timeout 300 detik persis → `[WinError 10048]` setelahnya.

**Kode bermasalah:**
```python
# langchain_engine.py baris 277-280
async for chunk in llm.astream(messages):
    if chunk.content:          # ← untuk qwen3.5, chunk.content selalu ""
        token_count += 1
        yield chunk.content    # ← tidak pernah sampai sini
```

**Fix yang diperlukan:**
```python
async for chunk in llm.astream(messages):
    # Qwen3 thinking models pakai additional_kwargs, bukan .content langsung
    text = chunk.content or ""
    if not text and hasattr(chunk, 'additional_kwargs'):
        text = chunk.additional_kwargs.get('reasoning_content', '')
    if text:
        token_count += 1
        yield text
```
Atau lebih mudah: tambah `think=False` di ChatOllama config untuk disable thinking mode.

---

## MASALAH 2 — SEDANG ⚠️
### Format Section Duplikat di Sources Panel

**Lokasi:** `langchain_engine.py` baris 163–168

**Apa yang terjadi (tampil di UI):**
```
BAB II > Ketiga -  > Pasal Pasal 9 > Ayat (Ayat (1))
                     ^^^^^^^^^^^^     ^^^^^^^^^^^^^^^
                     duplikat!        duplikat!
```

**Kenapa terjadi:**
Field `pasal` di Qdrant payload SUDAH berisi teks `"Pasal 9"`, tapi kode menambah 
prefix `"Pasal "` lagi → jadi `"Pasal Pasal 9"`.
Field `ayat` SUDAH berisi `"Ayat (1)"`, tapi kode membungkus dengan `f"Ayat ({val})"` 
→ jadi `"Ayat (Ayat (1))"`.

**Kode bermasalah:**
```python
# baris 166-167
if meta.get("pasal"): section_parts.append(f"Pasal {meta['pasal']}")  # ← tambah "Pasal"
if meta.get("ayat"): section_parts.append(f"Ayat ({meta['ayat']})")   # ← tambah "Ayat ()"
```

**Fix:**
```python
# Cek apakah sudah ada prefix sebelum menambahkan
pasal_val = str(meta.get("pasal", ""))
ayat_val = str(meta.get("ayat", ""))
if pasal_val:
    section_parts.append(pasal_val if pasal_val.lower().startswith("pasal") else f"Pasal {pasal_val}")
if ayat_val:
    section_parts.append(ayat_val if ayat_val.lower().startswith("ayat") else f"Ayat ({ayat_val})")
```

---

## MASALAH 3 — SEDANG ⚠️
### Default Model Tidak Persisten (Hilang Saat Restart)

**Lokasi:** `app/api/routes/models.py` baris 10–11

**Apa yang terjadi:**
```python
# In-memory storage — HILANG saat server restart!
_default_model = "qwen2.5:3b"
```

**Kenapa bermasalah:**
- Default model disimpan di **variabel Python biasa di memori** (in-memory)
- Setiap kali server restart → kembali ke `qwen2.5:3b`
- Tapi saat user mengganti model di UI (ke `qwen3.5:4b`) → server MATI/RESTART → 
  model kembali ke `qwen2.5:3b` tapi **UI frontend tidak tahu** (cache state)
- Ini bisa menyebabkan inkonsistensi antara model yang digunakan dan yang ditampilkan user

**Fix yang diperlukan:**
Simpan default model ke database atau file config, bukan memory:
```python
# Opsi simpel: simpan ke file JSON kecil
import json, pathlib
_MODEL_FILE = pathlib.Path("data/default_model.json")

def get_default_model() -> str:
    if _MODEL_FILE.exists():
        return json.loads(_MODEL_FILE.read_text()).get("model", "qwen2.5:3b")
    return "qwen2.5:3b"

def set_default_model(model: str):
    _MODEL_FILE.write_text(json.dumps({"model": model}))
```

---

## MASALAH 4 — RINGAN ℹ️
### Qdrant Client Version Warning Setiap Health Check

**Lokasi:** `app/api/routes/health.py` baris 33

**Pesan warning:**
```
UserWarning: Qdrant client version 1.16.2 is incompatible with server version 1.12.0.
Major versions should match and minor version difference must not exceed 1.
Set check_compatibility=False to skip version check.
```

**Apa yang terjadi:**
Health check membuat `QdrantClient` BARU setiap request, DAN tidak menonaktifkan 
compatibility check. Ini muncul sebagai UserWarning di setiap `/api/health` call.

**Kode bermasalah:**
```python
# health.py baris 33 — client baru tanpa check_compatibility=False
client = QdrantClient(url=settings.QDRANT_URL)  # ← warning setiap kali!
```

Bandingkan dengan langchain_engine.py yang sudah benar:
```python
self.client = QdrantClient(url=self.qdrant_url, check_compatibility=False)  # ← benar
```

**Fix:** Tambah `check_compatibility=False` di health.py.

---

## RINGKASAN PRIORITAS PERBAIKAN

| # | Masalah | Dampak | Fix Complexity |
|---|---------|--------|----------------|
| 1 | qwen3.5 timeout → 0 tokens | **Chat kosong** | ⭐ Mudah (2 baris) |
| 2 | Format section duplikat | Tampilan kotor di UI | ⭐ Mudah (5 baris) |
| 3 | Default model tidak persisten | Inkonsistensi UX | ⭐⭐ Sedang (1 file baru) |
| 4 | Qdrant version warning | Log spam | ⭐ Mudah (1 karakter) |

---

## CATATAN PENTING

### Yang SUDAH BERFUNGSI DENGAN BAIK ✅
- Sources/referensi dokumen sudah tampil benar (hasil fix metadata key sebelumnya)
- Streaming pipeline sudah benar (event: retrieval, token, complete)
- Database ORM sudah konsisten (hasil refactoring Phase 1)
- History chat tersimpan dan diload dengan benar
- Session management berjalan normal

### Masalah BUKAN di kode program
- `qwen2.5:3b` → jawaban bagus, cepat ✅
- `qwen3.5:4b` → jawaban kosong karena streaming format incompatibility
