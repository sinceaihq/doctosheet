"""Print DocToSheet's lines and field errors for one EuroDocBench document (development aid)."""

import json
import sys

import pyarrow.parquet as pq

from doctosheet.extract import extract
from doctosheet.layout import group_lines
from doctosheet.pdf import read_pdf

split, doc_id = sys.argv[1], sys.argv[2]
rows = {r["id"]: r for r in pq.read_table(f"../data/eurodocbench/data/{split}.parquet").to_pylist()}
r = rows[doc_id]
content = read_pdf(r["pdf"])
for ln in group_lines(content.words):
    print(f"p{ln.page} y{ln.box.y0:6.1f} | {ln.text}")
res = extract(r["pdf"])
for k, g in r["fields"].items():
    p = res.fields[k].value
    if str(p) != str(g):
        print(f"  {k}: pred={p!r} gold={g!r} ev={res.fields[k].evidence}")
print("lines pred", len(res.lines), "gold", len(r["lines"]))
for li in res.lines[:3]:
    print(
        "  ", li.description.value, li.quantity.value, li.unit_price.value, li.vat_rate.value, li.amount.value
    )
print("  gold:", json.dumps(r["lines"][:2], ensure_ascii=False))
