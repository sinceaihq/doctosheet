"""Reading PDFs: text layer with positions, embedded e-invoice files, page images.

PDFs are untrusted input. Callers run this in a separate process with time and
memory limits (see sandbox.py); here we cap size and page count and never
execute anything embedded in the file (JavaScript, forms, actions are ignored).
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from .layout import Word
from .model import Box, Page

MAX_PAGES = 20
# Pages with fewer characters than this in the text layer are treated as scanned.
MIN_TEXT_CHARS = 40
EMBEDDED_XML_NAMES = (
    "factur-x.xml",
    "zugferd-invoice.xml",
    "zugferd_invoice.xml",
    "xrechnung.xml",
    "order-x.xml",
)

logging.getLogger("pdfminer").setLevel(logging.ERROR)


class PdfError(ValueError):
    pass


def clean_text(text: str) -> str:
    """Control characters (some PDFs map spaces to NUL) and odd spaces become plain spaces."""
    return "".join(" " if (ord(c) < 32 or c in "\u00a0\u2007\u202f\u2009\u200a") else c for c in text)


@dataclass
class PdfContent:
    pages: list[Page]
    words: list[Word]
    # Indices of pages without a usable text layer.
    scanned_pages: list[int]
    embedded_xml: tuple[str, bytes] | None


def read_pdf(data: bytes) -> PdfContent:
    import pdfplumber

    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception as exc:  # malformed or encrypted
        raise PdfError(f"Could not open the PDF ({type(exc).__name__}).") from exc
    with pdf:
        if len(pdf.pages) > MAX_PAGES:
            raise PdfError(f"The PDF has {len(pdf.pages)} pages; at most {MAX_PAGES} are supported.")
        pages: list[Page] = []
        words: list[Word] = []
        scanned: list[int] = []
        for i, page in enumerate(pdf.pages):
            pages.append(Page(float(page.width), float(page.height)))
            page_words = page.extract_words(keep_blank_chars=False, use_text_flow=False, x_tolerance=1.5)
            chars = sum(len(w["text"]) for w in page_words)
            if chars < MIN_TEXT_CHARS:
                scanned.append(i)
                continue
            for w in page_words:
                words.append(
                    Word(
                        clean_text(w["text"]),
                        Box(i, float(w["x0"]), float(w["top"]), float(w["x1"]), float(w["bottom"])),
                    )
                )
    return PdfContent(pages, words, scanned, embedded_files(data))


def embedded_files(data: bytes) -> tuple[str, bytes] | None:
    """The embedded e-invoice XML of a Factur-X/ZUGFeRD/XRechnung PDF, if any."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        attachments = reader.attachments
    except Exception:
        return None
    for name, contents in attachments.items():
        if name.lower() in EMBEDDED_XML_NAMES or name.lower().endswith(".xml"):
            if contents:
                return name, contents[0]
    return None


def render_pages(data: bytes, indices: list[int], dpi: int = 200) -> list[tuple[int, object, float]]:
    """Render pages for OCR: (page index, PIL image, scale from pixels to PDF points)."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(data)
    try:
        out = []
        for i in indices:
            page = doc[i]
            scale = dpi / 72
            image = page.render(scale=scale).to_pil().convert("RGB")
            out.append((i, image, 1 / scale))
        return out
    finally:
        doc.close()
