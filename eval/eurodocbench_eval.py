"""Evaluate DocToSheet on EuroDocBench (https://huggingface.co/datasets/sinceaihq/eurodocbench).

    python eval/eurodocbench_eval.py --data path/to/eurodocbench --split dev --track text --out eval/results/edb-dev-text

The text track gives DocToSheet the original PDF (it reads the text layer
itself); the scan track gives it the degraded page image (OCR). Header
fields are scored with EuroDocBench's own scorer; line items and VAT rows
with exact matching after normalisation. Computed suggestions count as empty.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq

from doctosheet import extract


def _run(job: tuple[str, bytes, str]) -> dict:
    doc_id, data, name = job
    t0 = time.perf_counter()
    try:
        r = extract(data, name)
    except Exception as exc:  # report, do not crash the evaluation
        return {"id": doc_id, "error": f"{type(exc).__name__}: {exc}", "seconds": time.perf_counter() - t0}
    return {
        "id": doc_id,
        "seconds": time.perf_counter() - t0,
        "method": r.method,
        "fields": {k: (None if f.computed else f.value) for k, f in r.fields.items()},
        "confidence": {
            k: f.confidence for k, f in r.fields.items() if f.value is not None and not f.computed
        },
        "lines": [
            {
                "description": li.description.value,
                "quantity": li.quantity.value,
                "unit_price": li.unit_price.value,
                "vat_rate": li.vat_rate.value,
                "amount": li.amount.value,
            }
            for li in r.lines
        ],
        "vat_breakdown": [
            {"rate": v.rate.value, "base": v.base.value, "vat": v.vat.value} for v in r.vat_breakdown
        ],
        "checks": [c.status for c in r.checks if c.name == "net + VAT = total"],
    }


def _num(x: str | None) -> Decimal | None:
    try:
        return None if x is None else Decimal(x)
    except Exception:
        return None


def _rate_printed(row: dict, line: dict) -> bool:
    """Is a VAT rate printed on the text line of this item? (Many layouts omit it.)"""
    for text_line in row["text"].splitlines():
        if line["description"] in text_line:
            return "%" in text_line
    return False


def line_scores(gold_rows: list[dict], preds: list[dict]) -> dict:
    keys = ("description", "quantity", "unit_price", "vat_rate", "amount")
    correct = {k: 0 for k in keys}
    rate_printed = rate_printed_ok = 0
    total = exact_docs = count_ok = 0
    for g, p in zip(gold_rows, preds, strict=True):
        gl, pl = g["lines"], p.get("lines", [])
        count_ok += len(gl) == len(pl)
        doc_ok = len(gl) == len(pl)
        for i, gi in enumerate(gl):
            total += 1
            pi = pl[i] if i < len(pl) else {}
            for k in keys:
                if k == "description":
                    ok = (pi.get(k) or "").strip() == gi[k].strip()
                else:
                    ok = _num(pi.get(k)) is not None and _num(pi.get(k)) == _num(gi[k])
                correct[k] += ok
                if k == "vat_rate" and _rate_printed(g, gi):
                    rate_printed += 1
                    rate_printed_ok += ok
                # Many layouts do not print a per-line VAT rate; it is scored per cell only.
                if k != "vat_rate":
                    doc_ok &= ok
        exact_docs += doc_ok
    n = len(gold_rows)
    return {
        "line_count_correct": round(count_ok / n, 4),
        "documents_all_lines_correct_excl_vat_rate": round(exact_docs / n, 4),
        "cell_accuracy": {k: round(v / total, 4) for k, v in correct.items() if k != "vat_rate"},
        "vat_rate_accuracy_where_printed": round(rate_printed_ok / rate_printed, 4) if rate_printed else None,
        "lines_with_printed_vat_rate": rate_printed,
        "gold_lines": total,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--split", default="dev")
    ap.add_argument("--track", choices=["text", "scan"], default="text")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    sys.path.insert(0, str(Path(os.environ.get("EURODOCBENCH_SRC", "../eurodocbench/src")).resolve()))
    from eurodocbench.score import score

    rows = pq.read_table(args.data / "data" / f"{args.split}.parquet").to_pylist()
    if args.limit:
        rows = rows[: args.limit]
    jobs = [(r["id"], r["pdf"] if args.track == "text" else r["image"]["bytes"], r["id"]) for r in rows]
    t0 = time.perf_counter()
    with ProcessPoolExecutor(args.workers) as pool:
        preds = list(pool.map(_run, jobs, chunksize=4))
    wall = time.perf_counter() - t0
    gold = [
        {"id": r["id"], "fields": r["fields"], "locale": r["locale"], "layout": r["layout"]} for r in rows
    ]
    s = score(gold, [{"id": p["id"], "fields": p.get("fields", {})} for p in preds])
    lines = line_scores(rows, preds)
    errors = [p for p in preds if "error" in p]
    conf = {"high": [0, 0], "medium": [0, 0], "low": [0, 0]}
    for g, p in zip(rows, preds, strict=True):
        for k, c in p.get("confidence", {}).items():
            conf[c][1] += 1
            conf[c][0] += str(p["fields"][k]) == str(g["fields"][k])
    summary = {
        "split": args.split, "track": args.track, "documents": len(rows), "errors": len(errors),
        "field_accuracy": round(s["field_accuracy"], 4), "field_precision": round(s["field_precision"], 4),
        "field_recall": round(s["field_recall"], 4), "document_accuracy": round(s["document_accuracy"], 4),
        "per_field": {k: round(v["accuracy"], 4) for k, v in s["fields"].items()},
        "per_locale": {k: round(v, 4) for k, v in s["by"]["locale"].items()} if "locale" in s.get("by", {}) else {},
        "per_layout": {k: round(v, 4) for k, v in s["by"]["layout"].items()} if "layout" in s.get("by", {}) else {},
        "confidence_calibration": {k: {"n": v[1], "correct": round(v[0] / v[1], 4) if v[1] else None} for k, v in conf.items()},
        "lines": lines,
        "seconds_per_document": round(sum(p["seconds"] for p in preds) / len(preds), 3),
        "wall_seconds": round(wall, 1),
    }  # fmt: skip
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (args.out / "predictions.jsonl").open("w") as fh:
        for p in preds:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
