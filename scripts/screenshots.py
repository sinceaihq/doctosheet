"""Screenshots of the running app for the README: python scripts/screenshots.py"""

import socket
import threading
import time
from pathlib import Path

import uvicorn
from playwright.sync_api import sync_playwright

from doctosheet.server import create_app

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app("shot", port), host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    with sync_playwright() as p:
        b = p.chromium.launch()
        for scheme in ("light", "dark"):
            page = b.new_page(viewport={"width": 1440, "height": 900}, color_scheme=scheme)
            page.goto(f"http://127.0.0.1:{port}/#token=shot")
            samples = ROOT / "tests" / "samples"
            page.set_input_files("input[type=file]", [str(samples / f) for f in
                                 ("invoice-fi.pdf", "invoice-de-zugferd.pdf", "receipt-fi.png", "invoice-nl-peppol.xml")])  # fmt: skip
            for _ in range(600):  # the app's CSP forbids eval, so poll from here
                badges = page.locator(".badge").all_text_contents()
                if len(badges) >= 4 and "reading…" not in badges:
                    break
                time.sleep(0.1)
            page.get_by_role("button", name="invoice-fi.pdf").click()
            page.wait_for_selector(".marker")
            page.get_by_role("textbox", name="Total amount").focus()
            time.sleep(0.8)
            page.screenshot(path=str(ROOT / f"docs/screenshots/review-{scheme}.png"))
            page.get_by_role("button", name="receipt-fi.png").click()
            page.wait_for_selector(".page img")
            time.sleep(0.8)
            page.screenshot(path=str(ROOT / f"docs/screenshots/receipt-{scheme}.png"))
        b.close()
    server.should_exit = True
