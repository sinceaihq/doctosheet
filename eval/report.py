"""Fill the result tables in README.md and docs/EVALUATION.md from eval/results/*/summary.json.

python eval/report.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "eval" / "results"
LABELS = {
    "invoice_number": "invoice number", "issue_date": "invoice date", "due_date": "due date", "currency": "currency",
    "seller_name": "seller", "seller_vat_id": "seller VAT no.", "buyer_name": "buyer", "buyer_vat_id": "buyer VAT no.",
    "iban": "IBAN", "net_amount": "net amount", "vat_amount": "VAT amount", "total_amount": "total amount",
}  # fmt: skip


def load(name: str) -> dict | None:
    p = RES / name / "summary.json"
    return json.loads(p.read_text()) if p.exists() else None


def pct(x: float | None) -> str:
    return "—" if x is None else f"{100 * x:.1f}"


def acc(v: object) -> float | None:
    return v["accuracy"] if isinstance(v, dict) else v  # type: ignore[index,return-value]


def zugferd_table() -> str:
    t, o = load("zugferd-test-text"), load("zugferd-test-ocr")
    if t is None:
        return "_not yet measured_"
    rows = [
        "| field | printed PDF (text layer) | same pages as images (OCR) | invoices with this field |",
        "|---|---|---|---|",
    ]
    for k, label in LABELS.items():
        n = t["per_field"][k]["n"]
        rows.append(
            f"| {label} | {pct(acc(t['per_field'][k]))} | {pct(acc(o['per_field'][k])) if o else '—'} | {n} |"
        )
    rows.append(
        f"| **all fields** | **{pct(t['field_accuracy'])}** | **{pct(o['field_accuracy']) if o else '—'}** | |"
    )
    hi_t, hi_o = t["confidence_calibration"]["high"], (o or {}).get("confidence_calibration", {}).get("high")
    ocr_cell = f"{pct(hi_o['correct'])} (of {hi_o['n']})" if hi_o else "—"
    rows.append(
        f"| values marked ✓ that were correct | {pct(hi_t['correct'])} (of {hi_t['n']}) | {ocr_cell} | |"
    )
    return "\n".join(rows)


def edb_table() -> str:
    t, s = load("edb-test-text"), load("edb-test-scan")
    if t is None:
        return "_not yet measured_"
    rows = [
        "| | text PDFs | simulated scans (OCR) | previous best on the scans |",
        "|---|---|---|---|",
        f"| fields correct | {pct(t['field_accuracy'])} | {pct(s['field_accuracy']) if s else '—'} | 67.3 (EasyOCR → Qwen2.5-1.5B) |",
        f"| invoices with all 12 fields correct | {pct(t['document_accuracy'])} | {pct(s['document_accuracy']) if s else '—'} | 4.3 |",
        f"| values marked ✓ that were correct | {pct(t['confidence_calibration']['high']['correct'])} | "
        f"{pct(s['confidence_calibration']['high']['correct']) if s else '—'} | — |",
        f"| line items: invoices with the right number of rows | {pct(t['lines']['line_count_correct'])} | "
        f"{pct(s['lines']['line_count_correct']) if s else '—'} | — |",
        f"| line items: amounts correct | {pct(t['lines']['cell_accuracy']['amount'])} | "
        f"{pct(s['lines']['cell_accuracy']['amount']) if s else '—'} | — |",
        f"| seconds per invoice (one process) | {t['seconds_per_document']} | {s['seconds_per_document'] if s else '—'} | — |",
    ]  # fmt: skip
    return "\n".join(rows)


def per_field_edb() -> str:
    t, s = load("edb-test-text"), load("edb-test-scan")
    if t is None:
        return "_not yet measured_"
    rows = ["| field | text PDFs | simulated scans |", "|---|---|---|"]
    for k, label in LABELS.items():
        rows.append(f"| {label} | {pct(t['per_field'][k])} | {pct(s['per_field'][k]) if s else '—'} |")
    return "\n".join(rows)


def dev_table() -> str:
    rows = ["| set | fields correct | ✓ correct |", "|---|---|---|"]
    for name, label in [("edb-dev-text", "EuroDocBench dev, text"), ("edb-dev-scan", "EuroDocBench dev, scans"),
                        ("zugferd-dev-text", "ZUGFeRD dev producers, text"), ("zugferd-dev-ocr", "ZUGFeRD dev producers, OCR")]:  # fmt: skip
        r = load(name)
        if r:
            rows.append(
                f"| {label} | {pct(r['field_accuracy'])} | {pct(r['confidence_calibration']['high']['correct'])} |"
            )
    return "\n".join(rows)


def fill(path: Path, blocks: dict[str, str]) -> None:
    text = path.read_text()
    for key, content in blocks.items():
        text = re.sub(rf"<!-- {key}:start -->.*?<!-- {key}:end -->", f"<!-- {key}:start -->\n{content}\n<!-- {key}:end -->",
                      text, flags=re.S)  # fmt: skip
    path.write_text(text)


if __name__ == "__main__":
    blocks = {
        "zugferd": zugferd_table(),
        "edb": edb_table(),
        "edb-fields": per_field_edb(),
        "dev": dev_table(),
    }
    fill(ROOT / "README.md", blocks)
    fill(ROOT / "docs" / "EVALUATION.md", blocks)
    print("updated README.md and docs/EVALUATION.md")
