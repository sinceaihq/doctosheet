# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-20

First public release.

### Added
- Extraction from e-invoice XML (Factur-X / ZUGFeRD, XRechnung CII and UBL, Peppol BIS, Finvoice), PDF text layers
  and OCR (RapidOCR), with source boxes, confidence and evidence for every value.
- Header fields, line items (tables and receipt-style lines) and VAT breakdowns; consistency checks; computed amounts
  offered as suggestions only.
- Local review app (`doctosheet serve`), command line (`doctosheet extract`), Python API, XLSX and CSV export.
- Sandboxed processing of untrusted files; token- and host-checked local server.
- Web demo (Pyodide) for e-invoice XML and text PDFs.
- Evaluation on EuroDocBench and on independent invoices from the ZUGFeRD corpus.
