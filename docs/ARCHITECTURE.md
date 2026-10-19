# Architecture

```
src/doctosheet/
  extract.py    entry point: sniff the file type, e-invoice XML first, then PDF text layer, then OCR
  einvoice.py   CII (Factur-X/ZUGFeRD/XRechnung), UBL (Peppol/XRechnung) and Finvoice parsers (defusedxml)
  pdf.py        pdfplumber words with boxes, embedded XML attachments (pypdf), page rendering (pypdfium2)
  ocr.py        RapidOCR (PaddleOCR PP-OCRv5 detection + PP-OCRv6 multilingual recognition) → words with boxes
  layout.py     words → lines; character spans ↔ page boxes
  vocab.py      invoice vocabulary (labels, legal forms, table headers) in about 15 languages
  numbers.py    European amounts, quantities, percentages and dates
  fields.py     header fields: label → value right of / below it, check digits, party blocks, totals
  lines.py      line items: table header columns, or receipt-style "2 x item à price amount" rows
  checks.py     consistency checks that raise or lower confidence; suggestions for missing amounts
  export.py     XLSX (typed cells) and CSV (standard / European dialects), formula-injection safe
  sandbox.py    one process per file, time and memory limits
  server.py     FastAPI app on 127.0.0.1: token + Host checks, CSP, in-memory files
  cli.py        doctosheet serve | extract
  static/       built review app (from ui/)
ui/             TypeScript review app: viewer (pdf.js + boxes), form, line-item editor, export; api.ts switches
                between the local server and the in-browser backend of the web demo (lite.ts, Pyodide)
eval/           EuroDocBench and ZUGFeRD-corpus evaluations, report generator
```

## Design decisions

- **Exact data first.** An e-invoice's XML is the legally relevant invoice; reading it beats any OCR. Embedded XML is
  detected in every PDF.
- **Every value carries its evidence** (`Field.evidence`) and source box (`Field.box`), so the user can verify it in a
  click and the confidence mark is explainable.
- **Confidence is evidence-based**, not a model score: label match, check digits (IBAN mod 97, VAT number algorithms
  from python-stdnum), arithmetic (net + VAT = total, lines = net, rate × base = VAT), OCR word confidence.
- **No silent guessing.** Derived amounts are `computed=True` suggestions, empty in exports until accepted.
- **Rules, not a trained model, in v0.1.** On the available evaluation data a rule system with explicit evidence was
  both more accurate and more explainable than the small LLM baseline in EuroDocBench (82.7 % on text, 67.3 % on scans).
  A learned confidence model is the most promising next step (see EVALUATION.md).
- **Untrusted input is isolated** in a worker process; the UI is served with a strict CSP.
