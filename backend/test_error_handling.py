"""
Test Marker error handling improvements
"""

import sys
from pathlib import Path

# Test imports
print("Testing imports...")
try:
    from app.core.ingestion.marker_converter import (
        marker_converter,
        MarkerConfig,
        MarkerErrorType,
        ConversionResult,
        get_gpu_memory_info,
        get_pdf_info,
        clear_gpu_memory,
    )
    from app.core.ingestion.document_manager import (
        extract_text_from_pdf,
        ExtractionResult,
    )

    print("[OK] All imports successful")
except Exception as e:
    print(f"[FAIL] Import error: {e}")
    sys.exit(1)

# Test GPU info
print("\n=== GPU Info ===")
gpu = get_gpu_memory_info()
print(f"GPU Available: {gpu['available']}")
if gpu["available"]:
    print(f"GPU Total: {gpu['total_mb']:.0f} MB")
    print(f"GPU Free: {gpu['free_mb']:.0f} MB")
    print(f"GPU Allocated: {gpu['allocated_mb']:.0f} MB")

# Test config
print("\n=== Config for GTX 1650 ===")
config = MarkerConfig()
print(f"Total VRAM: {config.TOTAL_VRAM_MB} MB")
print(f"Safe VRAM: {config.SAFE_VRAM_MB} MB")
print(f"Max pages (single batch): {config.MAX_PAGES_SINGLE_BATCH}")
print(f"VRAM per page: {config.VRAM_PER_PAGE_MB} MB")
print(f"Max retries: {config.MAX_RETRIES}")
print(f"Retry delay: {config.RETRY_DELAY}s")
print(f"Timeout per page: {config.TIMEOUT_PER_PAGE}s")
print(f"Max timeout: {config.MAX_TIMEOUT}s")

# Test PDF info function
print("\n=== PDF Info Test ===")
test_pdf = Path(
    r"D:\aqil\pusdatik\data\documents\peraturan\Perpres Nomor 95 Tahun 2018.pdf"
)
if test_pdf.exists():
    pdf_info = get_pdf_info(test_pdf)
    print(f"File: {test_pdf.name}")
    print(f"Size: {pdf_info['size_mb']:.2f} MB")
    print(f"Pages: {pdf_info['pages']}")
    print(f"Valid: {pdf_info['valid']}")
    print(f"Encrypted: {pdf_info['encrypted']}")
else:
    print(f"Test PDF not found: {test_pdf}")

# Test Marker availability
print("\n=== Marker Availability ===")
print(f"Marker available: {marker_converter.is_available()}")

# Test extraction with details
print("\n=== Extraction Test (with details) ===")
if test_pdf.exists():
    result = extract_text_from_pdf(test_pdf, return_details=True)
    print(f"Success: {result.success}")
    print(f"Method: {result.method}")
    print(f"Text length: {len(result.text):,} chars")
    if result.warning:
        print(f"Warning: {result.warning}")
    if result.error:
        print(f"Error: {result.error}")
    print(f"Stats: {result.stats}")

print("\n=== ALL TESTS COMPLETED ===")
