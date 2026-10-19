# Evaluation

DocToSheet is evaluated on two kinds of documents. Code: [`eval/`](../eval). The extraction code was frozen at the
commit recorded in `eval/results/FROZEN_COMMIT` before the test numbers below were measured, and each test set was
evaluated once. (Later commits changed only the wording of warnings, formatting and the user interface, not
extraction.)

## 1. Independent invoices (ZUGFeRD corpus)

The [ZUGFeRD corpus](https://github.com/ZUGFeRD/corpus) (Apache-2.0) collects sample invoices produced by different
software vendors. Each PDF embeds its own EN 16931 XML, so the correct values are known exactly, while the printed
layout was designed by someone else — the closest we have to "invoices from the wild" with an answer key.

- **Selection** (`eval/zugferd_inventory.py`): PDFs in the corpus's `correct` folders with readable embedded CII XML,
  deduplicated by the XML's SHA-256 → 104 invoices.
- **Split by producer**: *dev* = intarsys and Mustangproject (32 invoices; inspected and used to improve the rules);
  *test* = symtrax, XML-Rechnung, FNFE and gpFacturX (72 invoices; not inspected).
- **Task**: DocToSheet reads the printed PDF with `use_embedded_xml=False`; with `--ocr`, the pages are rendered to
  images at 200 dpi first, so the OCR path reads the same documents.
- **Scoring** (`eval/zugferd_eval.py`): a field counts only when the XML has a value; values are compared after
  normalisation (case, spaces, separators; dates and amounts canonical). Some XML files put extra lines into a party
  name (a GLN or "Herrn" line before the name); a prediction equal to one of those lines counts as correct. Computed
  suggestions count as empty.

### Results (test producers)

<!-- zugferd:start -->
| field | printed PDF (text layer) | same pages as images (OCR) | invoices with this field |
|---|---|---|---|
| invoice number | 22.2 | 30.6 | 72 |
| invoice date | 62.5 | 54.2 | 72 |
| due date | 82.6 | 87.0 | 23 |
| currency | 98.6 | 100.0 | 72 |
| seller | 61.1 | 61.1 | 72 |
| seller VAT no. | 69.0 | 59.2 | 71 |
| buyer | 52.8 | 52.8 | 72 |
| buyer VAT no. | 71.4 | 57.1 | 14 |
| IBAN | 76.0 | 80.0 | 25 |
| net amount | 97.2 | 97.2 | 72 |
| VAT amount | 90.3 | 84.7 | 72 |
| total amount | 97.2 | 95.8 | 72 |
| **all fields** | **72.8** | **71.2** | |
| values marked ✓ that were correct | 90.5 (of 485) | 91.9 (of 434) | |
<!-- zugferd:end -->

Amounts are the strongest part: totals are the anchor of every invoice and are cross-checked. Invoice numbers, names
and issue dates depend on how each producer labels them; the dev producers taught DocToSheet some phrasings ("…rechnung
Nr. … vom …") that the test producers do not use. This gap between dev (92 %) and test (73 %) is the honest measure
of how rule-based extraction generalises, and the reason the app is built around review.

## 2. EuroDocBench (synthetic)

[EuroDocBench](https://huggingface.co/datasets/sinceaihq/eurodocbench): 1,200 synthetic test invoices in 12 locales and
5 layouts, as born-digital PDFs and as degraded scans. Scored with EuroDocBench's own scorer. Its VAT numbers and IBANs
deliberately fail their check digits; DocToSheet reports them with low confidence.

<!-- edb:start -->
| | text PDFs | simulated scans (OCR) | previous best on the scans |
|---|---|---|---|
| fields correct | 95.7 | 88.5 | 67.3 (EasyOCR → Qwen2.5-1.5B) |
| invoices with all 12 fields correct | 75.6 | 37.6 | 4.3 |
| values marked ✓ that were correct | 100.0 | 98.2 | — |
| line items: invoices with the right number of rows | 97.4 | 75.4 | — |
| line items: amounts correct | 97.1 | 74.9 | — |
| seconds per invoice (one process) | 0.155 | 4.771 | — |
<!-- edb:end -->

Per field:

<!-- edb-fields:start -->
| field | text PDFs | simulated scans |
|---|---|---|
| invoice number | 98.1 | 88.2 |
| invoice date | 100.0 | 96.2 |
| due date | 100.0 | 93.7 |
| currency | 93.4 | 92.8 |
| seller | 93.3 | 72.1 |
| seller VAT no. | 85.8 | 76.4 |
| buyer | 98.2 | 75.7 |
| buyer VAT no. | 88.5 | 83.1 |
| IBAN | 91.3 | 86.8 |
| net amount | 100.0 | 99.2 |
| VAT amount | 100.0 | 97.9 |
| total amount | 99.8 | 99.8 |
<!-- edb-fields:end -->

"Previous best" is the best published EuroDocBench baseline on the scan track. EuroDocBench's synthetic layouts are
regular; these numbers are much higher than on the independent invoices above and should not be read as real-world
accuracy.

## Development sets (for reference)

<!-- dev:start -->
| set | fields correct | ✓ correct |
|---|---|---|
| EuroDocBench dev, text | 96.0 | 100.0 |
| EuroDocBench dev, scans | 89.3 | 98.8 |
| ZUGFeRD dev producers, text | 92.0 | 98.4 |
| ZUGFeRD dev producers, OCR | 91.0 | 98.7 |
<!-- dev:end -->

## Limitations

- 72 independent invoices from four producers, mostly German, is a small and narrow sample. Real invoices from small
  businesses, receipts and photos vary much more; we would welcome lawfully shareable real documents for evaluation.
- OCR is evaluated on clean renderings and on EuroDocBench's simulated degradation, not on phone photos.
- Line items are scored on EuroDocBench only (the corpus's line structures are not compared row by row).
- No learned model is involved; confidence is rule-based. On unfamiliar layouts about one in ten values marked ✓ was
  wrong. A confidence model trained on development data is a possible next step.

## Reproduce

```bash
git clone --depth 1 https://github.com/ZUGFeRD/corpus ../data/zugferd-corpus
hf download sinceaihq/eurodocbench --repo-type dataset --local-dir ../data/eurodocbench
git clone https://github.com/sinceaihq/eurodocbench ../eurodocbench   # scorer
python eval/zugferd_inventory.py ../data/zugferd-corpus > eval/zugferd-inventory.json
python eval/zugferd_eval.py --corpus ../data/zugferd-corpus --split test --out eval/results/zugferd-test-text
python eval/zugferd_eval.py --corpus ../data/zugferd-corpus --split test --ocr --out eval/results/zugferd-test-ocr
EURODOCBENCH_SRC=../eurodocbench/src python eval/eurodocbench_eval.py --data ../data/eurodocbench --split test --track text --out eval/results/edb-test-text
EURODOCBENCH_SRC=../eurodocbench/src python eval/eurodocbench_eval.py --data ../data/eurodocbench --split test --track scan --out eval/results/edb-test-scan
python eval/report.py
```
