# File: `backend/app/core/rag/langchain_engine.py` — Sesi 2

## 🎯 Tujuan Perubahan (Sesi Ini)
Memperbaiki **2 bug tambahan** yang ditemukan setelah sesi pertama:
1. Model `qwen3.5:4b` menghasilkan 0 token saat streaming
2. Format section sources tampil duplikat: `"Pasal Pasal 9"`, `"Ayat (Ayat (1))"`

---

## BUG 1 — qwen3.5:4b Menghasilkan 0 Token

### ❌ Sebelum

```python
def _get_llm(self, model_name: str) -> ChatOllama:
    if model_name not in self.llms:
        self.llms[model_name] = ChatOllama(
            base_url="http://localhost:11434",
            model=model_name,
            temperature=0.1,
            num_predict=2048,
            timeout=300,   # ← 5 menit, terlalu pendek untuk load model besar
        )
```

**Masalah:**
- `qwen3.5` dan `qwen3` adalah model "thinking" — secara default menggunakan
  *reasoning mode* di mana model berpikir dulu sebelum menjawab
- Selama fase berpikir, token dikirim via field berbeda (`reasoning_content`), 
  bukan `chunk.content` yang dibaca oleh kode
- Hasilnya: `chunk.content` selalu kosong → `Generated 0 tokens`
- Log bukti: streaming berlangsung **5 menit 48 detik** lalu selesai tanpa output

### ✅ Sesudah

```python
def _get_llm(self, model_name: str) -> ChatOllama:
    if model_name not in self.llms:
        # Deteksi model thinking (qwen3.x, qwen3.5.x)
        is_thinking_model = any(model_name.startswith(p) for p in ["qwen3", "qwen3.5"])
        # langchain-ollama 1.0.1: parameter 'reasoning' → dikirim sebagai {"think": false} ke Ollama
        extra_kwargs = {"reasoning": False} if is_thinking_model else {}
        self.llms[model_name] = ChatOllama(
            base_url="http://localhost:11434",
            model=model_name,
            temperature=0.1,
            num_predict=2048,
            timeout=600,   # ← 10 menit, cukup untuk model besar seperti qwen3.5:9b
            **extra_kwargs,
        )
        if is_thinking_model:
            logger.info(f"[LLM] Thinking mode DISABLED for {model_name}")
```

**Kenapa `reasoning` bukan `think`?**

Dari source code `langchain-ollama==1.0.1`:
```python
# Di dalam ChatOllama._create_chat_result():
"think": kwargs.pop("reasoning", self.reasoning),
```
Field yang diekspos ke user adalah `reasoning`, yang kemudian secara internal
dikirim ke Ollama API sebagai `think`. Nama berbeda antara LangChain dan Ollama.

---

## BUG 2 — Format Section Duplikat di Sources Panel

### ❌ Sebelum

```python
# Di retrieve_context() dan _format_context()
if meta.get("pasal"): section_parts.append(f"Pasal {meta['pasal']}")
if meta.get("ayat"):  section_parts.append(f"Ayat ({meta['ayat']})")
```

**Masalah:**
Field `pasal` di Qdrant payload **sudah berisi** teks `"Pasal 9"` (sudah ada prefix).
Kode menambahkan prefix `"Pasal "` lagi → hasil: `"Pasal Pasal 9"`.
Sama untuk `ayat`: sudah berisi `"Ayat (1)"` → jadi `"Ayat (Ayat (1))"`.

Terlihat di UI Sources:
```
BAB II > Ketiga -  > Pasal Pasal 9 > Ayat (Ayat (1))
```

### ✅ Sesudah

```python
# Cek apakah nilai SUDAH mengandung prefix sebelum menambahkan
pasal_val = str(meta["pasal"]) if meta.get("pasal") else ""
if pasal_val:
    section_parts.append(
        pasal_val if pasal_val.lower().startswith("pasal") else f"Pasal {pasal_val}"
    )
ayat_val = str(meta["ayat"]) if meta.get("ayat") else ""
if ayat_val:
    section_parts.append(
        ayat_val if ayat_val.lower().startswith("ayat") else f"Ayat ({ayat_val})"
    )
```

**Logic:** 
- Jika nilai sudah dimulai dengan `"pasal"` (case-insensitive) → pakai apa adanya
- Jika belum ada prefix → tambahkan prefix
- Berlaku untuk kedua tempat: `retrieve_context()` (sources UI) dan `_format_context()` (context ke LLM)

---

## 📊 Perbandingan Hasil

| Aspek | Sebelum | Sesudah |
|-------|---------|---------|
| Model qwen3.5:4b | 0 token, jawaban kosong | Streaming normal, jawaban muncul |
| Waktu respons qwen3.5:4b | 5m48s (timeout) | ~88 detik (normal) |
| Format section | `"Pasal Pasal 9 > Ayat (Ayat (1))"` | `"Pasal 9 > Ayat (1)"` |
| Timeout | 300 detik (5 menit) | 600 detik (10 menit) |

---

## 💡 Temuan Penting: cara cek dukungan parameter ChatOllama

```python
# Cara verifikasi parameter yang didukung:
from langchain_ollama import ChatOllama
import inspect
src = inspect.getsource(ChatOllama)
lines = [l for l in src.split('\n') if 'think' in l.lower() or 'reasoning' in l.lower()]
```

Output akan menampilkan baris yang relevan beserta penjelasan parameter `reasoning`.

---

## Daftar Baris yang Diubah

| Method | Baris (approx) | Perubahan |
|--------|----------------|-----------|
| `_get_llm()` | 95-115 | Tambah deteksi thinking model + `reasoning=False` + timeout 600s |
| `retrieve_context()` | 162-175 | Fix format pasal/ayat duplikat di sources UI |
| `_format_context()` | 214-225 | Fix format pasal/ayat duplikat di context LLM |
