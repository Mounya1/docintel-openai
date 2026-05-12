"""
OCR Service — extracts raw text from uploaded documents.

Supported:
  • PDF  → pypdf (text layer) with optional Tesseract fallback for scanned PDFs
  • Images (jpg/png) → Tesseract OCR (if enabled) or base64 passthrough to Claude
  • DOCX/XLSX → text extraction via python-docx / openpyxl stubs
"""

import io
import base64
import logging
from pathlib import Path
from typing import Tuple

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def extract_text_from_file(file_path: Path) -> Tuple[str, int]:
    """
    Returns (text_content, estimated_page_count).
    text_content is capped at 20,000 chars to stay within LLM context.
    """
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        return _extract_pdf(file_path)
    elif ext in {".jpg", ".jpeg", ".png", ".webp"}:
        return _extract_image(file_path)
    elif ext == ".docx":
        return _extract_docx(file_path)
    elif ext == ".xlsx":
        return _extract_xlsx(file_path)
    elif ext in {".txt", ".csv"}:
        text = file_path.read_text(errors="ignore")[:20_000]
        return text, 1
    else:
        logger.warning(f"Unsupported file type: {ext}")
        return f"[Unsupported file type: {ext}]", 0


def _extract_pdf(path: Path) -> Tuple[str, int]:
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        text = "\n\n".join(pages)

        if not text.strip() and settings.use_tesseract:
            # Scanned PDF — fall back to Tesseract
            logger.info("PDF has no text layer — falling back to Tesseract OCR")
            return _ocr_pdf_with_tesseract(path, len(reader.pages))

        return text[:20_000], len(reader.pages)
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return f"[PDF extraction failed: {e}]", 0


def _ocr_pdf_with_tesseract(path: Path, page_count: int) -> Tuple[str, int]:
    """Convert PDF pages to images and OCR each one."""
    try:
        import pytesseract
        from PIL import Image
        # Requires pdf2image: pip install pdf2image + poppler
        from pdf2image import convert_from_path

        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

        images = convert_from_path(str(path), dpi=200, first_page=1, last_page=min(10, page_count))
        texts = [pytesseract.image_to_string(img) for img in images]
        return "\n\n".join(texts)[:20_000], page_count
    except ImportError:
        logger.warning("pdf2image or pytesseract not installed — skipping OCR")
        return "[Scanned PDF — OCR not available]", page_count
    except Exception as e:
        logger.error(f"Tesseract OCR failed: {e}")
        return f"[OCR failed: {e}]", page_count


def _extract_image(path: Path) -> Tuple[str, int]:
    """For images, return base64 encoding for Claude's vision input."""
    try:
        from PIL import Image

        # Resize large images to keep within API limits
        img = Image.open(path)
        max_dim = 1568
        if max(img.size) > max_dim:
            ratio = max_dim / max(img.size)
            img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        # Return a special marker so the extraction service knows to send as image
        return f"__IMAGE_BASE64__:{b64}", 1
    except Exception as e:
        logger.error(f"Image extraction error: {e}")
        return f"[Image extraction failed: {e}]", 1


def _extract_docx(path: Path) -> Tuple[str, int]:
    try:
        import docx
        doc = docx.Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs)
        # Rough page estimate
        pages = max(1, len(text) // 3000)
        return text[:20_000], pages
    except ImportError:
        logger.warning("python-docx not installed")
        return "[DOCX extraction requires: pip install python-docx]", 0
    except Exception as e:
        logger.error(f"DOCX extraction error: {e}")
        return f"[DOCX extraction failed: {e}]", 0


def _extract_xlsx(path: Path) -> Tuple[str, int]:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        sheets_text = []
        for sheet in wb.sheetnames:
            ws = wb[sheet]
            rows = []
            for row in ws.iter_rows(values_only=True):
                row_vals = [str(c) if c is not None else "" for c in row]
                rows.append("\t".join(row_vals))
            sheets_text.append(f"[Sheet: {sheet}]\n" + "\n".join(rows[:200]))
        text = "\n\n".join(sheets_text)
        return text[:20_000], len(wb.sheetnames)
    except ImportError:
        logger.warning("openpyxl not installed")
        return "[XLSX extraction requires: pip install openpyxl]", 0
    except Exception as e:
        logger.error(f"XLSX extraction error: {e}")
        return f"[XLSX extraction failed: {e}]", 0
