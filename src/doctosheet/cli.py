"""Command line: ``doctosheet serve`` (review app) and ``doctosheet extract`` (batch)."""

from __future__ import annotations

import argparse
import json
import secrets
import socket
import sys
import webbrowser
from pathlib import Path

from . import __version__


def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    from .server import create_app

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        sys.exit("DocToSheet only listens on this computer (127.0.0.1); other hosts are not allowed.")
    port = args.port
    if port == 0:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
    token = secrets.token_urlsafe(24)
    url = f"http://127.0.0.1:{port}/#token={token}"
    print(
        f"DocToSheet {__version__} is running at:\n\n  {url}\n\nPress Ctrl+C to stop. Files stay on this computer."
    )
    if not args.no_browser:
        webbrowser.open(url)
    uvicorn.run(create_app(token, port), host="127.0.0.1", port=port, log_level="warning")


def _extract(args: argparse.Namespace) -> None:
    from .export import to_csv, to_xlsx
    from .sandbox import ExtractionFailed, extract_isolated

    docs = []
    failed = 0
    for path in args.files:
        p = Path(path)
        try:
            data = p.read_bytes()
            result = extract_isolated(data, p.name)
        except (OSError, ExtractionFailed) as exc:
            print(f"{p.name}: {exc}", file=sys.stderr)
            failed += 1
            continue
        docs.append(result)
        if not args.output and not args.json:
            _print_summary(result)
    if args.json:
        print(json.dumps(docs if len(docs) != 1 else docs[0], ensure_ascii=False, indent=2))
    if args.output:
        out = Path(args.output)
        if out.suffix.lower() == ".xlsx":
            out.write_bytes(to_xlsx(docs))
        elif out.suffix.lower() == ".csv":
            out.write_text(to_csv(docs, args.table, args.dialect), encoding="utf-8-sig")
        else:
            sys.exit("The output file must end in .xlsx or .csv")
        print(f"Wrote {len(docs)} document(s) to {out}", file=sys.stderr)
    if failed:
        sys.exit(1)


def _print_summary(result: dict) -> None:  # type: ignore[type-arg]
    from .model import FIELD_LABELS, HEADER_FIELDS

    print(
        f"\n{result['file_name']}  (read from: {result['method']}{', ' + result['einvoice'] if result['einvoice'] else ''})"
    )
    for k in HEADER_FIELDS:
        f = result["fields"][k]
        if f["value"] is None:
            continue
        mark = {"high": " ", "medium": "?", "low": "!"}[f["confidence"]]
        extra = "  (suggestion, not printed)" if f["computed"] else ""
        print(f"  {mark} {FIELD_LABELS[k]:<18} {f['value']}{extra}")
    if result["lines"]:
        print(f"    {len(result['lines'])} line item(s)")
    for c in result["checks"]:
        if c["status"] == "failed":
            print(f"  ! check failed: {c['name']} — {c['detail']}")
    for w in result["warnings"]:
        print(f"  · {w}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="doctosheet", description="Invoices and receipts to spreadsheets, locally."
    )
    parser.add_argument("--version", action="version", version=f"doctosheet {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("serve", help="open the review app in your browser")
    s.add_argument("--port", type=int, default=0)
    s.add_argument("--host", default="127.0.0.1", help=argparse.SUPPRESS)
    s.add_argument("--no-browser", action="store_true")
    s.set_defaults(func=_serve)
    e = sub.add_parser("extract", help="extract one or more files")
    e.add_argument("files", nargs="+")
    e.add_argument("-o", "--output", help="write .xlsx or .csv")
    e.add_argument("--json", action="store_true", help="print the full result as JSON")
    e.add_argument(
        "--table", choices=["invoices", "lines", "vat"], default="invoices", help="table for CSV output"
    )
    e.add_argument("--dialect", choices=["standard", "eu"], default="standard",
                   help="CSV: standard (comma, 1234.56) or eu (semicolon, 1234,56)")  # fmt: skip
    e.set_defaults(func=_extract)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
