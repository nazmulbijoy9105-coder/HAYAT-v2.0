"""
HAYAT v2.0 — Document Intelligence Service
Layer 2: Turn documents into clean structured text.
OCR, layout detection, table extraction, language detection.
"""

import io
from typing import Optional, Dict, Any, List
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import pdfplumber
from pdfplumber.utils import extract_text

from app.core.config import settings
from app.core.logging import get_logger
from app.db.minio import DocumentStorage
from app.models.legal import Document, DocumentStatus

logger = get_logger("hayat.processor")


class DocumentProcessor:
    """
    Document intelligence pipeline:
    PDF → Text extraction → OCR fallback → Layout analysis → Table extraction
    """

    def __init__(self):
        self.storage = DocumentStorage()

    def _extract_text_pymupdf(self, pdf_bytes: bytes) -> tuple[str, int, dict]:
        """Extract text using PyMuPDF (fast, good layout preservation)."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text_parts = []
        page_count = len(doc)
        metadata = doc.metadata

        for page in doc:
            text = page.get_text("text")
            if text.strip():
                text_parts.append(text)

        doc.close()
        full_text = "\n\n".join(text_parts)
        return full_text, page_count, metadata

    def _extract_text_pdfplumber(self, pdf_bytes: bytes) -> tuple[str, List[dict]]:
        """Extract text and tables using pdfplumber."""
        tables = []
        text_parts = []

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

                page_tables = page.extract_tables()
                for table in page_tables:
                    tables.append({
                        "page": page.page_number,
                        "data": table,
                    })

        full_text = "\n\n".join(text_parts)
        return full_text, tables

    def _ocr_page(self, image: Image.Image, lang: str = "eng+ben") -> tuple[str, float]:
        """OCR a single page image."""
        try:
            text = pytesseract.image_to_string(image, lang=lang)
            data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)

            # Calculate confidence
            confidences = [int(c) for c in data["conf"] if int(c) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            return text, avg_confidence / 100.0
        except Exception as e:
            logger.error("ocr_failed", error=str(e))
            return "", 0.0

    def _pdf_page_to_image(self, pdf_bytes: bytes, page_num: int, dpi: int = 300) -> Image.Image:
        """Convert PDF page to image for OCR."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()
        return img

    def _detect_language(self, text: str) -> str:
        """Detect if text is Bengali, English, or mixed."""
        if not text:
            return "unknown"

        bengali_chars = sum(1 for c in text if '\u0980' <= c <= '\u09FF')
        total_chars = len(text.strip())

        if total_chars == 0:
            return "unknown"

        ratio = bengali_chars / total_chars
        if ratio > 0.5:
            return "ben"
        elif ratio > 0.1:
            return "ben+eng"
        else:
            return "eng"

    def _clean_text(self, text: str) -> str:
        """Clean extracted text: remove headers, footers, page numbers."""
        import re

        # Remove common page number patterns
        text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
        text = re.sub(r'Page\s*\d+\s*of\s*\d+', '', text, flags=re.IGNORECASE)

        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        return text.strip()

    async def process_document(self, document: Document) -> Dict[str, Any]:
        """
        Main processing pipeline:
        1. Download from MinIO
        2. Extract text (native → OCR fallback)
        3. Detect language
        4. Clean text
        5. Extract tables
        6. Return structured result
        """
        logger.info("processing_started", doc_id=document.id, title=document.title)

        try:
            # Download
            pdf_bytes = self.storage.download_document(document.object_path)

            # Attempt native text extraction
            native_text, page_count, metadata = self._extract_text_pymupdf(pdf_bytes)

            # If native text is too short, fallback to OCR
            if len(native_text.strip()) < 500:
                logger.info("ocr_fallback_triggered", doc_id=document.id)
                ocr_texts = []
                confidences = []

                for i in range(min(page_count, 50)):  # Limit to 50 pages
                    img = self._pdf_page_to_image(pdf_bytes, i, settings.ocr_dpi)
                    text, conf = self._ocr_page(img, settings.ocr_language)
                    ocr_texts.append(text)
                    confidences.append(conf)

                native_text = "\n\n".join(ocr_texts)
                ocr_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            else:
                ocr_confidence = 1.0

            # Clean text
            cleaned_text = self._clean_text(native_text)

            # Detect language
            language = self._detect_language(cleaned_text)

            # Extract tables
            _, tables = self._extract_text_pdfplumber(pdf_bytes)

            result = {
                "text": cleaned_text,
                "page_count": page_count,
                "language": language,
                "ocr_confidence": ocr_confidence,
                "tables": tables[:20],  # Limit tables
                "metadata": {
                    "title": metadata.get("title", ""),
                    "author": metadata.get("author", ""),
                    "creation_date": metadata.get("creationDate", ""),
                },
                "word_count": len(cleaned_text.split()),
            }

            logger.info("processing_completed", doc_id=document.id, word_count=result["word_count"])
            return result

        except Exception as e:
            logger.error("processing_failed", doc_id=document.id, error=str(e))
            raise
