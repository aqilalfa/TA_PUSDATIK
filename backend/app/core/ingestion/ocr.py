"""
OCR Pipeline for processing PDF documents
Supports both text-selectable PDFs and scanned images
Uses PaddleOCR for Indonesian text recognition
"""

import fitz  # PyMuPDF
from paddleocr import PaddleOCR
from pdf2image import convert_from_path
from PIL import Image
import numpy as np
import cv2
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from loguru import logger
from app.config import settings
import tempfile
import os


class OCRProcessor:
    """Handle OCR detection and text extraction from PDFs"""

    def __init__(self):
        self.ocr_engine = None
        self._initialized = False

    def initialize(self):
        """Initialize PaddleOCR engine"""
        if self._initialized:
            return

        logger.info("Initializing PaddleOCR for Indonesian text...")
        logger.info(f"OCR Engine: {settings.OCR_ENGINE}")
        logger.info(f"Language: {settings.OCR_LANG}")
        logger.info(f"Use GPU: {settings.OCR_USE_GPU}")

        try:
            # Initialize PaddleOCR with Indonesian language
            self.ocr_engine = PaddleOCR(
                lang=settings.OCR_LANG,  # 'id' for Indonesian
                use_angle_cls=True,  # Enable text orientation detection
                use_gpu=settings.OCR_USE_GPU,  # Use GPU if available
                show_log=settings.DEBUG,
            )

            self._initialized = True
            logger.success("✓ PaddleOCR initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            raise

    def detect_ocr_needed(self, pdf_path: str, sample_pages: int = 3) -> bool:
        """
        Detect if PDF needs OCR by checking text content

        Args:
            pdf_path: Path to PDF file
            sample_pages: Number of pages to sample

        Returns:
            True if OCR needed, False if text-selectable
        """
        logger.info(f"Checking if OCR needed for: {pdf_path}")

        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)

            # Sample first few pages
            pages_to_check = min(sample_pages, total_pages)
            total_text = ""

            for page_num in range(pages_to_check):
                page = doc[page_num]
                text = page.get_text()
                total_text += text

            doc.close()

            # If very little text extracted, likely needs OCR
            # Threshold: less than 100 characters means scanned PDF
            text_length = len(total_text.strip())

            if text_length < 100:
                logger.warning(
                    f"PDF appears to be scanned (only {text_length} chars). OCR needed."
                )
                return True
            else:
                logger.info(f"PDF has text layer ({text_length} chars). No OCR needed.")
                return False

        except Exception as e:
            logger.error(f"Error detecting OCR need: {e}")
            # If error, assume OCR needed to be safe
            return True

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text directly from PDF (for text-selectable PDFs)

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text
        """
        logger.info(f"Extracting text from PDF: {pdf_path}")

        try:
            doc = fitz.open(pdf_path)
            full_text = ""

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()

                # Add page marker
                full_text += f"\n\n--- Page {page_num + 1} ---\n\n"
                full_text += text

            doc.close()

            logger.success(f"✓ Extracted {len(full_text)} characters from PDF")
            return full_text

        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR results

        Args:
            image: Input image as numpy array

        Returns:
            Preprocessed image
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray)

        # Enhance contrast (adaptive thresholding)
        enhanced = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        return enhanced

    def ocr_with_paddleocr(self, pdf_path: str) -> str:
        """
        Perform OCR on PDF using PaddleOCR

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text
        """
        if not self._initialized:
            self.initialize()

        logger.info(f"Performing OCR on: {pdf_path}")

        try:
            # Convert PDF to images
            logger.info("Converting PDF to images...")
            images = convert_from_path(pdf_path, dpi=300)
            logger.info(f"Converted {len(images)} pages to images")

            full_text = ""

            # Process each page
            for page_num, image in enumerate(images):
                logger.info(f"OCR processing page {page_num + 1}/{len(images)}...")

                # Convert PIL Image to numpy array
                img_array = np.array(image)

                # Preprocess image
                preprocessed = self.preprocess_image(img_array)

                # Perform OCR
                result = self.ocr_engine.ocr(preprocessed, cls=True)

                # Extract text from OCR result
                page_text = ""
                if result and result[0]:
                    for line in result[0]:
                        if line[1]:  # Check if text exists
                            text = line[1][0]  # Get text (first element of tuple)
                            confidence = line[1][1]  # Get confidence

                            # Only include high-confidence results
                            if confidence > 0.5:
                                page_text += text + " "

                # Add page marker
                full_text += f"\n\n--- Page {page_num + 1} ---\n\n"
                full_text += page_text

                logger.info(
                    f"Page {page_num + 1}: Extracted {len(page_text)} characters"
                )

            logger.success(
                f"✓ OCR completed. Extracted {len(full_text)} total characters"
            )
            return full_text

        except Exception as e:
            logger.error(f"Error during OCR: {e}")
            raise

    def process_pdf(self, pdf_path: str, force_ocr: bool = False) -> Tuple[str, bool]:
        """
        Process PDF and extract text (with or without OCR)

        Args:
            pdf_path: Path to PDF file
            force_ocr: Force OCR even if text-selectable

        Returns:
            Tuple of (extracted_text, ocr_was_used)
        """
        logger.info(f"Processing PDF: {pdf_path}")

        # Check if file exists
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        # Detect if OCR is needed
        needs_ocr = force_ocr or self.detect_ocr_needed(pdf_path)

        if needs_ocr:
            logger.info("Using OCR to extract text...")
            text = self.ocr_with_paddleocr(pdf_path)
            ocr_used = True
        else:
            logger.info("Extracting text directly from PDF...")
            text = self.extract_text_from_pdf(pdf_path)
            ocr_used = False

        logger.success(f"✓ PDF processing complete. Text length: {len(text)}")

        return text, ocr_used

    def save_ocr_result(self, text: str, output_path: str):
        """Save OCR result to file"""
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info(f"OCR result saved to: {output_path}")
        except Exception as e:
            logger.error(f"Error saving OCR result: {e}")
            raise


# Global OCR processor instance
ocr_processor = OCRProcessor()


def process_pdf_with_ocr(pdf_path: str, force_ocr: bool = False) -> Tuple[str, bool]:
    """
    Convenience function to process PDF with OCR

    Args:
        pdf_path: Path to PDF file
        force_ocr: Force OCR even if text-selectable

    Returns:
        Tuple of (extracted_text, ocr_was_used)
    """
    return ocr_processor.process_pdf(pdf_path, force_ocr)
