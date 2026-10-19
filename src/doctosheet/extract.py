"""From file bytes to a Result: e-invoice XML first, then the PDF text layer, then OCR."""

from __future__ import annotations

import io

from . import einvoice
from .checks import run_checks
from .fields import Doc, extract_fields
from .layout import Word, group_lines
from .lines import extract_lines
from .model import HEADER_FIELDS, Field, Page, Result, Source
from .pdf import PdfError, read_pdf, render_pages

MAX_BYTES = 25 * 1024 * 1024
IMAGE_MAGIC = {b"\x89PNG": "png", b"\xff\xd8\xff": "jpeg", b"II*\x00": "tiff", b"MM\x00*": "tiff", b"RIFF": "webp"}


class UnsupportedFile(ValueError):
    pass


def sniff(data: bytes) -> str:
    head = data[:16]
    if head.startswith(b"%PDF"):
        return "pdf"
    if any(head.startswith(m) for m in IMAGE_MAGIC):
        return "image"
    stripped = data[:200].lstrip(b"\xef\xbb\xbf \t\r\n")
    if stripped.startswith(b"<"):
        return "xml"
    raise UnsupportedFile("Supported files: PDF, PNG, JPEG, TIFF, WebP, and e-invoice XML.")


def extract(data: bytes, file_name: str = "document") -> Result:
    if len(data) > MAX_BYTES:
        raise UnsupportedFile(f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    kind = sniff(data)
    warnings: list[str] = []
    if kind == "xml":
        fmt, fields, items, vat_rows = einvoice.parse(data)
        return _result(file_name, "xml", [], "xml", fmt, fields, items, vat_rows, warnings)

    pages: list[Page]
    words: list[Word] = []
    method: Source = "text"
    if kind == "pdf":
        try:
            content = read_pdf(data)
        except PdfError:
            raise
        pages = content.pages
        if content.embedded_xml is not None:
            name, xml = content.embedded_xml
            try:
                fmt, fields, items, vat_rows = einvoice.parse(xml)
                return _result(file_name, "pdf", pages, "xml", f"{fmt}, embedded as {name}", fields, items, vat_rows,
                               warnings)  # fmt: skip
            except einvoice.EInvoiceError as exc:
                warnings.append(f"The PDF contains {name}, but it could not be read ({exc}); using the printed text.")
        words = content.words
        if content.scanned_pages:
            from .ocr import ocr_image

            if len(content.scanned_pages) == len(pages):
                method = "ocr"
            for i, image, scale in render_pages(data, content.scanned_pages):
                words.extend(ocr_image(image, i, scale))
            warnings.append(
                f"{len(content.scanned_pages)} page(s) had no text layer and were read with OCR: check the values."
            )
    else:
        from PIL import Image

        from .ocr import ocr_image

        image = Image.open(io.BytesIO(data))
        image.load()
        if image.width * image.height > 60_000_000:
            raise UnsupportedFile("The image is too large.")
        image = image.convert("RGB")
        pages = [Page(float(image.width), float(image.height))]
        words = ocr_image(image, 0)
        method = "ocr"
        warnings.append("The document was read with OCR: check the values.")

    if not words:
        warnings.append("No text was found in the document.")
    doc = Doc(group_lines(words), method)
    found, vat_rows = extract_fields(doc)
    fields = {k: v for k, v in found.items() if v is not None}
    items = extract_lines(doc)
    if not items:
        warnings.append("No line item table was recognised.")
    return _result(file_name, kind, pages, method, None, fields, items, vat_rows, warnings)  # type: ignore[arg-type]


def _result(file_name, kind, pages, method, fmt, fields, items, vat_rows, warnings) -> Result:  # type: ignore[no-untyped-def]
    complete: dict[str, Field] = {k: fields.get(k) or Field(None) for k in HEADER_FIELDS}
    checks = run_checks(complete, items, vat_rows)
    missing = [k for k in HEADER_FIELDS if complete[k].value is None]
    if missing:
        warnings.append("Not found: " + ", ".join(m.replace("_", " ") for m in missing) + ".")
    return Result(file_name, kind, pages, method, fmt, complete, items, vat_rows, checks, warnings)
