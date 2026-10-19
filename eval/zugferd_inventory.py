"""Inventory of the ZUGFeRD corpus (https://github.com/ZUGFeRD/corpus, Apache-2.0) for evaluation.

Keeps PDFs from the "correct" folders that embed CII XML we can read, removes
duplicates (same embedded XML), and assigns each file to a split by producer:
dev = intarsys, Mustangproject (may be inspected); test = everything else (held out).
"""

import hashlib
import json
import sys
from pathlib import Path

from doctosheet.einvoice import EInvoiceError, parse
from doctosheet.pdf import embedded_files

corpus = Path(sys.argv[1])
rows, seen = [], set()
for pdf in sorted(corpus.rglob("*.pdf")):
    rel = pdf.relative_to(corpus).as_posix()
    if "/fail" in "/" + rel or rel.startswith("ZUGFeRDv1") or "/fail/" in rel:
        continue
    data = pdf.read_bytes()
    emb = embedded_files(data)
    if not emb:
        continue
    digest = hashlib.sha256(emb[1]).hexdigest()
    if digest in seen:
        continue
    try:
        fmt, fields, items, vat = parse(emb[1])
    except EInvoiceError:
        continue
    seen.add(digest)
    producer = rel.split("/")[2] if rel.startswith("ZUGFeRDv2/correct/") else rel.split("/")[0]
    split = "dev" if producer in ("intarsys", "Mustangproject") else "test"
    rows.append({"path": rel, "producer": producer, "split": split, "sha256_xml": digest,
                 "fields": {k: f.value for k, f in fields.items()}, "lines": len(items)})  # fmt: skip
json.dump(rows, sys.stdout, indent=1, ensure_ascii=False)
