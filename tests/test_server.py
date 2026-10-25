from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from doctosheet.server import create_app

TOKEN = "t0ken"
SAMPLES = Path(__file__).parent / "samples"


def client() -> TestClient:
    return TestClient(create_app(TOKEN), base_url="http://127.0.0.1")


def test_token_and_host_are_required() -> None:
    c = client()
    assert c.get("/api/health").status_code == 401
    assert c.get("/api/health", headers={"X-DocToSheet-Token": "wrong"}).status_code == 401
    assert c.get("/api/health", headers={"X-DocToSheet-Token": TOKEN}).status_code == 200
    evil = TestClient(create_app(TOKEN), base_url="http://evil.example")
    assert evil.get("/", headers={"X-DocToSheet-Token": TOKEN}).status_code == 403


def test_security_headers() -> None:
    res = client().get("/")
    assert res.status_code == 200
    csp = res.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "unsafe-eval" not in csp
    assert res.headers["x-content-type-options"] == "nosniff"


def test_extract_and_export_roundtrip() -> None:
    c = client()
    h = {"X-DocToSheet-Token": TOKEN}
    with (SAMPLES / "invoice-fi.pdf").open("rb") as fh:
        res = c.post("/api/extract", headers=h, files={"file": ("invoice-fi.pdf", fh, "application/pdf")})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["result"]["fields"]["invoice_number"]["value"] == "2026-1047"
    assert c.get(f"/api/files/{body['id']}", headers=h).content[:4] == b"%PDF"
    xlsx = c.post("/api/export?format=xlsx", headers=h, json={"documents": [body["result"]]})
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    csv = c.post(
        "/api/export?format=csv&table=lines&dialect=eu", headers=h, json={"documents": [body["result"]]}
    )
    assert "Logon suunnittelu" in csv.content.decode("utf-8-sig")


def test_broken_pdf_is_reported_not_crashing() -> None:
    res = client().post(
        "/api/extract",
        headers={"X-DocToSheet-Token": TOKEN},
        files={"file": ("broken.pdf", b"%PDF-1.7\n garbage \n%%EOF", "application/pdf")},
    )
    assert res.status_code == 422
    assert res.json()["detail"]


def test_malformed_export_requests_are_rejected_cleanly() -> None:
    c = client()
    h = {"X-DocToSheet-Token": TOKEN}
    assert c.post("/api/export", headers=h, content=b"not json").status_code == 400
    assert c.post("/api/export", headers=h, json=[1, 2]).status_code == 400
    assert c.post("/api/export", headers=h, json={"documents": []}).status_code == 400
    assert c.post("/api/export?format=pdf", headers=h, json={"documents": [{}]}).status_code == 400
    assert c.post("/api/export", headers=h, json={"documents": [{"fields": 3}]}).status_code == 422
    assert c.post("/api/export?format=csv", headers=h, json={"documents": ["x"]}).status_code == 422
