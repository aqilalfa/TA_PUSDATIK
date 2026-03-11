# OCR Pipeline - Quick Start & Testing Guide

## 🚀 Quick Start: Test OCR dengan 3 Dokumen Anda

Sekarang Anda bisa test OCR pipeline dengan 3 dokumen PDF yang sudah ada!

---

## 📋 Prerequisites

Pastikan Docker sudah running:
```bash
docker-compose -f docker-compose.dev.yml up -d
```

---

## 🧪 Step-by-Step Testing

### Step 1: Upload Dokumen Anda

```bash
# Copy 3 dokumen PDF ke dalam container
# Asumsi dokumen ada di: D:\aqil\documents\

# Dokumen 1 (Peraturan)
docker cp D:\aqil\documents\PP_71_2019.pdf spbe-backend:/app/data/documents/peraturan/

# Dokumen 2 (Audit)
docker cp D:\aqil\documents\audit_2023.pdf spbe-backend:/app/data/documents/audit/

# Dokumen 3 (Other)
docker cp D:\aqil\documents\dokumen_lainnya.pdf spbe-backend:/app/data/documents/others/

# Atau copy ke local directory:
# cp /path/to/your/pdfs/*.pdf data/documents/
```

### Step 2: Test OCR Detection (Cek apakah perlu OCR)

```bash
# Test dokumen 1
docker-compose -f docker-compose.dev.yml exec backend python -c "
from app.core.ingestion.ocr import ocr_processor
needs_ocr = ocr_processor.detect_ocr_needed('/app/data/documents/peraturan/PP_71_2019.pdf')
print(f'OCR needed: {needs_ocr}')
"

# Output example:
# OCR needed: False  (jika text-selectable)
# OCR needed: True   (jika scanned)
```

### Step 3: Test Single PDF dengan Test Script

```bash
# Test dokumen peraturan
docker-compose -f docker-compose.dev.yml exec backend \
  python scripts/test_ocr.py \
  --file /app/data/documents/peraturan/PP_71_2019.pdf

# Output:
# ======================================================================
# Testing OCR on: /app/data/documents/peraturan/PP_71_2019.pdf
# ======================================================================
# 
# [STEP 1] Detecting if OCR is needed...
#   ✓ Detection complete: Text-selectable
#   ⏱ Detection time: 0.18s
# 
# [STEP 2] Processing PDF...
#   ✓ Processing complete
#   ⏱ Processing time: 1.23s
#   📄 Text extracted: 45623 chars, 6234 words
# 
# [STEP 3] Assessing text quality...
#   Quality Score: 94/100
#     - Readability: 96/100
#     - Indonesian content: 90/100
#     - Structure: 95/100
# 
# [STEP 4] Text Preview...
#   First 500 chars: PERATURAN PEMERINTAH REPUBLIK INDONESIA NOMOR 71 TAHUN 2019...
# 
# ======================================================================
# ✓ OCR Test PASSED
# ======================================================================
# Summary:
#   • File size: 2.34 MB
#   • OCR used: No
#   • Processing time: 1.23s
#   • Text extracted: 6234 words
#   • Quality score: 94/100
# ======================================================================
```

### Step 4: Test Semua 3 Dokumen Sekaligus

```bash
# Test batch - semua dokumen dalam directory
docker-compose -f docker-compose.dev.yml exec backend \
  python scripts/test_ocr.py \
  --dir /app/data/documents \
  --output-report /app/data/ocr_test_results.json

# Output:
# Found 3 PDF files to test
# 
# ======================================================================
# Test 1/3
# ======================================================================
# [Processing dokumen 1...]
# 
# ======================================================================
# Test 2/3
# ======================================================================
# [Processing dokumen 2...]
# 
# ======================================================================
# Test 3/3
# ======================================================================
# [Processing dokumen 3...]
# 
# ======================================================================
# OCR TEST REPORT
# ======================================================================
# Total tests: 3
#   ✓ Successful: 3
#   ✗ Failed: 0
# 
# Performance Metrics:
#   • Avg processing time: 45.23s
#   • Avg quality score: 89.3/100
#   • OCR used: 2/3 files
# 
# Detailed Results:
#   File: PP_71_2019.pdf
#     Size: 2.34 MB
#     OCR: No
#     Time: 1.23s
#     Words: 6234
#     Quality: 94/100
# 
#   File: audit_2023.pdf
#     Size: 4.56 MB
#     OCR: Yes
#     Time: 125.45s
#     Words: 8456
#     Quality: 87/100
# 
#   File: dokumen_lainnya.pdf
#     Size: 1.23 MB
#     OCR: Yes
#     Time: 35.67s
#     Words: 3234
#     Quality: 86/100
# 
# ✓ Report saved to: /app/data/ocr_test_results.json
```

### Step 5: Force OCR Test (untuk compare quality)

```bash
# Test dengan force OCR pada dokumen text-selectable
# Untuk compare: direct extraction vs OCR quality

docker-compose -f docker-compose.dev.yml exec backend \
  python scripts/test_ocr.py \
  --file /app/data/documents/peraturan/PP_71_2019.pdf \
  --force-ocr

# Compare results:
# Without OCR: 1.23s, Quality: 94/100
# With OCR:    ~50s,  Quality: ~92/100
# 
# Conclusion: Text-selectable PDF lebih baik direct extraction
```

---

## 📊 View Test Results

```bash
# View JSON report
docker-compose -f docker-compose.dev.yml exec backend \
  cat /app/data/ocr_test_results.json

# Or copy to local:
docker cp spbe-backend:/app/data/ocr_test_results.json ./ocr_results.json

# Then open in browser/text editor
```

---

## 🔬 Advanced Testing

### Test 1: OCR Quality Assessment

```bash
# Test quality dengan different preprocessing
docker-compose -f docker-compose.dev.yml exec backend python -c "
from app.core.ingestion.ocr import ocr_processor
from scripts.test_ocr import OCRTester

# Process PDF
text, ocr_used = ocr_processor.process_pdf(
    '/app/data/documents/audit/audit_2023.pdf'
)

# Assess quality
tester = OCRTester()
quality = tester.assess_text_quality(text)

print(f'Quality Assessment:')
print(f'  Overall: {quality[\"overall_score\"]}/100')
print(f'  Readability: {quality[\"readability_score\"]}/100')
print(f'  Indonesian: {quality[\"indonesian_score\"]}/100')
print(f'  Structure: {quality[\"structure_score\"]}/100')
"
```

### Test 2: Performance Benchmarking

```bash
# Measure processing time untuk different scenarios
docker-compose -f docker-compose.dev.yml exec backend python -c "
from app.core.ingestion.ocr import ocr_processor
import time

pdf_path = '/app/data/documents/peraturan/PP_71_2019.pdf'

# Benchmark 1: Detection only
start = time.time()
needs_ocr = ocr_processor.detect_ocr_needed(pdf_path)
detection_time = time.time() - start
print(f'Detection time: {detection_time:.2f}s')

# Benchmark 2: Direct extraction
start = time.time()
text = ocr_processor.extract_text_from_pdf(pdf_path)
extraction_time = time.time() - start
print(f'Direct extraction: {extraction_time:.2f}s')

# Benchmark 3: Full pipeline
start = time.time()
text, ocr_used = ocr_processor.process_pdf(pdf_path)
total_time = time.time() - start
print(f'Full pipeline: {total_time:.2f}s')
print(f'OCR used: {ocr_used}')
"
```

### Test 3: Memory Usage Monitoring

```bash
# Monitor GPU memory during OCR
# Terminal 1: Watch GPU
watch -n 1 nvidia-smi

# Terminal 2: Run OCR
docker-compose -f docker-compose.dev.yml exec backend \
  python scripts/test_ocr.py \
  --file /app/data/documents/audit/large_audit.pdf

# Observe GPU memory usage during processing
```

---

## 🎯 Expected Results untuk 3 Dokumen Anda

Berdasarkan spesifikasi (<5MB, <100 halaman):

### Scenario 1: Semua Text-selectable
```
Document 1 (Peraturan, 50 pages):
  Detection: 0.2s
  Processing: 1.5s
  Quality: 90-95/100
  OCR used: No

Document 2 (Audit, 80 pages):
  Detection: 0.3s
  Processing: 2.3s
  Quality: 85-90/100
  OCR used: No

Document 3 (Other, 30 pages):
  Detection: 0.1s
  Processing: 0.8s
  Quality: 85-90/100
  OCR used: No

Total time: ~5s
```

### Scenario 2: Semua Scanned (Perlu OCR)
```
Document 1 (Peraturan, 50 pages):
  Detection: 0.2s
  OCR Processing: ~140s (2.8s/page)
  Quality: 85-92/100
  OCR used: Yes

Document 2 (Audit, 80 pages):
  Detection: 0.3s
  OCR Processing: ~224s (2.8s/page)
  Quality: 80-88/100
  OCR used: Yes

Document 3 (Other, 30 pages):
  Detection: 0.1s
  OCR Processing: ~84s (2.8s/page)
  Quality: 82-88/100
  OCR used: Yes

Total time: ~450s (~7.5 minutes)
GPU Usage: 85-95%
```

### Scenario 3: Mixed (Realistic)
```
Document 1 (Text-selectable): ~1.5s
Document 2 (Scanned): ~224s
Document 3 (Text-selectable): ~0.8s

Total time: ~226s (~3.8 minutes)
Average quality: ~87/100
```

---

## 🔍 Troubleshooting

### Issue: "No PDF files found"

```bash
# Check files exist
docker-compose -f docker-compose.dev.yml exec backend ls -la /app/data/documents/

# If empty, copy files:
docker cp your-file.pdf spbe-backend:/app/data/documents/
```

### Issue: "OCR too slow"

```bash
# Check GPU utilization
nvidia-smi

# Should show:
# - GPU utilization: 80-95%
# - Memory usage: ~1.5-2.5 GB
# - Process: python (PaddleOCR)

# If GPU not used:
# Check settings.OCR_USE_GPU=true in .env
```

### Issue: "Low quality results"

```bash
# Regenerate dengan higher DPI atau preprocessing adjustments
# Edit app/core/ingestion/ocr.py:
# - Increase DPI: 300 → 400
# - Adjust preprocessing thresholds
# - Lower confidence filter: 0.5 → 0.4
```

---

## 📈 Next Steps After Testing

Setelah OCR test berhasil:

1. **Lanjut ke Ingestion:**
```bash
# Process dan index ke vector store
docker-compose -f docker-compose.dev.yml exec backend \
  python scripts/ingest_documents.py --input-dir /app/data/documents
```

2. **Check Vector Store:**
```bash
# Open Qdrant dashboard
http://localhost:6333/dashboard

# Check collection 'spbe_documents'
# Should see indexed chunks dari 3 dokumen
```

3. **Test Retrieval:**
```bash
# Coming in Week 3-4: Hybrid retrieval testing
```

---

## ✅ Success Checklist

- [ ] 3 dokumen PDF copied ke `/app/data/documents/`
- [ ] OCR detection test berhasil
- [ ] Single PDF test berhasil
- [ ] Batch test (3 dokumen) berhasil
- [ ] Quality scores >80/100
- [ ] Processing time acceptable
- [ ] GPU utilization >80% (jika OCR used)
- [ ] Test report generated

Jika semua ✅, OCR pipeline ready! 🎉

---

## 🎓 Tips & Best Practices

1. **Organize Documents by Type:**
```
data/documents/
├── peraturan/   # PP, Perpres, Permen
├── audit/       # Laporan audit
└── others/      # Lainnya
```

2. **Keep OCR Results:**
```bash
# OCR results automatically saved to:
data/ocr_output/{filename}_ocr.txt

# Use for debugging or re-processing
```

3. **Monitor Quality:**
```bash
# Always check quality score
# If <70: Review results manually
# If 70-85: Good for most use cases
# If >85: Excellent quality
```

4. **GPU Memory Management:**
```bash
# If processing large batches:
# - Process 1-2 PDFs at a time
# - Let GPU cool down between batches
# - Monitor with nvidia-smi
```

---

**Ready to test! Happy OCR-ing! 🚀📄**
