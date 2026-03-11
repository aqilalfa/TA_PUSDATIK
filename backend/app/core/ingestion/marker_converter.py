"""
Marker PDF to Markdown Converter
Wrapper for marker-pdf library with robust error handling

Optimized for: GTX 1650 (4GB VRAM), Ryzen 7 2700, 16GB RAM
"""

import os
import gc
import shutil
import time
import traceback
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from loguru import logger


# ============== Configuration for GTX 1650 (4GB VRAM) ==============


class MarkerConfig:
    """Configuration optimized for GTX 1650 4GB VRAM"""

    # VRAM limits (in MB)
    TOTAL_VRAM_MB = 4096
    SAFE_VRAM_MB = 3000  # Leave 1GB for system/display
    VRAM_PER_PAGE_MB = 80  # Estimated VRAM per page

    # Page limits
    MAX_PAGES_SINGLE_BATCH = 35  # Safe limit for 4GB VRAM
    LARGE_PDF_THRESHOLD = 50  # Pages, consider as "large"

    # Timeouts (in seconds)
    TIMEOUT_PER_PAGE = 10  # seconds per page
    MIN_TIMEOUT = 60  # minimum timeout
    MAX_TIMEOUT = 600  # 10 minutes max

    # Retry settings
    MAX_RETRIES = 2
    RETRY_DELAY = 5  # seconds between retries

    # File size limits
    MAX_FILE_SIZE_MB = 100  # Max file size to process


# ============== Error Types ==============


class MarkerErrorType(Enum):
    """Classification of Marker errors"""

    NONE = "none"
    VRAM_INSUFFICIENT = "vram_insufficient"
    CUDA_ERROR = "cuda_error"
    MODEL_LOAD_FAILED = "model_load_failed"
    PDF_CORRUPTED = "pdf_corrupted"
    PDF_ENCRYPTED = "pdf_encrypted"
    TIMEOUT = "timeout"
    OUT_OF_MEMORY = "out_of_memory"
    FILE_TOO_LARGE = "file_too_large"
    UNKNOWN = "unknown"


class MarkerConversionError(Exception):
    """Custom exception for Marker conversion failures"""

    def __init__(
        self,
        message: str,
        error_type: MarkerErrorType = MarkerErrorType.UNKNOWN,
        details: Dict[str, Any] = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}


@dataclass
class ConversionResult:
    """Result of PDF conversion with detailed stats"""

    success: bool
    text: str
    output_path: Optional[str]
    method: str  # "marker", "marker_cached", "fallback_pdfplumber", etc.
    error_type: MarkerErrorType = MarkerErrorType.NONE
    warning: Optional[str] = None
    stats: Dict[str, Any] = None

    def __post_init__(self):
        if self.stats is None:
            self.stats = {}


# ============== Helper Functions ==============


def get_gpu_memory_info() -> Dict[str, float]:
    """Get GPU memory info in MB"""
    try:
        import torch

        if torch.cuda.is_available():
            total = torch.cuda.get_device_properties(0).total_memory / 1024 / 1024
            allocated = torch.cuda.memory_allocated(0) / 1024 / 1024
            cached = torch.cuda.memory_reserved(0) / 1024 / 1024
            free = total - cached
            return {
                "total_mb": total,
                "allocated_mb": allocated,
                "cached_mb": cached,
                "free_mb": free,
                "available": True,
            }
    except Exception as e:
        logger.debug(f"Could not get GPU info: {e}")

    return {"available": False, "free_mb": 0, "total_mb": 0}


def clear_gpu_memory():
    """Clear GPU memory cache"""
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
            logger.debug("Cleared GPU memory cache")
    except Exception as e:
        logger.debug(f"Could not clear GPU memory: {e}")


def get_pdf_info(pdf_path: Path) -> Dict[str, Any]:
    """Get PDF metadata without full processing"""
    info = {
        "exists": False,
        "size_mb": 0,
        "pages": 0,
        "encrypted": False,
        "valid": False,
        "error": None,
    }

    if not pdf_path.exists():
        info["error"] = "File not found"
        return info

    info["exists"] = True
    info["size_mb"] = pdf_path.stat().st_size / 1024 / 1024

    # Try to get page count
    try:
        import fitz

        doc = fitz.open(pdf_path)
        info["pages"] = len(doc)
        info["encrypted"] = doc.is_encrypted
        info["valid"] = True
        doc.close()
    except Exception as e:
        # Try with PyPDF2
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(pdf_path)
            info["pages"] = len(reader.pages)
            info["encrypted"] = reader.is_encrypted
            info["valid"] = True
        except Exception as e2:
            info["error"] = str(e2)

    return info


def classify_error(exception: Exception) -> MarkerErrorType:
    """Classify exception into MarkerErrorType"""
    error_str = str(exception).lower()
    error_type_str = type(exception).__name__.lower()

    # CUDA/GPU errors
    if any(x in error_str for x in ["cuda", "gpu", "device"]):
        if "out of memory" in error_str or "oom" in error_str:
            return MarkerErrorType.VRAM_INSUFFICIENT
        return MarkerErrorType.CUDA_ERROR

    # Memory errors
    if "memory" in error_str or "memoryerror" in error_type_str:
        return MarkerErrorType.OUT_OF_MEMORY

    # Model loading errors
    if any(x in error_str for x in ["model", "weight", "checkpoint", "load"]):
        return MarkerErrorType.MODEL_LOAD_FAILED

    # PDF errors
    if any(x in error_str for x in ["corrupt", "invalid pdf", "damaged"]):
        return MarkerErrorType.PDF_CORRUPTED
    if any(x in error_str for x in ["encrypt", "password", "protected"]):
        return MarkerErrorType.PDF_ENCRYPTED

    # Timeout
    if "timeout" in error_str or "timed out" in error_str:
        return MarkerErrorType.TIMEOUT

    return MarkerErrorType.UNKNOWN


# ============== Main Converter Class ==============


class MarkerConverter:
    """
    Convert PDF documents to Markdown using Marker library.
    Includes robust error handling optimized for GTX 1650 (4GB VRAM).
    """

    def __init__(self, output_dir: str = None):
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            # Default to absolute path: backend/data/marker_output
            # This ensures we use the correct data directory regardless of CWD
            self.output_dir = (
                Path(__file__).parent.parent.parent.parent / "data" / "marker_output"
            )

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._marker_available = None
        self._models_loaded = False
        self._models = None  # Store reference to loaded models for cleanup
        self.config = MarkerConfig()

    def is_available(self) -> bool:
        """Check if Marker library is available"""
        if self._marker_available is None:
            try:
                from marker.converters.pdf import PdfConverter
                from marker.models import create_model_dict

                self._marker_available = True
                logger.info("Marker library is available")
            except ImportError as e:
                self._marker_available = False
                logger.warning(f"Marker library not available: {e}")
        return self._marker_available

    def _preflight_check(
        self, pdf_path: Path
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Pre-flight checks before conversion.

        Returns:
            Tuple of (can_proceed, warning_message, pdf_info)
        """
        pdf_info = get_pdf_info(pdf_path)

        # Check if file exists and is valid
        if not pdf_info["exists"]:
            return False, f"File tidak ditemukan: {pdf_path}", pdf_info

        if not pdf_info["valid"]:
            return (
                False,
                f"PDF tidak valid atau corrupt: {pdf_info.get('error')}",
                pdf_info,
            )

        if pdf_info["encrypted"]:
            return False, "PDF terenkripsi/dilindungi password", pdf_info

        # Check file size
        if pdf_info["size_mb"] > self.config.MAX_FILE_SIZE_MB:
            return (
                False,
                f"File terlalu besar ({pdf_info['size_mb']:.1f}MB > {self.config.MAX_FILE_SIZE_MB}MB)",
                pdf_info,
            )

        # Check GPU memory for large PDFs
        warning = None
        if pdf_info["pages"] > self.config.MAX_PAGES_SINGLE_BATCH:
            gpu_info = get_gpu_memory_info()
            if gpu_info["available"]:
                estimated_vram = pdf_info["pages"] * self.config.VRAM_PER_PAGE_MB
                if estimated_vram > self.config.SAFE_VRAM_MB:
                    warning = f"PDF besar ({pdf_info['pages']} halaman), mungkin butuh waktu lebih lama"
            else:
                warning = f"PDF besar ({pdf_info['pages']} halaman), GPU tidak terdeteksi - akan lebih lambat"

        return True, warning, pdf_info

    def _calculate_timeout(self, pages: int) -> int:
        """Calculate appropriate timeout based on page count"""
        timeout = max(
            self.config.MIN_TIMEOUT,
            min(pages * self.config.TIMEOUT_PER_PAGE, self.config.MAX_TIMEOUT),
        )
        return timeout

    def convert(
        self, pdf_path: str, save_output: bool = True, force_reconvert: bool = False
    ) -> ConversionResult:
        """
        Convert PDF to Markdown using Marker with robust error handling.

        Args:
            pdf_path: Path to PDF file
            save_output: Whether to save Markdown to file
            force_reconvert: Force reconversion even if cached

        Returns:
            ConversionResult with detailed stats and error info
        """
        pdf_file = Path(pdf_path)
        start_time = datetime.now()

        # Initialize result
        result = ConversionResult(
            success=False,
            text="",
            output_path=None,
            method="marker",
            stats={"file": pdf_file.name},
        )

        # === Pre-flight checks ===
        can_proceed, warning, pdf_info = self._preflight_check(pdf_file)
        result.stats.update(pdf_info)

        if warning:
            result.warning = warning
            logger.warning(f"Pre-flight warning: {warning}")

        if not can_proceed:
            result.error_type = (
                MarkerErrorType.PDF_CORRUPTED
                if not pdf_info["valid"]
                else MarkerErrorType.PDF_ENCRYPTED
                if pdf_info.get("encrypted")
                else MarkerErrorType.FILE_TOO_LARGE
            )
            raise MarkerConversionError(warning, result.error_type, pdf_info)

        # === Check for cached output ===
        filename_stem = pdf_file.stem
        output_subdir = self.output_dir / filename_stem
        output_md_path = output_subdir / f"{filename_stem}.md"

        if not force_reconvert and output_md_path.exists():
            logger.info(f"Menggunakan cache Marker: {output_md_path}")
            with open(output_md_path, "r", encoding="utf-8") as f:
                result.text = f.read()
            result.success = True
            result.output_path = str(output_md_path)
            result.method = "marker_cached"
            result.stats["cached"] = True
            result.stats["time_seconds"] = 0
            return result

        # === Check Marker availability ===
        if not self.is_available():
            raise MarkerConversionError(
                "Marker library tidak terinstall", MarkerErrorType.MODEL_LOAD_FAILED
            )

        # === Conversion with retry ===
        last_error = None
        last_error_type = MarkerErrorType.UNKNOWN

        for attempt in range(self.config.MAX_RETRIES + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt}/{self.config.MAX_RETRIES}")
                    clear_gpu_memory()
                    time.sleep(self.config.RETRY_DELAY)

                # Log GPU state
                gpu_info = get_gpu_memory_info()
                if gpu_info["available"]:
                    logger.debug(
                        f"GPU Memory: {gpu_info['free_mb']:.0f}MB free / {gpu_info['total_mb']:.0f}MB total"
                    )

                # Import and run Marker
                markdown_text = self._run_marker_conversion(pdf_file, pdf_info)

                # Success!
                elapsed = (datetime.now() - start_time).total_seconds()

                result.success = True
                result.text = markdown_text
                result.stats["time_seconds"] = elapsed
                result.stats["chars"] = len(markdown_text)
                result.stats["tables"] = markdown_text.count("\n|")

                # Save output
                if save_output:
                    result.output_path = self._save_output(
                        markdown_text, None, output_subdir, filename_stem
                    )

                logger.success(
                    f"Marker berhasil: {pdf_info['pages']} halaman, "
                    f"{len(markdown_text):,} chars dalam {elapsed:.1f}s"
                )

                return result

            except Exception as e:
                last_error = e
                last_error_type = classify_error(e)
                elapsed = (datetime.now() - start_time).total_seconds()

                logger.error(
                    f"Marker error (attempt {attempt + 1}): {last_error_type.value}\n"
                    f"  Detail: {str(e)[:200]}\n"
                    f"  File: {pdf_file.name} ({pdf_info['pages']} pages, {pdf_info['size_mb']:.1f}MB)\n"
                    f"  Elapsed: {elapsed:.1f}s"
                )

                # Don't retry for certain errors
                if last_error_type in [
                    MarkerErrorType.PDF_CORRUPTED,
                    MarkerErrorType.PDF_ENCRYPTED,
                    MarkerErrorType.MODEL_LOAD_FAILED,
                    MarkerErrorType.FILE_TOO_LARGE,
                ]:
                    break

        # All retries failed
        result.error_type = last_error_type
        result.stats["time_seconds"] = (datetime.now() - start_time).total_seconds()

        raise MarkerConversionError(
            f"Marker gagal setelah {self.config.MAX_RETRIES + 1} percobaan: {str(last_error)[:200]}",
            last_error_type,
            {"last_error": str(last_error), "traceback": traceback.format_exc()},
        )

    def _run_marker_conversion(self, pdf_path: Path, pdf_info: Dict) -> str:
        """Run actual Marker conversion"""
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered

        # Load models
        if not self._models_loaded:
            logger.info("Loading Marker models (pertama kali mungkin lambat)...")

        models = create_model_dict()
        self._models = models  # Store reference for cleanup
        self._models_loaded = True

        # Create converter
        converter = PdfConverter(artifact_dict=models)

        # Convert
        logger.info(f"Converting {pdf_info['pages']} halaman...")
        rendered = converter(str(pdf_path))

        # Extract text
        markdown_text, _, images = text_from_rendered(rendered)

        return markdown_text

    def unload_models(self):
        """
        Unload Marker models from GPU memory.
        Call this after conversion to free VRAM for other tasks (e.g., Ollama).
        """
        import torch

        try:
            if self._models is not None:
                logger.info("Unloading Marker models from GPU...")

                # Delete model references
                del self._models
                self._models = None
                self._models_loaded = False

                # Clear GPU memory
                if torch.cuda.is_available():
                    torch.cuda.synchronize()  # Wait for all CUDA operations to complete
                    torch.cuda.empty_cache()

                # Force garbage collection
                gc.collect()

                # Log memory status
                gpu_info = get_gpu_memory_info()
                if gpu_info["available"]:
                    logger.info(
                        f"GPU Memory after unload: {gpu_info['free_mb']:.0f}MB free / {gpu_info['total_mb']:.0f}MB total"
                    )

                logger.success("Marker models unloaded successfully")
        except Exception as e:
            logger.warning(f"Error unloading Marker models: {e}")

    def _save_output(
        self,
        markdown_text: str,
        images: Optional[dict],
        output_dir: Path,
        filename_stem: str,
    ) -> str:
        """Save Markdown output and images to files."""
        output_dir.mkdir(parents=True, exist_ok=True)

        md_path = output_dir / f"{filename_stem}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)
        logger.debug(f"Saved Markdown: {md_path}")

        if images:
            images_dir = output_dir / f"{filename_stem}_images"
            images_dir.mkdir(exist_ok=True)
            for img_name, img_data in images.items():
                try:
                    img_path = images_dir / img_name
                    if hasattr(img_data, "save"):
                        img_data.save(img_path)
                    elif isinstance(img_data, bytes):
                        with open(img_path, "wb") as f:
                            f.write(img_data)
                except Exception as e:
                    logger.warning(f"Gagal simpan image {img_name}: {e}")

        return str(md_path)

    def cleanup_old_outputs(self, max_age_days: int = 30):
        """Clean up old Marker outputs to free disk space."""
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60

        removed_count = 0
        for item in self.output_dir.iterdir():
            if item.is_dir():
                item_age = current_time - item.stat().st_mtime
                if item_age > max_age_seconds:
                    shutil.rmtree(item)
                    removed_count += 1
                    logger.info(f"Removed old output: {item}")

        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old Marker outputs")


# ============== Global Instance ==============

marker_converter = MarkerConverter()


def convert_pdf_to_markdown(
    pdf_path: str, save_output: bool = True, force_reconvert: bool = False
) -> ConversionResult:
    """
    Convenience function to convert PDF to Markdown.

    Returns:
        ConversionResult with success status, text, and stats
    """
    return marker_converter.convert(pdf_path, save_output, force_reconvert)
