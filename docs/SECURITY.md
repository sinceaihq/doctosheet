# Security

DocToSheet processes untrusted files (invoices from anyone) on the user's computer. Threats considered: malicious or
malformed PDFs, images and XML; other web pages in the same browser trying to use the local server; other programs on
the network.

| risk | measure |
|---|---|
| Malformed or hostile PDF, image or XML exhausting CPU or memory, or crashing the app | Each file is processed in a separate process (`multiprocessing` spawn) with a 120 s time limit and an 8 GB address-space cap (`RLIMIT_AS`; ONNX Runtime reserves several GB it never touches, so the cap is high, but it stops runaway allocations). Files over 25 MB and PDFs over 20 pages are refused; images are limited to 60 megapixels (and Pillow's own decompression-bomb guard). A failing or killed worker becomes an error message. |
| Active content in PDFs | Nothing in a PDF is executed: no JavaScript, forms, actions or embedded programs. Text and embedded XML are read with pdfplumber/pdfminer.six and pypdf. The viewer uses pdf.js 6 (no `eval`, XFA disabled) under a CSP that forbids `eval`. |
| XML attacks (XXE, entity expansion) | XML is parsed with defusedxml, which refuses DTD entity tricks; files are capped at 5 MB. |
| Other web pages calling the local API (CSRF, DNS rebinding) | The server binds to 127.0.0.1 only and refuses other bind addresses. Every API call needs a random per-session token (sent in a header, given to the browser in the URL fragment, which is not sent to servers or put in referrers); requests with a Host other than 127.0.0.1/localhost are refused; responses carry `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`. No CORS headers are sent. |
| Spreadsheet formula injection | XLSX cells are written as text cells (never formulas); CSV text starting with `=`, `+`, `-`, `@`, tab or CR is prefixed with `'`. |
| Data leaving the computer | No telemetry, no network calls, except RapidOCR's one-time model download (from its project's model storage) the first time OCR is used. Uploaded files stay in the server's memory until it stops. |

Residual risks: bugs in the PDF and image libraries themselves (kept up to date; `pip-audit` runs in CI); the worker
limit does not apply on Windows (`resource` is unavailable — the time limit still applies); the web demo loads Pyodide
from a CDN.

Report vulnerabilities privately: <https://github.com/sinceaihq/doctosheet/security/advisories/new>.
