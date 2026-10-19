"""Result types. Every extracted value records where it came from."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

# Where a value was read from, from most to least reliable.
#   xml  - structured e-invoice data (Factur-X/ZUGFeRD, XRechnung, Peppol UBL, Finvoice)
#   text - the PDF's own text layer
#   ocr  - optical character recognition of a scanned page or photo
#   computed - derived from other values (never filled in silently; see Field.computed)
Source = Literal["xml", "text", "ocr", "computed"]
Confidence = Literal["high", "medium", "low"]

HEADER_FIELDS = (
    "invoice_number",
    "issue_date",
    "due_date",
    "currency",
    "seller_name",
    "seller_vat_id",
    "buyer_name",
    "buyer_vat_id",
    "iban",
    "net_amount",
    "vat_amount",
    "total_amount",
)

FIELD_LABELS = {
    "invoice_number": "Invoice number",
    "issue_date": "Invoice date",
    "due_date": "Due date",
    "currency": "Currency",
    "seller_name": "Seller",
    "seller_vat_id": "Seller VAT number",
    "buyer_name": "Buyer",
    "buyer_vat_id": "Buyer VAT number",
    "iban": "IBAN",
    "net_amount": "Net amount",
    "vat_amount": "VAT amount",
    "total_amount": "Total amount",
}


@dataclass
class Box:
    """A region on a page, in PDF points from the top-left corner (page size in Page)."""

    page: int
    x0: float
    y0: float
    x1: float
    y1: float

    @staticmethod
    def union(boxes: list[Box]) -> Box | None:
        if not boxes:
            return None
        page = boxes[0].page
        same = [b for b in boxes if b.page == page]
        return Box(
            page,
            min(b.x0 for b in same),
            min(b.y0 for b in same),
            max(b.x1 for b in same),
            max(b.y1 for b in same),
        )


@dataclass
class Field:
    """One extracted value.

    ``value`` is canonical (ISO dates, plain decimals with a dot, ISO currency
    codes, compact VAT numbers and IBANs); ``raw`` is the text as printed.
    """

    value: str | None
    raw: str | None = None
    source: Source | None = None
    box: Box | None = None
    confidence: Confidence = "low"
    # Why we believe it (or doubt it): label found, checksum valid, totals add up...
    evidence: list[str] = field(default_factory=list)
    # A value derived from others (e.g. total = net + VAT) that is NOT printed on
    # the document. It is offered as a suggestion and never exported unless the
    # user accepts it.
    computed: bool = False


@dataclass
class LineItem:
    description: Field
    quantity: Field
    unit: Field
    unit_price: Field
    vat_rate: Field
    amount: Field
    box: Box | None = None


@dataclass
class VatRow:
    rate: Field
    base: Field
    vat: Field


@dataclass
class Check:
    name: str
    status: Literal["ok", "failed", "not_applicable"]
    detail: str


@dataclass
class Page:
    width: float
    height: float


@dataclass
class Result:
    file_name: str
    kind: Literal["pdf", "image", "xml"]
    pages: list[Page]
    # How the content was read: "xml" (exact), "text" (PDF text layer), "ocr".
    method: Source
    einvoice: str | None  # e.g. "Factur-X/ZUGFeRD (CII)", "Peppol BIS (UBL)"
    fields: dict[str, Field]
    lines: list[LineItem]
    vat_breakdown: list[VatRow]
    checks: list[Check]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def value(self, name: str) -> str | None:
        f = self.fields.get(name)
        return None if f is None or f.computed else f.value


def empty_field() -> Field:
    return Field(value=None)
