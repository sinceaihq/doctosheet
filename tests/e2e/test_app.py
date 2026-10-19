"""The review app in a real browser (Chromium via Playwright)."""

from __future__ import annotations

import io
from pathlib import Path

import openpyxl
import pytest
from playwright.sync_api import Page, expect

from .conftest import TOKEN

pytest.importorskip("playwright")
SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def open_app(page: Page, server_url: str) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{server_url}/#token={TOKEN}")
    expect(page.get_by_text("Drop invoices or receipts here")).to_be_visible()
    page.errors = errors  # type: ignore[attr-defined]


def test_upload_review_and_export(page: Page, server_url: str) -> None:
    open_app(page, server_url)
    page.set_input_files("input[type=file]", str(SAMPLES / "invoice-fi.pdf"))
    expect(page.get_by_role("textbox", name="Invoice number")).to_have_value("2026-1047", timeout=30_000)
    expect(page.get_by_role("textbox", name="Total amount")).to_have_value("1568.75")
    expect(page.get_by_role("textbox", name="Due date")).to_have_value("2026-04-14")
    expect(page.locator(".marker").first).to_be_visible()
    expect(page.locator("tbody tr")).to_have_count(3)
    # correct a value, then export
    page.get_by_role("textbox", name="Buyer", exact=True).fill("Esimerkki Asiakas Oy")
    page.get_by_role("textbox", name="Buyer", exact=True).press("Enter")
    with page.expect_download() as dl:
        page.get_by_role("button", name="Export XLSX").click()
    wb = openpyxl.load_workbook(io.BytesIO(Path(dl.value.path()).read_bytes()))
    row = [c.value for c in wb["Invoices"][2]]
    assert "Esimerkki Asiakas Oy" in row
    assert 1568.75 in [v for v in row if isinstance(v, (int, float))]
    assert len(list(wb["Line items"].iter_rows(min_row=2))) == 3
    assert page.errors == []  # type: ignore[attr-defined]


def test_api_requires_token(page: Page, server_url: str) -> None:
    res = page.request.get(f"{server_url}/api/health")
    assert res.status == 401
    res = page.request.get(f"{server_url}/api/health", headers={"X-DocToSheet-Token": TOKEN})
    assert res.ok


def test_foreign_host_is_refused(page: Page, server_url: str) -> None:
    res = page.request.get(f"{server_url}/", headers={"Host": "evil.example"})
    assert res.status == 403
