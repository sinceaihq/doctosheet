"""Print lines and field errors for one corpus PDF (dev split only)."""

import json
import sys
from pathlib import Path

from doctosheet import extract
from doctosheet.layout import group_lines
from doctosheet.pdf import read_pdf

sys.path.insert(0, "eval")
from zugferd_eval import norm

corpus = Path("../data/zugferd-corpus")
inv = {r["path"]: r for r in json.loads(Path("eval/zugferd-inventory.json").read_text())}
path = sys.argv[1]
assert inv[path]["split"] == "dev", "only dev files may be inspected"
data = (corpus / path).read_bytes()
for ln in group_lines(read_pdf(data).words)[: int(sys.argv[2]) if len(sys.argv) > 2 else 60]:
    print(f"p{ln.page} y{ln.box.y0:6.1f} | {ln.text}")
r = extract(data, path, use_embedded_xml=False)
for k, g in inv[path]["fields"].items():
    v = r.fields[k].value
    if g is not None and norm(k, v) != norm(k, g):
        print(f"  {k}: pred={v!r} gold={g!r} ev={r.fields[k].evidence}")
