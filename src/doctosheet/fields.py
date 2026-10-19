"""Header fields from positioned text lines (PDF text layer or OCR).

Each field is located through a label ("Due date", "Eräpäivä", "Fällig am" …)
and a value next to it (to the right on the same line, or directly below), or
by its own structure (IBAN and VAT numbers with valid check digits). Every
value keeps the box it was read from and the evidence for it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from stdnum import iban as std_iban
from stdnum.eu import vat as std_vat

from . import vocab
from .layout import Line
from .model import Field, Source, VatRow
from .numbers import amounts_in, dates_in, fmt_amount, percents_in

ISO_CURRENCIES = ("EUR", "SEK", "DKK", "NOK", "PLN", "CZK", "HUF", "RON", "BGN", "CHF", "GBP", "USD", "ISK")
CURRENCY_SYMBOLS = {"€": "EUR", "£": "GBP", "zł": "PLN", "kč": "CZK", "ft": "HUF", "lei": "RON"}
IBAN_RE = re.compile(r"\b([A-Z]{2}\d{2}(?:[  ]?[A-Z0-9]{1,4}){3,8})\b")
VAT_RE = re.compile(
    r"(?<![A-Za-z0-9])(AT|BE|BG|CY|CZ|DE|DK|EE|EL|ES|FI|FR|HR|HU|IE|IT|LT|LU|LV|MT|NL|PL|PT|RO|SE|SI|SK|XI)"
    r"[  ]?([0-9A-Z](?:[  .]?[0-9A-Z]){5,13})(?![A-Za-z0-9])"
)


def norm_map(text: str) -> tuple[str, list[int]]:
    """``vocab.norm`` of each character, with a map from normalised to original index."""
    out: list[str] = []
    index: list[int] = []
    for i, ch in enumerate(text):
        n = vocab.norm(ch)
        out.append(n)
        index.extend([i] * len(n))
    index.append(len(text))
    return "".join(out), index


@dataclass
class Label:
    line: int
    start: int  # character offsets in the line's text
    end: int


class Doc:
    """Lines plus helpers to find labels and the values belonging to them."""

    def __init__(self, lines: list[Line], source: Source):
        self.lines = lines
        self.source = source
        self._norm = [norm_map(ln.text) for ln in lines]

    def find(self, words: tuple[str, ...]) -> list[Label]:
        rx = vocab.phrase_regex(words)
        out = []
        for i, (text, index) in enumerate(self._norm):
            for m in rx.finditer(text):
                out.append(Label(i, index[m.start()], index[m.end()]))
        return out

    def has(self, i: int, words: tuple[str, ...]) -> bool:
        return bool(vocab.phrase_regex(words).search(self._norm[i][0]))

    def right_of(self, lab: Label) -> tuple[int, int]:
        """Span of the text after a label on the same line, up to the next column gap."""
        text = self.lines[lab.line].text
        start = lab.end
        while start < len(text) and text[start] in " .:#°º-/|":
            start += 1
        gap = text.find("  ", start)
        return start, (gap if gap >= 0 else len(text))

    def below(self, lab: Label, max_lines: int = 2) -> list[tuple[int, int, int]]:
        """(line, start, end) of text directly under a label, for stacked layouts."""
        line = self.lines[lab.line]
        box = line.span_box(lab.start, lab.end)
        if box is None:
            return []
        out = []
        for j in range(lab.line + 1, min(lab.line + 1 + max_lines, len(self.lines))):
            nxt = self.lines[j]
            if nxt.page != line.page:
                break
            # The first word under the label, extended to the end of its column (the
            # next wide gap), so that narrow labels still get long values.
            first = next(
                (
                    sp
                    for w, sp in zip(nxt.words, nxt.spans, strict=True)
                    if w.box.x1 > box.x0 - 2 and w.box.x0 < box.x1 + 60
                ),
                None,
            )
            if first:
                gap = nxt.text.find("  ", first[0])
                out.append((j, first[0], gap if gap >= 0 else len(nxt.text)))
        return out

    def field(self, value: str, line: int, start: int, end: int, evidence: list[str], strong: bool) -> Field:
        ln = self.lines[line]
        conf = ln.span_confidence(start, end)
        confidence = "high" if strong and conf >= 0.9 else "medium" if strong or conf >= 0.9 else "low"
        if self.source == "ocr" and conf < 0.9:
            evidence = [*evidence, f"OCR confidence {conf:.0%}"]
        return Field(
            value=value,
            raw=ln.text[start:end],
            source=self.source,
            box=ln.span_box(start, end),
            confidence=confidence,  # type: ignore[arg-type]
            evidence=evidence,
        )


def _label_text(doc: Doc, lab: Label) -> str:
    return doc.lines[lab.line].text[lab.start : lab.end]


def _candidates(doc: Doc, words: tuple[str, ...]) -> list[tuple[Label, int, int, int]]:
    """(label, line, start, end) of the text to the right of, then below, each label."""
    out = []
    for lab in doc.find(words):
        s, e = doc.right_of(lab)
        if e > s:
            out.append((lab, lab.line, s, e))
        for j, s2, e2 in doc.below(lab):
            out.append((lab, j, s2, e2))
    return out


# "Rechnungskorrektur Nr. RK21012345", "Baurechnung Nr. 181301674", "Credit invoice no. 12"
TITLE_NUMBER_RE = re.compile(
    r"(?<![^\W\d_])[\w-]*(?:rechnung|gutschrift|invoice|lasku|faktura|facture|factuur|fattura|factura|fatura)[\w-]*"
    r"\s+(?:nr|no|nro|n°|nº|nummer|number|numero|#)\.?\s*:?\s*(\S*\d\S*)",
    re.IGNORECASE,
)


def invoice_number(doc: Doc) -> Field | None:
    for i, ln in enumerate(doc.lines):
        m = TITLE_NUMBER_RE.search(ln.text)
        if m and not dates_in(m.group(1)):
            token = m.group(1).rstrip(".,;:")
            return doc.field(
                token,
                i,
                m.start(1),
                m.start(1) + len(token),
                [f"“{m.group(0)[: m.start(1) - m.start()].strip()}”"],
                True,
            )
    for lab, i, s, e in _candidates(doc, vocab.INVOICE_NUMBER):
        text = doc.lines[i].text[s:e]
        m = re.match(r"\S*\d\S*", text.strip())
        if m:
            start = s + text.index(m.group(0))
            token = m.group(0).rstrip(".,;:")
            if dates_in(token):  # "Invoice date 05.03.2026" mis-read as a number label
                continue
            return doc.field(token, i, start, start + len(token), [f"label “{_label_text(doc, lab)}”"], True)
    return None


def _date(doc: Doc, words: tuple[str, ...]) -> Field | None:
    for lab, i, s, e in _candidates(doc, words):
        found = dates_in(doc.lines[i].text[s:e])
        if found:
            ds, de, d = found[0]
            return doc.field(d.isoformat(), i, s + ds, s + de, [f"label “{_label_text(doc, lab)}”"], True)
    return None


def issue_and_due(doc: Doc) -> tuple[Field | None, Field | None]:
    due = _date(doc, vocab.DUE_DATE)
    issue = None
    for lab, i, s, e in _candidates(doc, vocab.ISSUE_DATE):
        # "date" inside "due date", "datum" inside "Fälligkeitsdatum" ...
        before = vocab.norm(doc.lines[lab.line].text[max(0, lab.start - 12) : lab.end])
        if vocab.phrase_regex(vocab.DUE_DATE).search(before):
            continue
        found = dates_in(doc.lines[i].text[s:e])
        if found:
            ds, de, d = found[0]
            if due and due.value == d.isoformat() and due.raw == doc.lines[i].text[s + ds : s + de]:
                continue
            issue = doc.field(d.isoformat(), i, s + ds, s + de, [f"label “{_label_text(doc, lab)}”"], True)
            break
    if issue is None:
        # "Rechnung Nr. 471102 vom 05.03.2018", "Invoice # 12 issued at 2020-11-21"
        rx = vocab.phrase_regex(vocab.ISSUED_ON)
        for lab in doc.find(vocab.INVOICE_NUMBER):
            text = doc.lines[lab.line].text
            for s, e, d in dates_in(text[lab.end :]):
                before = vocab.norm(text[lab.end : lab.end + s])
                if rx.search(before[-14:]):
                    issue = doc.field(d.isoformat(), lab.line, lab.end + s, lab.end + e,
                                      ["date given with the invoice number"], True)  # fmt: skip
                    break
            if issue:
                break
    if issue is None:
        # The earliest date on the first page, without a label: a weak guess, shown as such.
        dated = [
            (d, i, s, e) for i, ln in enumerate(doc.lines) if ln.page == 0 for s, e, d in dates_in(ln.text)
        ]
        dated = [x for x in dated if not (due and due.value == x[0].isoformat())]
        if dated:
            d, i, s, e = min(dated, key=lambda x: x[0])
            issue = doc.field(
                d.isoformat(), i, s, e, ["earliest date on the first page (no label found)"], False
            )
            issue.confidence = "low"
    return issue, due


def _labelled_spans(doc: Doc, words: tuple[str, ...]) -> dict[int, list[tuple[int, int]]]:
    """Line -> character spans that sit right of, or directly below, a label."""
    out: dict[int, list[tuple[int, int]]] = {}
    for lab in doc.find(words):
        s, e = doc.right_of(lab)
        if e > s:
            out.setdefault(lab.line, []).append((s, e))
        for j, s2, e2 in doc.below(lab, max_lines=1):
            out.setdefault(j, []).append((s2, e2))
    return out


def _in_spans(spans: list[tuple[int, int]] | None, start: int, end: int) -> bool:
    return bool(spans) and any(s <= start < e or s < end <= e for s, e in spans)  # type: ignore[union-attr]


def _vat_ids(doc: Doc) -> list[Field]:
    out: list[Field] = []
    seen = set()
    labelled_at = _labelled_spans(doc, vocab.VAT_ID)
    for i, ln in enumerate(doc.lines):
        for m in VAT_RE.finditer(ln.text):
            compact = m.group(1) + re.sub(r"[  .]", "", m.group(2))
            if compact in seen or len(compact) > 16:
                continue
            if IBAN_RE.fullmatch(re.sub(r"[  ]", "", m.group(0))) and std_iban.is_valid(compact):
                continue  # an IBAN
            valid = std_vat.is_valid(compact)
            labelled = _in_spans(labelled_at.get(i), m.start(), m.end())
            if not valid and not labelled:
                continue
            evidence = ["check digits valid" if valid else "check digits do NOT match"]
            if labelled:
                evidence.append("label nearby")
            f = doc.field(compact, i, m.start(), m.end(), evidence, valid)
            if not valid:
                f.confidence = "low"
            seen.add(compact)
            out.append(f)
    return out


def ibans(doc: Doc) -> list[Field]:
    out = []
    labelled_at = _labelled_spans(doc, vocab.IBAN)
    for i, ln in enumerate(doc.lines):
        for m in IBAN_RE.finditer(ln.text):
            compact = re.sub(r"[  ]", "", m.group(1))
            if not 15 <= len(compact) <= 34:
                continue
            valid = std_iban.is_valid(compact)
            if not valid and not _in_spans(labelled_at.get(i), m.start(1), m.end(1)):
                continue
            f = doc.field(compact, i, m.start(1), m.end(1),
                          ["IBAN check digits valid" if valid else "IBAN check digits do NOT match"], valid)  # fmt: skip
            if not valid:
                f.confidence = "low"
            out.append(f)
    return out


def _is_company(text: str) -> bool:
    # "N.V.", "S.p.A.", "sp. z o.o." -> "n v", "s p a", "sp z o o"
    t = re.sub(r"[.\s]+", " ", vocab.norm(text.split(",")[0])).strip(" ,")
    return len(t) < 80 and any(t.endswith(" " + lf) for lf in vocab.LEGAL_FORMS)


def _company_span(text: str) -> tuple[int, int] | None:
    """The company name in a line: text up to and including its legal form."""
    head = text.split(",")[0]
    for seg_start in [0, *[m.end() for m in re.finditer(r" {2,}|: ?", head)]]:
        seg = head[seg_start:]
        gap = seg.find("  ")
        seg = seg[:gap] if gap >= 0 else seg
        if _is_company(seg):
            return seg_start, seg_start + len(seg.rstrip(" ,"))
    return None


def _company_near(doc: Doc, lab: Label) -> Field | None:
    """A company name right of the label, or in the column directly below it."""
    s, e = doc.right_of(lab)
    places = ([(lab.line, s, e)] if e > s else []) + doc.below(lab, max_lines=3)
    for i, a, b in places:
        sp = _company_span(doc.lines[i].text[a:b])
        if sp is None:
            seg = doc.lines[i].text[a:b]
            words = set(re.sub(r"[.\s]+", " ", vocab.norm(seg)).split())
            # Under a party label a legal form may sit mid-name ("Kunden AG Mitte").
            if ":" not in seg and len(seg) < 60 and words & {lf for lf in vocab.LEGAL_FORMS if " " not in lf}:
                sp = (0, len(seg.rstrip(" ,")))
        if sp:
            start, end = a + sp[0], a + sp[1]
            name = doc.lines[i].text[start:end].strip()
            return doc.field(name, i, start, end, [f"under/after “{_label_text(doc, lab)}”"], True)
    return None


ADDRESS_LINE = re.compile(
    r"\d|@|https?:|\bstr\b|stra(ss|ß)e|tie\b|katu\b|gatan\b|vej\b|weg\b|rue\b|via\b|calle\b", re.I
)


def _name_below(doc: Doc, lab: Label) -> Field | None:
    """First plausible name line under a label: a person or an organisation without a legal form."""
    for i, a, b in doc.below(lab, max_lines=3):
        text = doc.lines[i].text[a:b].strip()
        whole = doc.lines[i].text
        if len(text) < 3 or ":" in whole or ADDRESS_LINE.search(whole) or not re.search(r"[^\W\d_]{2}", text):
            continue
        if doc.find(vocab.BUYER + vocab.SELLER) and any(
            lb.line == i for lb in doc.find(vocab.BUYER + vocab.SELLER)
        ):
            continue
        f = doc.field(
            text,
            i,
            a,
            a + len(doc.lines[i].text[a:b].rstrip()),
            [f"line under “{_label_text(doc, lab)}”"],
            False,
        )
        f.confidence = "medium"
        return f
    return None


def parties(doc: Doc) -> tuple[Field | None, Field | None]:
    buyer = next((f for f in (_company_near(doc, lab) for lab in doc.find(vocab.BUYER)) if f), None)
    if buyer is None:
        buyer = next((f for f in (_name_below(doc, lab) for lab in doc.find(vocab.BUYER)) if f), None)
    seller = None
    for lab in doc.find(vocab.SELLER):
        f = _company_near(doc, lab)
        if f and (not buyer or f.value != buyer.value):
            seller = f
            break
    if seller is None:
        for i, ln in enumerate(doc.lines):
            sp = _company_span(ln.text)
            if not sp:
                continue
            a, b = sp
            name = ln.text[a:b].strip()
            name = re.sub(rf"^(?:{'|'.join(map(re.escape, vocab.TITLE))})\s+", "", name, flags=re.I)
            if buyer and name == buyer.value:
                continue
            seller = doc.field(name, i, a, b, ["first company name on the document (no seller label)"], False)
            seller.confidence = "medium" if ln.page == 0 and i < 8 else "low"
            break
    return seller, buyer


def currency(doc: Doc) -> Field | None:
    for i, ln in enumerate(doc.lines):
        for code in ISO_CURRENCIES:
            m = re.search(rf"(?<![A-Z]){code}(?![A-Z])", ln.text)
            if m:
                return doc.field(code, i, m.start(), m.end(), ["currency code printed"], True)
    for i, ln in enumerate(doc.lines):
        low = ln.text.casefold()
        for sym, code in CURRENCY_SYMBOLS.items():
            # Alphabetic symbols ("lei", "ft") must be whole words, not part of "Leistung".
            m = re.search(rf"(?<![^\W\d_]){re.escape(sym)}(?![^\W\d_])", low) if sym.isalpha() else None
            j = (m.start() if m else -1) if sym.isalpha() else low.find(sym)
            if j >= 0 and amounts_in(ln.text):
                return doc.field(code, i, j, j + len(sym), [f"symbol “{sym}” next to amounts"], True)
        m = re.search(r"\d\s?kr\.?(?!\w)", low)
        if m:
            return doc.field("SEK", i, m.start(), m.end(), ["“kr” could be SEK, DKK or NOK — check"], False)
    return None


@dataclass
class Totals:
    net: Field | None
    vat: Field | None
    total: Field | None
    breakdown: list[VatRow]


def _amount_field(doc: Doc, i: int, which: int, evidence: list[str]) -> Field | None:
    found = amounts_in(doc.lines[i].text)
    if not found:
        return None
    s, e, v = found[which]
    return doc.field(fmt_amount(v), i, s, e, evidence, True)


def totals(doc: Doc) -> Totals:
    net = vat = total = None
    breakdown: list[VatRow] = []
    vat_lines = []
    vat_total = None
    totals_found: list[tuple[int, Field, bool]] = []
    for i, ln in enumerate(doc.lines):
        has_amount = bool(amounts_in(ln.text))
        if not has_amount:
            continue
        including = doc.has(i, vocab.INCLUDING)
        is_net = doc.has(i, vocab.NET) and not including
        is_vat = doc.has(i, vocab.VAT) and not is_net and not including
        is_total = doc.has(i, vocab.TOTAL) and not is_net
        if is_net:
            net = _amount_field(doc, i, -1, ["net / subtotal label"])
        elif is_vat and not percents_in(ln.text) and (is_total or len(amounts_in(ln.text)) == 1):
            # "VAT total 75.04", "Steuerbetrag 37,62": one VAT amount without a rate is the VAT total;
            # rows of a VAT breakdown carry a rate and usually the taxable amount.
            vat_total = _amount_field(doc, i, -1, ["VAT total label"])
        elif is_vat and (percents_in(ln.text) or not is_total):
            vat_lines.append(i)
        elif is_total:
            f = _amount_field(doc, i, -1, ["total label"])
            if f is not None:
                totals_found.append((i, f, doc.has(i, vocab.TOTAL_DUE) and not doc.has(i, vocab.TOTAL_GROSS)))
    # Keep only VAT lines after the item table area: they follow the net line when there is one.
    if net is not None:
        vat_lines = [i for i in vat_lines if net.box and doc.lines[i].page >= net.box.page]
    for i in vat_lines:
        ln = doc.lines[i]
        amounts = amounts_in(ln.text)
        pcts = percents_in(ln.text)
        s, e, value = amounts[-1]
        rate = Field(f"{pcts[0][2].normalize():f}", ln.text[pcts[0][0] : pcts[0][1]], doc.source,
                     ln.span_box(pcts[0][0], pcts[0][1]), "high") if pcts else Field(None)  # fmt: skip
        base = (
            doc.field(fmt_amount(amounts[0][2]), i, amounts[0][0], amounts[0][1], ["VAT line"], True)
            if len(amounts) >= 2
            else Field(None)
        )
        breakdown.append(VatRow(rate, base, doc.field(fmt_amount(value), i, s, e, ["VAT line"], True)))
    total = _choose_total(totals_found, net, vat_total, breakdown)
    if vat_total is not None:
        vat = vat_total
    elif len(breakdown) == 1:
        vat = breakdown[0].vat
    elif len(breakdown) > 1:
        values = [Decimal(r.vat.value) for r in breakdown if r.vat.value]
        vat = Field(
            fmt_amount(sum(values, Decimal(0))),
            None,
            doc.source,
            None,
            "medium",
            [f"sum of {len(values)} VAT lines ({' + '.join(fmt_amount(v) for v in values)})"],
        )
    return Totals(net, vat, total, breakdown)


def _assign_vat_ids(
    vats: list[Field], seller: Field | None, buyer: Field | None
) -> tuple[Field | None, Field | None]:
    """Give each VAT number to the party whose name is printed nearest above it.

    Seller and buyer blocks are often side by side, so distance counts in both
    directions; a VAT number belongs to a block when it is below the name.
    """

    def dist(v: Field, party: Field | None) -> float:
        if party is None or party.box is None or v.box is None or v.box.page != party.box.page:
            return float("inf")
        dy = v.box.y0 - party.box.y0
        if dy < -2:  # above the name: not in its block
            return float("inf")
        return dy + 2 * abs(v.box.x0 - party.box.x0)

    seller_vat = buyer_vat = None
    for v in vats:
        ds, db = dist(v, seller), dist(v, buyer)
        if db < ds and buyer_vat is None:
            buyer_vat = v
        elif ds <= db and ds != float("inf") and seller_vat is None:
            seller_vat = v
    # Fall back to reading order: the seller's number usually comes first.
    rest = [v for v in vats if v is not seller_vat and v is not buyer_vat]
    if seller_vat is None and rest:
        seller_vat = rest.pop(0)
    if buyer_vat is None and rest:
        buyer_vat = rest.pop(0)
    return seller_vat, buyer_vat


def _choose_total(found: list[tuple[int, Field, bool]], net: Field | None, vat_total: Field | None,
                  rows: list[VatRow]) -> Field | None:  # fmt: skip
    """The invoice total: the candidate equal to net + VAT if any, else the last gross total, else the last one.

    An "amount due" can be lower than the invoice total (prepayments, credits),
    so a gross total label ("Rechnungsbetrag", "Total incl. VAT") is preferred.
    """
    if not found:
        return None
    vat_value = vat_total.value if vat_total is not None else None
    if vat_value is None and rows and all(r.vat.value for r in rows):
        vat_value = fmt_amount(sum((Decimal(r.vat.value) for r in rows if r.vat.value), Decimal(0)))
    if net is not None and net.value and vat_value:
        expected = Decimal(net.value) + Decimal(vat_value)
        for _, f, _ in reversed(found):
            if f.value and abs(Decimal(f.value) - expected) <= Decimal("0.02"):
                return f
    gross = [f for _, f, due in found if not due]
    return gross[-1] if gross else found[-1][1]


def extract_fields(doc: Doc) -> tuple[dict[str, Field | None], list[VatRow]]:
    issue, due = issue_and_due(doc)
    vats = _vat_ids(doc)
    seller, buyer = parties(doc)
    iban_fields = ibans(doc)
    t = totals(doc)
    seller_vat, buyer_vat = _assign_vat_ids(vats, seller, buyer)
    fields: dict[str, Field | None] = {
        "invoice_number": invoice_number(doc),
        "issue_date": issue,
        "due_date": due,
        "currency": currency(doc),
        "seller_name": seller,
        "seller_vat_id": seller_vat,
        "buyer_name": buyer,
        "buyer_vat_id": buyer_vat,
        "iban": iban_fields[0] if iban_fields else None,
        "net_amount": t.net,
        "vat_amount": t.vat,
        "total_amount": t.total,
    }
    return fields, t.breakdown
