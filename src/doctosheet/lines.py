"""Line items from a table with a header row.

The header is a line with at least three recognised column labels (description,
quantity, unit, unit price, VAT rate, amount) in any supported language. Column
boundaries are the midpoints between header labels; each following line is
split into columns by word position until the totals block starts. A row is
trusted when quantity × unit price equals its amount.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise

from . import vocab
from .fields import Doc, norm_map
from .layout import Line
from .model import Box, Field, LineItem
from .numbers import amounts_in, fmt_amount, parse_amount, parse_quantity, percents_in

NUMERIC = ("quantity", "unit_price", "vat_rate", "amount")


@dataclass
class Column:
    kind: str
    x0: float  # header label extent
    x1: float
    left: float = 0.0  # assignment range
    right: float = 0.0


def _header_columns(line: Line) -> list[Column] | None:
    text, index = norm_map(line.text)
    found: list[tuple[int, int, str]] = []
    for kind, words in vocab.COLUMNS.items():
        for m in vocab.phrase_regex(words).finditer(text):
            found.append((index[m.start()], index[m.end()], kind))
    # Longest, leftmost matches win; one column per kind.
    found.sort(key=lambda f: (-(f[1] - f[0]), f[0]))
    taken: list[tuple[int, int, str]] = []
    for f in found:
        if all(f[1] <= t[0] or f[0] >= t[1] for t in taken) and f[2] not in {t[2] for t in taken}:
            taken.append(f)
    kinds = {t[2] for t in taken}
    if (
        len(taken) < 3
        or not ({"description", "amount"} & kinds)
        or not ({"quantity", "unit_price", "amount"} & kinds)
    ):
        return None
    if any(amounts_in(line.text)):  # a header has no amounts
        return None
    cols = []
    for s, e, kind in sorted(taken):
        box = line.span_box(s, e)
        if box:
            cols.append(Column(kind, box.x0, box.x1))
    cols.sort(key=lambda c: c.x0)
    for a, b in pairwise(cols):
        # Numbers are usually right-aligned under their label, text left-aligned:
        # split between a column's label end and the next label's start.
        mid = (a.x1 + b.x0) / 2
        a.right, b.left = mid, mid
    cols[0].left = -1e9
    cols[-1].right = 1e9
    return cols


def _is_totals(doc: Doc, i: int) -> bool:
    return doc.has(i, vocab.NET) or (doc.has(i, vocab.TOTAL) and not doc.has(i, vocab.COLUMNS["description"]))


def _cell(line: Line, col: Column) -> tuple[str, int, int] | None:
    words = line.words_in(col.left, col.right)
    if not words:
        return None
    s, e = words[0][1][0], words[-1][1][1]
    return line.text[s:e], s, e


def extract_lines(doc: Doc) -> list[LineItem]:
    items = _table_lines(doc)
    return items if items else _receipt_lines(doc)


def _table_lines(doc: Doc) -> list[LineItem]:
    items: list[LineItem] = []
    i = 0
    while i < len(doc.lines):
        cols = _header_columns(doc.lines[i])
        if cols is None:
            i += 1
            continue
        page = doc.lines[i].page
        j = i + 1
        while j < len(doc.lines) and doc.lines[j].page == page and not _is_totals(doc, j):
            row = _row(doc, j, cols)
            if row is not None:
                items.append(row)
            elif items and not amounts_in(doc.lines[j].text) and len(doc.lines[j].text) < 120:
                # A wrapped description line belongs to the item above.
                _continue_description(items[-1], doc.lines[j])
            elif not amounts_in(doc.lines[j].text):
                pass
            j += 1
        i = j
    return items


def _field(doc: Doc, line_idx: int, value: str | None, s: int, e: int, evidence: list[str]) -> Field:
    if value is None:
        return Field(None)
    f = doc.field(value, line_idx, s, e, evidence, True)
    return f


def _row(doc: Doc, idx: int, cols: list[Column]) -> LineItem | None:
    line = doc.lines[idx]
    cells = {c.kind: _cell(line, c) for c in cols}
    amount_cell = cells.get("amount")
    amount = parse_amount(amount_cell[0]) if amount_cell else None
    if amount is None:
        # the amount is usually the last number of the row
        found = amounts_in(line.text)
        if not found:
            return None
        s, e, amount = found[-1]
        amount_cell = (line.text[s:e], s, e)
    assert amount_cell is not None
    out: dict[str, Field] = {}
    out["amount"] = _field(doc, idx, fmt_amount(amount), amount_cell[1], amount_cell[2], [])
    q = cells.get("quantity")
    qty = parse_quantity(q[0].split()[0]) if q and q[0].split() else None
    out["quantity"] = (
        _field(doc, idx, None if qty is None else f"{qty.normalize():f}", q[1], q[2], [])
        if q
        else Field(None)
    )
    p = cells.get("unit_price")
    price = parse_amount(p[0]) if p else None
    out["unit_price"] = (
        _field(doc, idx, fmt_amount(price) if price is not None else None, p[1], p[2], [])
        if p
        else Field(None)
    )
    v = cells.get("vat_rate")
    pct = percents_in(v[0]) if v else []
    if v and pct:
        out["vat_rate"] = _field(
            doc, idx, f"{pct[0][2].normalize():f}", v[1] + pct[0][0], v[1] + pct[0][1], []
        )
    else:
        out["vat_rate"] = Field(None)
    u = cells.get("unit")
    out["unit"] = (
        _field(doc, idx, u[0].strip(), u[1], u[2], [])
        if u and not any(ch.isdigit() for ch in u[0])
        else Field(None)
    )
    d = cells.get("description")
    if d:
        desc = d[0].strip()
        out["description"] = _field(doc, idx, desc, d[1], d[2], [])
    else:
        # everything left of the first numeric column
        first_num = min((c.left for c in cols if c.kind in NUMERIC), default=1e9)
        words = line.words_in(-1e9, first_num)
        if words:
            s, e = words[0][1][0], words[-1][1][1]
            out["description"] = _field(doc, idx, line.text[s:e].strip(), s, e, [])
        else:
            out["description"] = Field(None)
    if not out["description"].value or not any(ch.isalpha() for ch in out["description"].value):
        return None
    _cross_check(out)
    return LineItem(
        out["description"],
        out["quantity"],
        out["unit"],
        out["unit_price"],
        out["vat_rate"],
        out["amount"],
        line.box,
    )


def _cross_check(out: dict[str, Field]) -> None:
    q, p, a = out["quantity"].value, out["unit_price"].value, out["amount"].value
    if q and p and a:
        expected = Decimal(q) * Decimal(p)
        ok = abs(expected - Decimal(a)) <= max(Decimal("0.02"), abs(Decimal(a)) * Decimal("0.001"))
        note = f"quantity × unit price = {fmt_amount(expected)}"
        for k in ("quantity", "unit_price", "amount"):
            out[k].evidence.append(note + (" ✓" if ok else f" ≠ {a}"))
            if ok:
                out[k].confidence = "high"
            else:
                out[k].confidence = "low"


def _continue_description(item: LineItem, line: Line) -> None:
    d = item.description
    if d.value is None:
        return
    d.value = f"{d.value} {line.text.strip()}"
    d.raw = d.value
    if d.box and line.box.page == d.box.page:
        d.box = Box.union([d.box, line.box])


# Receipt-style items without a table header:
#   "2 x Coffee à 3,50   7,00"     "Coffee  2 x 3,50   7,00"
#   "Coffee" on one line and "2 x 3,50   7,00" on the next.
# A row is accepted only when quantity × price equals the amount, so text that
# merely looks similar cannot produce items.
QTY_X = re.compile(r"(?<![\d.,])(\d{1,6}(?:[.,]\d{1,3})?)\s*[x×*]\s", re.IGNORECASE)


def _receipt_lines(doc: Doc) -> list[LineItem]:
    items: list[LineItem] = []
    for i, line in enumerate(doc.lines):
        if _is_totals(doc, i):
            continue
        amounts = amounts_in(line.text)
        q = QTY_X.search(line.text)
        if len(amounts) < 2 or not q:
            continue
        (ps, pe, price), (as_, ae, amount) = amounts[-2], amounts[-1]
        qty = parse_quantity(q.group(1))
        if qty is None or q.end() > ps:
            continue
        if abs(qty * price - amount) > max(Decimal("0.02"), abs(amount) * Decimal("0.001")):
            continue
        # description: text between "2 x" and the price, or before the quantity,
        # or the previous line when this line has nothing else
        between = line.text[q.end() : ps].strip(" \t·-–@").removesuffix(" à").removesuffix(" a").strip()
        before = line.text[: q.start()].strip(" \t·-–")
        if re.search(r"[^\W\d_]", between):
            desc_idx, ds = i, line.text.index(between, q.end())
            desc_text = between
        elif re.search(r"[^\W\d_]", before):
            desc_idx, ds, desc_text = i, line.text.index(before), before
        elif (
            i > 0 and not amounts_in(doc.lines[i - 1].text) and re.search(r"[^\W\d_]", doc.lines[i - 1].text)
        ):
            desc_idx, ds, desc_text = i - 1, 0, doc.lines[i - 1].text.strip()
        else:
            continue
        evidence = [f"quantity × price = {fmt_amount(qty * price)} ✓"]
        desc = doc.field(desc_text, desc_idx, ds, ds + len(desc_text), [], True)
        items.append(
            LineItem(
                desc,
                doc.field(f"{qty.normalize():f}", i, q.start(1), q.end(1), list(evidence), True),
                Field(None),
                doc.field(fmt_amount(price), i, ps, pe, list(evidence), True),
                Field(None),
                doc.field(fmt_amount(amount), i, as_, ae, list(evidence), True),
                Box.union([b for b in (doc.lines[desc_idx].box, line.box) if b.page == line.page]),
            )
        )
    return items
