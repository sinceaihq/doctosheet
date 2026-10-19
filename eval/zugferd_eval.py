"""Independent evaluation: invoices designed by other producers (ZUGFeRD corpus).

Each PDF embeds its own EN 16931 XML; the XML values are the gold standard.
DocToSheet reads the *printed* PDF (``use_embedded_xml=False``), and with
``--ocr`` a rendering of the pages (no text layer), so the text and OCR paths
are measured on layouts we did not design.

    python eval/zugferd_eval.py --corpus ../data/zugferd-corpus --split dev --out eval/results/zugferd-dev-text

Party names whose XML value spans several lines (a GLN or salutation line
plus the name) count as correct when the prediction equals one of the lines.
Scored only where the XML has a value (many files omit e.g. the due date even
when it is printed). Values are compared after the same normalisation as the
EuroDocBench scorer (case, spaces, dots in names; dates and amounts canonical).
"""

from __future__ import annotations

import argparse
import io
import json
import re
import time
import unicodedata
from concurrent.futures import ProcessPoolExecutor
from decimal import Decimal, InvalidOperation
from pathlib import Path

from doctosheet import extract
from doctosheet.model import HEADER_FIELDS

AMOUNTS = {"net_amount", "vat_amount", "total_amount"}


def norm(field: str, value: str | None) -> str | None:
    if value is None:
        return None
    if field in AMOUNTS:
        try:
            return f"{Decimal(value):.2f}"
        except InvalidOperation:
            return value
    v = unicodedata.normalize("NFKC", value).casefold()
    if field in ("seller_vat_id", "buyer_vat_id", "iban", "invoice_number"):
        return re.sub(r"[\s.\-/]", "", v)
    return re.sub(r"[\s.,]+", " ", v).strip()


def _render_as_scan(data: bytes) -> bytes:
    """The PDF's pages as one image per page, in a PDF without a text layer."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(data)
    images = [doc[i].render(scale=200 / 72).to_pil().convert("RGB") for i in range(min(len(doc), 5))]
    buf = io.BytesIO()
    images[0].save(buf, format="PDF", save_all=True, append_images=images[1:], resolution=200)
    return buf.getvalue()


def _run(job: tuple[str, bytes, bool]) -> dict:
    path, data, ocr = job
    t0 = time.perf_counter()
    try:
        if ocr:
            data = _render_as_scan(data)
        r = extract(data, path, use_embedded_xml=False)
        fields = {k: (None if f.computed else f.value) for k, f in r.fields.items()}
        conf = {k: f.confidence for k, f in r.fields.items() if f.value and not f.computed}
        return {"path": path, "fields": fields, "confidence": conf, "lines": len(r.lines), "method": r.method,
                "seconds": time.perf_counter() - t0}  # fmt: skip
    except Exception as exc:
        return {"path": path, "error": f"{type(exc).__name__}: {exc}", "seconds": time.perf_counter() - t0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--inventory", type=Path, default=Path("eval/zugferd-inventory.json"))
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    rows = [r for r in json.loads(args.inventory.read_text()) if r["split"] == args.split]
    jobs = [(r["path"], (args.corpus / r["path"]).read_bytes(), args.ocr) for r in rows]
    with ProcessPoolExecutor(args.workers) as pool:
        preds = list(pool.map(_run, jobs))
    per = {k: [0, 0, 0] for k in HEADER_FIELDS}  # correct, gold present, predicted-but-gold-missing
    conf = {"high": [0, 0], "medium": [0, 0], "low": [0, 0]}
    lines_ok = lines_n = 0
    for gold, p in zip(rows, preds, strict=True):
        if "error" in p:
            for k in HEADER_FIELDS:
                per[k][1] += gold["fields"][k] is not None
            continue
        for k in HEADER_FIELDS:
            g = norm(k, gold["fields"][k])
            v = norm(k, p["fields"][k])
            if g is None:
                per[k][2] += v is not None
                continue
            per[k][1] += 1
            ok = v == g
            if not ok and k in ("seller_name", "buyer_name") and "\n" in (gold["fields"][k] or ""):
                # Some files put extra lines into the XML name ("GLN …\nLief-Nr …\nNAME GMBH",
                # "Herrn\nMax Mustermann"); a printed name equal to one of those lines counts.
                ok = v in {norm(k, line) for line in gold["fields"][k].splitlines()}
            per[k][0] += ok
            if k in p["confidence"]:
                c = conf[p["confidence"][k]]
                c[1] += 1
                c[0] += ok
        lines_n += 1
        lines_ok += p["lines"] == gold["lines"]
    total_correct = sum(v[0] for v in per.values())
    total_gold = sum(v[1] for v in per.values())
    summary = {
        "split": args.split, "track": "ocr" if args.ocr else "text", "documents": len(rows),
        "producers": sorted({r["producer"] for r in rows}), "errors": [p for p in preds if "error" in p],
        "field_accuracy": round(total_correct / total_gold, 4),
        "per_field": {k: {"accuracy": round(v[0] / v[1], 4) if v[1] else None, "n": v[1], "extra_when_gold_missing": v[2]}
                      for k, v in per.items()},
        "confidence_calibration": {k: {"n": v[1], "correct": round(v[0] / v[1], 4) if v[1] else None} for k, v in conf.items()},
        "line_count_correct": round(lines_ok / lines_n, 4) if lines_n else None,
        "seconds_per_document": round(sum(p["seconds"] for p in preds) / len(preds), 2),
    }  # fmt: skip
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    with (args.out / "predictions.jsonl").open("w") as fh:
        for p in preds:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k != "errors"} | {"errors": len(summary["errors"])}, indent=1
        )
    )


if __name__ == "__main__":
    main()
