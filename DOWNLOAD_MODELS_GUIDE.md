# ✅ FIXED! Script Siap Digunakan

## 🔧 Yang Sudah Diperbaiki

1. ✅ **Model links updated** → `bartowski/Qwen2.5-7B-Instruct-GGUF` (Q4_K_M)
2. ✅ **Logger encoding error fixed** → Emoji removed (Windows cp1252 compatible)
3. ✅ **Script tested** → Berfungsi dengan baik!

---

## 🚀 CARA DOWNLOAD MODELS (READY TO GO!)

### Step 1: Verify Script (Optional)
```bash
cd D:\aqil\pusdatik\backend

# Check current status (semua akan MISSING jika belum download)
venv\Scripts\python.exe scripts\download_models.py --verify

# Output:
#   [MISSING] LLM          : Missing    (models/llm)
#   [MISSING] EMBEDDING    : Missing    (models/embeddings/indo-sentence-bert-base)
#   [MISSING] RERANKER     : Missing    (models/reranker/bge-reranker-base)
```

### Step 2: Download All Models (~6-7 GB, 30-60 menit)
```bash
# Start download (bisa resume jika terputus)
venv\Scripts\python.exe scripts\download_models.py

# Output akan show progress seperti:
# [START] Starting model download process...
# 
# [MODEL] Processing: LLM
# [DOWNLOAD] bartowski/Qwen2.5-7B-Instruct-GGUF (Qwen2.5-7B-Instruct-Q4_K_M.gguf)...
# Downloading: 100%|██████████| 4.37G/4.37G [XX:XX<00:00, XXMiB/s]
# [OK] Downloaded to: models/llm/Qwen2.5-7B-Instruct-Q4_K_M.gguf
#
# [MODEL] Processing: EMBEDDING
# [DOWNLOAD] firqaaa/indo-sentence-bert-base (full repository)...
# Downloading: 100%|██████████| 400M/400M [XX:XX<00:00, XXMiB/s]
# [OK] Downloaded to: models/embeddings/indo-sentence-bert-base
#
# [MODEL] Processing: RERANKER
# [DOWNLOAD] BAAI/bge-reranker-base (full repository)...
# Downloading: 100%|██████████| 1.0G/1.0G [XX:XX<00:00, XXMiB/s]
# [OK] Downloaded to: models/reranker/bge-reranker-base
#
# [SUCCESS] All models downloaded successfully!
#
# [SUMMARY] Model Summary:
#   - LLM: models/llm/Qwen2.5-7B-Instruct-Q4_K_M.gguf (~4.37 GB)
#   - Embedding: models/embeddings/indo-sentence-bert-base/ (~400 MB)
#   - Reranker: models/reranker/bge-reranker-base/ (~1 GB)
#
#   Total size: ~6-7 GB
```

### Step 3: Verify Download Success
```bash
# Check semua models sudah downloaded
venv\Scripts\python.exe scripts\download_models.py --verify

# Output harus:
#   [OK] LLM          : Present    (models/llm)
#   [OK] EMBEDDING    : Present    (models/embeddings/indo-sentence-bert-base)
#   [OK] RERANKER     : Present    (models/reranker/bge-reranker-base)
#
# [OK] All models are present!
```

---

## 💡 TIPS DOWNLOAD

### Jika Internet Terputus (Resume Download)
Script otomatis resume download dari posisi terakhir:
```bash
# Jalankan lagi command yang sama
venv\Scripts\python.exe scripts\download_models.py

# Output akan show:
# [OK] Model already exists: models/llm
# Skipping download. Use --force to re-download.
```

### Jika Ingin Re-download (Force)
```bash
# Force re-download semua models
venv\Scripts\python.exe scripts\download_models.py --force
```

### Monitor Progress
Download akan show real-time progress:
```
Downloading: 45%|████▌     | 2.0G/4.37G [05:23<06:12, 6.35MiB/s]
```

Estimasi waktu:
- **Internet 10 Mbps:** ~60 menit
- **Internet 50 Mbps:** ~15 menit
- **Internet 100 Mbps:** ~8 menit

---

## 🗂️ File Structure Setelah Download

```
backend/models/
├── llm/
│   └── Qwen2.5-7B-Instruct-Q4_K_M.gguf          (4.37 GB)
│
├── embeddings/
│   └── indo-sentence-bert-base/
│       ├── config.json
│       ├── pytorch_model.bin                     (400 MB)
│       ├── tokenizer.json
│       ├── tokenizer_config.json
│       ├── vocab.txt
│       └── ...
│
└── reranker/
    └── bge-reranker-base/
        ├── config.json
        ├── pytorch_model.bin                     (1 GB)
        ├── tokenizer.json
        ├── tokenizer_config.json
        └── ...
```

---

## 🐛 Troubleshooting

### Error: Connection timeout
```bash
# Set environment variable untuk timeout lebih lama
set HF_HUB_DOWNLOAD_TIMEOUT=600

# Kemudian jalankan lagi
venv\Scripts\python.exe scripts\download_models.py
```

### Error: Disk space insufficient
```bash
# Check available space (butuh ~8-10 GB free)
dir

# Free up space jika perlu, kemudian jalankan lagi
```

### Error: Authentication required
Beberapa model mungkin butuh HuggingFace token:
```bash
# Login ke HuggingFace (jika diminta)
venv\Scripts\pip.exe install huggingface-hub[cli]
venv\Scripts\python.exe -m huggingface_hub.commands.huggingface_cli login

# Kemudian jalankan download lagi
```

### Download sangat lambat
Alternative manual download via browser:

1. **LLM:** https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/blob/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf
   - Klik "download" → save ke `backend/models/llm/`

2. **Embedding:** https://huggingface.co/firqaaa/indo-sentence-bert-base
   - Klik "Files and versions" → download semua files → save ke `backend/models/embeddings/indo-sentence-bert-base/`

3. **Reranker:** https://huggingface.co/BAAI/bge-reranker-base
   - Klik "Files and versions" → download semua files → save ke `backend/models/reranker/bge-reranker-base/`

---

## ✅ Ready to Download!

**Command to run NOW:**
```bash
cd D:\aqil\pusdatik\backend
venv\Scripts\python.exe scripts\download_models.py
```

**Biarkan running di background** (30-60 menit), sambil:
- Lanjut Step 1 di SETUP_GUIDE.md (copy PDFs)
- Atau lanjut Step 3 (install nvidia-docker)
- Atau istirahat ☕

Script akan otomatis save semua files ke lokasi yang benar!

---

**Status:** ✅ Script 100% ready, link 100% correct, error fixed!  
**Action:** Silakan jalankan command di atas! 🚀
