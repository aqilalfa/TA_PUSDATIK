# File 6: `backend/app/core/rag/langchain_engine.py`

## 🎯 Tujuan Perubahan
**Ini adalah root cause dari jawaban kosong.** Metadata field yang dipakai untuk membaca info dokumen dari Qdrant salah — tidak sesuai dengan nama field yang sebenarnya tersimpan.

---

## 🔍 Akar Masalah

Ketika dokumen diindeks ke Qdrant (lewat `sync_vectors.py`), payload yang tersimpan menggunakan field ini:

```python
# Yang TERSIMPAN di Qdrant (dari sync_vectors.py)
payload = {
    "text": "...",              # isi teks chunk
    "document_title": "...",    # judul dokumen
    "filename": "...",          # nama file 
    "doc_type": "...",          # tipe dokumen
    "context_header": "...",    # header konteks
    "bab": "...",               # BAB dokumen
    "bagian": "...",            # bagian
    "pasal": "...",             # nomor pasal
    "ayat": "...",              # nomor ayat
}
```

Tapi `langchain_engine.py` membacanya dengan field yang **tidak ada**:

```python
# Yang DICARI (SALAH!) di langchain_engine.py
meta.get("judul_dokumen")    # ← tidak ada! seharusnya "document_title"
meta.get("hierarchy_path")   # ← tidak ada! seharusnya "context_header"
```

---

## ❌ Sebelum (Problem)

### Di `retrieve_context()` → sources untuk frontend:
```python
sources.append({
    "id": i,
    "document": meta.get("judul_dokumen", "Dokumen Tidak Diketahui"),  # SALAH KEY
    "section": meta.get("hierarchy_path", ""),                          # SALAH KEY
    "score": 1.0,
})
```
**Hasil:** Semua dokumen tampil sebagai "Dokumen Tidak Diketahui" → LLM bingung → jawaban kosong/asal.

### Di `_format_context()` → context string untuk LLM:
```python
judul = (doc.metadata or {}).get("judul_dokumen", "Dokumen")  # SALAH KEY
hierarchy = meta.get("hierarchy_path", "")                     # SALAH KEY
```
**Hasil:** Context yang dikirim ke LLM berisi "Dokumen - " tanpa nama nyata → LLM tidak bisa merespons dengan benar.

---

## ✅ Sesudah (Fix)

### Fix 1: `retrieve_context()` — sources

```python
# Gunakan chain of fallback agar tidak pernah kosong
doc_title = (
    meta.get("document_title")    # field utama dari Qdrant
    or meta.get("judul_dokumen")  # fallback legacy
    or meta.get("tentang")        # fallback lain
    or meta.get("filename", "").replace(".pdf", "").replace("_", " ")  # dari nama file
    or "Dokumen"                  # last resort
)

# Build lokasi dari field yang tersedia
section_parts = []
if meta.get("bab"):    section_parts.append(str(meta["bab"]))
if meta.get("bagian"): section_parts.append(str(meta["bagian"]))
if meta.get("pasal"):  section_parts.append(f"Pasal {meta['pasal']}")
if meta.get("ayat"):   section_parts.append(f"Ayat ({meta['ayat']})")
section = " > ".join(section_parts) or meta.get("context_header", "")
```

### Fix 2: `_format_context()` — context untuk LLM

```python
# Header daftar sumber sekarang menampilkan nama asli dokumen
for i, doc in enumerate(docs, 1):
    meta = doc.metadata or {}
    judul = (
        meta.get("document_title") or meta.get("judul_dokumen")
        or meta.get("tentang") or "Dokumen"
    )
    # ... format dengan pasal/bab/ayat yang benar
```

---

## 📊 Perbandingan Hasil

| Aspek | Sebelum | Sesudah |
|-------|---------|---------|
| Nama dokumen di Sources | "Dokumen Tidak Diketahui" | "Pedoman Nomor 3 Tahun 2024" |
| Lokasi dalam dokumen | kosong | "BAB III > B. Tata Cara..." |
| Context ke LLM | "Dokumen - \nIsi: ..." | "Pedoman Nomor 3 Tahun 2024 — BAB III\nIsi: ..." |
| Kualitas jawaban | Kosong / tidak relevan | Substantif dengan sitasi [1], [2] dst |

---

## 💡 Pelajaran Penting
Selalu validasi bahwa **field name saat INDEX == field name saat READ**. Ini sering terjadi ketika kode indexing dan kode retrieval ditulis oleh orang/waktu berbeda.

Untuk ke depan: buat konstanta shared untuk field names:
```python
# Contoh: app/core/rag/constants.py
FIELD_DOC_TITLE = "document_title"
FIELD_CONTEXT_HEADER = "context_header"
```
