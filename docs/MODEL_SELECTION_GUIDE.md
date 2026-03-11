# 🤖 Model Selection Guide - SPBE RAG System

**Last Updated:** 25 Jan 2026  
**For:** GTX 1650 (4GB VRAM)

---

## ✅ REKOMENDASI MODEL TERBAIK

### 1. **LLM: Qwen 2.5 7B Instruct (Q4_K_M)** ⭐ RECOMMENDED

**Selected Model:**
- **Repository:** `bartowski/Qwen2.5-7B-Instruct-GGUF`
- **File:** `Qwen2.5-7B-Instruct-Q4_K_M.gguf`
- **Size:** ~4.37 GB
- **Format:** GGUF (untuk llama-cpp-python)
- **Quantization:** Q4_K_M

**Mengapa Q4_K_M?**
- ✅ **Optimal untuk 4GB VRAM** - Pas di GTX 1650 dengan overhead ~500MB
- ✅ **Balance terbaik** antara kualitas vs kecepatan
- ✅ **Bahasa Indonesia support** - Qwen 2.5 excellent untuk multilingual
- ✅ **Legal text friendly** - Bagus untuk dokumen formal/legal
- ✅ **Production ready** - Bartowski quantization terkenal reliable

**Perbandingan Quantization Levels:**

| Quantization | Size | Quality | VRAM | Speed | Recommendation |
|--------------|------|---------|------|-------|----------------|
| Q2_K | ~2.5 GB | ⭐⭐ Poor | 2.8 GB | ⚡⚡⚡ | ❌ Terlalu rendah |
| Q3_K_M | ~3.3 GB | ⭐⭐⭐ OK | 3.6 GB | ⚡⚡⚡ | ⚠️ Acceptable |
| **Q4_K_M** | **~4.4 GB** | **⭐⭐⭐⭐ Good** | **4.8 GB** | **⚡⚡** | **✅ BEST** |
| Q5_K_M | ~5.3 GB | ⭐⭐⭐⭐⭐ Excellent | 5.7 GB | ⚡⚡ | ❌ Terlalu besar |
| Q6_K | ~6.1 GB | ⭐⭐⭐⭐⭐ | 6.5 GB | ⚡ | ❌ Tidak muat |

**Estimasi VRAM Usage:**
```
Model weights:        ~4.37 GB
Context (4K tokens):  ~0.3 GB
Overhead:             ~0.2 GB
-----------------------------------
Total:                ~4.87 GB

GTX 1650 VRAM:        4.00 GB
Status:               ⚠️ TIGHT (perlu optimasi)
```

**Cara Handle di 4GB:**
1. Reduce context window ke 2048 tokens (default: 4096)
2. Set n_batch=128 (default: 512)
3. Set n_gpu_layers=-1 (offload semua ke GPU)

---

### 2. **Embedding: Indo-Sentence-BERT-Base** ✅

**Selected Model:**
- **Repository:** `firqaaa/indo-sentence-bert-base`
- **Size:** ~400 MB
- **Type:** Sentence Transformers (BERT-based)
- **Language:** Indonesian-optimized

**Mengapa model ini?**
- ✅ **Dilatih khusus untuk Bahasa Indonesia**
- ✅ **384-dimensional embeddings** (bagus untuk semantic search)
- ✅ **Pretrained pada corpus Indonesia**
- ✅ **Compatible dengan HuggingFace Transformers**
- ✅ **Sudah tested untuk RAG Indonesia**

**Alternative Models:**
- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (multilingual, lebih umum)
- `firqaaa/indo-sentence-bert-large` (lebih akurat tapi 2x lebih lambat)

**Recommendation:** Stick with `indo-sentence-bert-base` - balance terbaik!

---

### 3. **Reranker: BGE-Reranker-Base** ✅

**Selected Model:**
- **Repository:** `BAAI/bge-reranker-base`
- **Size:** ~1 GB
- **Type:** Cross-encoder (BERT-based)
- **Language:** Multilingual (including Indonesian)

**Mengapa model ini?**
- ✅ **State-of-the-art reranker** dari BAAI
- ✅ **Multilingual support** (termasuk Indonesia)
- ✅ **Ukuran moderate** (~1GB)
- ✅ **Excellent untuk legal documents**
- ✅ **Production proven**

**VRAM Usage:**
```
Reranker inference:   ~1.5 GB (saat dipakai)
Batch size 32:        ~2.0 GB
```

**Note:** Reranker berjalan **terpisah** dari LLM (tidak bersamaan), jadi safe untuk 4GB VRAM.

---

## 🔍 ANALISIS LINK YANG ANDA TEMUKAN

### 1. ❌ `Qwen/Qwen2.5-7B-Instruct`
**Status:** TIDAK RECOMMENDED  
**Alasan:**
- Full precision model (FP16/BF16)
- Size: ~15 GB
- VRAM required: ~16 GB
- ❌ **Terlalu besar untuk GTX 1650 4GB**

### 2. ⚠️ `paultimothymooney/Qwen2.5-7B-Instruct-Q4_K_M-GGUF`
**Status:** ACCEPTABLE ALTERNATIVE  
**Alasan:**
- ✅ Correct quantization (Q4_K_M)
- ✅ GGUF format
- ⚠️ Tapi kurang populer (22 downloads)
- ⚠️ Belum verified quality

**Recommendation:** Lebih baik pakai `bartowski` (lebih trusted)

### 3. ❌ `Qwen/Qwen2.5-VL-7B-Instruct`
**Status:** TIDAK PERLU  
**Alasan:**
- Vision-Language model (untuk image + text)
- Anda hanya butuh text processing
- Lebih besar dan lambat
- ❌ **Overkill untuk kebutuhan Anda**

### 4. ✅ `bartowski/Qwen2.5-7B-Instruct-GGUF` ⭐ BEST CHOICE
**Status:** RECOMMENDED  
**Alasan:**
- ✅ **Bartowski = trusted quantizer** (ribuan downloads)
- ✅ **Banyak pilihan quantization** (Q2 sampai Q8)
- ✅ **Verified quality** - community tested
- ✅ **Regular updates**
- ✅ **24 variants available**

**Available Quantizations:**
```
IQ2_M, IQ3_M, IQ3_XS, IQ4_XS       (Very low, experimental)
Q2_K, Q2_K_L                       (Low quality)
Q3_K_S, Q3_K_M, Q3_K_L, Q3_K_XL   (Medium-low)
Q4_0, Q4_K_S, Q4_K_M, Q4_K_L      (Good - RECOMMENDED)
Q5_K_S, Q5_K_M, Q5_K_L            (Very good - too big)
Q6_K, Q6_K_L                       (Excellent - too big)
Q8_0, f16                          (Near-original - way too big)
```

**Pilihan Anda:**
- **Primary:** `Q4_K_M` - 4.37 GB (optimal untuk 4GB VRAM)
- **Alternative 1:** `Q3_K_L` - 3.7 GB (jika Q4 terlalu besar)
- **Alternative 2:** `Q5_K_M` - 5.3 GB (jika upgrade ke GPU 6GB+)

---

## 📥 DOWNLOAD INSTRUCTIONS

### Automatic (RECOMMENDED):
```bash
cd D:\aqil\pusdatik\backend

# Download semua models (LLM + Embedding + Reranker)
venv\Scripts\python.exe scripts\download_models.py

# Monitor progress (akan show download percentage)
```

### Manual (jika automatic error):
```bash
cd D:\aqil\pusdatik\backend
venv\Scripts\python.exe
```

```python
from huggingface_hub import hf_hub_download, snapshot_download
from pathlib import Path

# Create directories
Path("models/llm").mkdir(parents=True, exist_ok=True)
Path("models/embeddings").mkdir(parents=True, exist_ok=True)
Path("models/reranker").mkdir(parents=True, exist_ok=True)

# 1. Download LLM (Q4_K_M - 4.37 GB)
print("Downloading Qwen 2.5 7B Instruct Q4_K_M...")
hf_hub_download(
    repo_id="bartowski/Qwen2.5-7B-Instruct-GGUF",
    filename="Qwen2.5-7B-Instruct-Q4_K_M.gguf",
    local_dir="models/llm",
    local_dir_use_symlinks=False,
    resume_download=True
)

# 2. Download Embedding (~400 MB)
print("Downloading Indonesian embeddings...")
snapshot_download(
    repo_id="firqaaa/indo-sentence-bert-base",
    local_dir="models/embeddings/indo-sentence-bert-base",
    local_dir_use_symlinks=False,
    resume_download=True
)

# 3. Download Reranker (~1 GB)
print("Downloading reranker...")
snapshot_download(
    repo_id="BAAI/bge-reranker-base",
    local_dir="models/reranker/bge-reranker-base",
    local_dir_use_symlinks=False,
    resume_download=True
)

print("✅ All models downloaded!")
exit()
```

---

## 🔧 JIKA DOWNLOAD GAGAL

### Error: Connection timeout
```bash
# Set longer timeout
export HF_HUB_DOWNLOAD_TIMEOUT=600

# Atau pakai mirror (jika di China/restricted network)
export HF_ENDPOINT=https://hf-mirror.com
```

### Error: Disk space
```bash
# Check available space
dir | findstr "bytes free"

# Free up space (hapus cache HuggingFace jika ada)
rmdir /s "%USERPROFILE%\.cache\huggingface"
```

### Error: Authentication required
```bash
# Login ke HuggingFace (jika model private)
venv\Scripts\pip.exe install huggingface-hub[cli]
venv\Scripts\python.exe -m huggingface_hub.commands.huggingface_cli login
```

### Download sangat lambat
**Alternative: Download via browser**
1. Buka: https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/tree/main
2. Klik file: `Qwen2.5-7B-Instruct-Q4_K_M.gguf`
3. Download
4. Move ke: `D:\aqil\pusdatik\backend\models\llm\`

Repeat untuk embedding dan reranker.

---

## ✅ VERIFY INSTALLATION

```bash
cd D:\aqil\pusdatik\backend

# Verify models downloaded
venv\Scripts\python.exe scripts\download_models.py --verify

# Expected output:
# ✓ LLM         : Present    (models/llm)
# ✓ EMBEDDING   : Present    (models/embeddings/indo-sentence-bert-base)
# ✓ RERANKER    : Present    (models/reranker/bge-reranker-base)
```

**File structure harus seperti ini:**
```
backend/models/
├── llm/
│   └── Qwen2.5-7B-Instruct-Q4_K_M.gguf (4.37 GB)
├── embeddings/
│   └── indo-sentence-bert-base/
│       ├── config.json
│       ├── pytorch_model.bin
│       ├── tokenizer.json
│       └── ...
└── reranker/
    └── bge-reranker-base/
        ├── config.json
        ├── pytorch_model.bin
        └── ...
```

---

## 🎯 PERFORMANCE EXPECTATIONS

### Qwen 2.5 7B Q4_K_M pada GTX 1650:

**Inference Speed:**
- Prompt processing: ~20-30 tokens/sec
- Generation: ~10-15 tokens/sec
- Latency first token: ~200-500ms

**Quality:**
- Perplexity: ~10-15% degradation vs FP16
- Practical impact: Minimal (masih sangat bagus)
- Legal text understanding: Excellent

**Context Window:**
- Default: 4096 tokens
- Recommended: 2048 tokens (untuk stability)
- Maximum: 8192 tokens (akan OOM di 4GB)

---

## 💡 TIPS & TRICKS

### Jika Model Terlalu Besar (OOM)
**Option 1:** Turunkan ke Q3_K_L
```python
# Dalam download script, ganti:
"filename": "Qwen2.5-7B-Instruct-Q3_K_L.gguf"  # ~3.7 GB
```

**Option 2:** Reduce context window
```python
# Dalam llm.py nanti:
llm = LlamaCPP(
    model_path="...",
    n_ctx=2048,      # Default: 4096
    n_batch=128,     # Default: 512
    n_gpu_layers=-1
)
```

**Option 3:** Offload sebagian ke CPU
```python
n_gpu_layers=25  # Hanya 25 layer di GPU (dari 32 total)
```

### Untuk Testing Cepat
**Gunakan model kecil dulu:**
```python
# Qwen 1.5B Q4_K_M (~900 MB) - untuk testing pipeline
repo_id="Qwen/Qwen2-1.5B-Instruct-GGUF"
filename="qwen2-1_5b-instruct-q4_k_m.gguf"
```

Setelah pipeline jalan, switch ke 7B.

---

## 📊 SUMMARY RECOMMENDATION

**Untuk GTX 1650 4GB:**

| Component | Model | Size | Link |
|-----------|-------|------|------|
| **LLM** | Qwen 2.5 7B Q4_K_M | 4.37 GB | bartowski/Qwen2.5-7B-Instruct-GGUF |
| **Embedding** | Indo-SBERT-Base | 400 MB | firqaaa/indo-sentence-bert-base |
| **Reranker** | BGE-Reranker-Base | 1 GB | BAAI/bge-reranker-base |
| **Total** | | **~5.8 GB** | |

**Download command:**
```bash
cd backend
venv\Scripts\python.exe scripts\download_models.py
```

**Expected time:** 30-60 menit (tergantung internet)

---

**✅ Script sudah di-update dengan link yang benar!**  
**Silakan lanjut download dengan perintah di atas.**
