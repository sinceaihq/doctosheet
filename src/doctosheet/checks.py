"""Consistency checks. They raise or lower confidence; they never change values.

A missing amount is not filled in: if, say, the total is not printed but net
and VAT are, the computed total is offered as a suggestion (Field.computed)
that the user has to accept explicitly.
"""

from __future__ import annotations

from decimal import Decimal

from .model import Check, Field, LineItem, VatRow
from .numbers import fmt_amount

TOLERANCE = Decimal("0.02")


def _d(f: Field | None) -> Decimal | None:
    if f is None or f.value is None or f.computed:
        return None
    try:
        return Decimal(f.value)
    except Exception:
        return None


def _close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCE


def _confirm(fields: list[Field | None], note: str) -> None:
    for f in fields:
        if f is not None and f.value is not None:
            f.evidence.append(note)
            if f.source in ("text", "xml") or f.confidence == "medium":
                f.confidence = "high"


def _doubt(fields: list[Field | None], note: str) -> None:
    for f in fields:
        if f is not None and f.value is not None:
            f.evidence.append(note)
            f.confidence = "low"


def run_checks(fields: dict[str, Field], lines: list[LineItem], vat_rows: list[VatRow]) -> list[Check]:
    checks: list[Check] = []
    net, vat, total = (_d(fields.get(k)) for k in ("net_amount", "vat_amount", "total_amount"))
    nf, vf, tf = fields.get("net_amount"), fields.get("vat_amount"), fields.get("total_amount")

    if net is not None and vat is not None and total is not None:
        ok = _close(net + vat, total)
        detail = f"{fmt_amount(net)} + {fmt_amount(vat)} = {fmt_amount(net + vat)}" + (
            "" if ok else f", but the total reads {fmt_amount(total)}"
        )
        checks.append(Check("net + VAT = total", "ok" if ok else "failed", detail))
        (_confirm if ok else _doubt)([nf, vf, tf], ("✓ " if ok else "✗ ") + "net + VAT = total")
    else:
        checks.append(Check("net + VAT = total", "not_applicable", "not all three amounts were found"))
        # Offer, never fill: a computed value is a suggestion the user must accept.
        missing = [k for k, v in (("net_amount", net), ("vat_amount", vat), ("total_amount", total)) if v is None]
        if len(missing) == 1:
            k = missing[0]
            value = (
                total - vat if k == "net_amount" and total is not None and vat is not None
                else total - net if k == "vat_amount" and total is not None and net is not None
                else net + vat if k == "total_amount" and net is not None and vat is not None
                else None
            )  # fmt: skip
            if value is not None:
                fields[k] = Field(
                    fmt_amount(value), None, "computed", None, "low",
                    ["not printed on the document; computed from the other two amounts — accept only if correct"],
                    computed=True,
                )  # fmt: skip

    if vat_rows and vat is not None:
        rows = [_d(r.vat) for r in vat_rows]
        if all(r is not None for r in rows) and len(rows) > 1:
            s = sum((r for r in rows if r is not None), Decimal(0))
            checks.append(Check("VAT lines add up", "ok" if _close(s, vat) else "failed",
                                f"{' + '.join(fmt_amount(r) for r in rows if r is not None)} = {fmt_amount(s)}"))  # fmt: skip
    for r in vat_rows:
        rate, base, amount = _d(r.rate), _d(r.base), _d(r.vat)
        if rate is not None and base is not None and amount is not None:
            expected = (base * rate / 100).quantize(Decimal("0.01"))
            ok = _close(expected, amount)
            checks.append(Check(f"VAT {rate.normalize():f} % of {fmt_amount(base)}", "ok" if ok else "failed",
                                f"expected {fmt_amount(expected)}, printed {fmt_amount(amount)}"))  # fmt: skip
            (_confirm if ok else _doubt)([r.base, r.vat], ("✓ " if ok else "✗ ") + "rate × base = VAT")

    amounts = [_d(li.amount) for li in lines]
    if lines and all(a is not None for a in amounts):
        s = sum((a for a in amounts if a is not None), Decimal(0))
        if net is not None:
            ok = _close(s, net)
            checks.append(Check("line items add up to the net amount", "ok" if ok else "failed",
                                f"{len(lines)} lines sum to {fmt_amount(s)}; net reads {fmt_amount(net)}"))  # fmt: skip
            if ok:
                _confirm([li.amount for li in lines] + [nf], "✓ lines sum to net")
        elif total is not None:
            ok = _close(s, total)
            checks.append(Check("line items add up to the total", "ok" if ok else "failed",
                                f"{len(lines)} lines sum to {fmt_amount(s)}; total reads {fmt_amount(total)}"))  # fmt: skip

    issue, due = fields.get("issue_date"), fields.get("due_date")
    if issue and due and issue.value and due.value:
        ok = due.value >= issue.value
        checks.append(Check("due date after invoice date", "ok" if ok else "failed", f"{issue.value} → {due.value}"))
        if not ok:
            _doubt([issue, due], "✗ due date is before the invoice date")

    for k in ("iban", "seller_vat_id", "buyer_vat_id"):
        f = fields.get(k)
        if f and f.value and f.source != "xml":
            valid = any("valid" in e and "NOT" not in e for e in f.evidence)
            checks.append(Check(f"{k.replace('_', ' ')} check digits", "ok" if valid else "failed", f.value))
    return checks
