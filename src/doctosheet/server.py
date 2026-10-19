"""Local web app: upload, review and export, on 127.0.0.1 only.

Every launch creates a random access token. The browser gets it in the URL
fragment of the address printed by ``doctosheet serve``; API calls must send it
in a header, so other web pages open in the same browser cannot use the local
API, and requests with a foreign Host header (DNS rebinding) are refused.
Uploaded files are kept in memory only, until the server stops.
"""

from __future__ import annotations

import secrets
import uuid
from importlib import resources
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from . import __version__
from .export import to_csv, to_xlsx
from .extract import MAX_BYTES
from .sandbox import ExtractionFailed, extract_isolated

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
MAX_FILES_IN_MEMORY = 200


class Guard(BaseHTTPMiddleware):
    def __init__(self, app: Any, token: str, port: int):
        super().__init__(app)
        self.token = token
        self.port = port

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        host = request.headers.get("host", "").rsplit(":", 1)[0]
        if host not in ALLOWED_HOSTS:
            return JSONResponse({"detail": "Forbidden host."}, status_code=403)
        if request.url.path.startswith("/api/") and not secrets.compare_digest(
            request.headers.get("x-doctosheet-token", ""), self.token
        ):
            return JSONResponse({"detail": "Missing or wrong access token."}, status_code=401)
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; "
            "worker-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response


def create_app(token: str, port: int = 0) -> FastAPI:
    app = FastAPI(title="DocToSheet", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(Guard, token=token, port=port)
    files: dict[str, tuple[str, bytes, str]] = {}
    static = resources.files("doctosheet") / "static"

    @app.get("/")
    def index() -> Response:
        return Response((static / "index.html").read_bytes(), media_type="text/html")

    @app.get("/static/{name}")
    def asset(name: str) -> Response:
        if "/" in name or name.startswith("."):
            raise HTTPException(404)
        path = static / name
        if not path.is_file():
            raise HTTPException(404)
        types = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".png": "image/png",
                 ".svg": "image/svg+xml", ".json": "application/json"}  # fmt: skip
        ext = name[name.rfind(".") :]
        return Response(path.read_bytes(), media_type=types.get(ext, "application/octet-stream"))

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/api/extract")
    async def extract_file(file: UploadFile = File(...)) -> dict[str, Any]:  # noqa: B008
        data = await file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB.")
        name = file.filename or "document"
        try:
            result = extract_isolated(data, name)
        except ExtractionFailed as exc:
            raise HTTPException(422, str(exc)) from exc
        if len(files) >= MAX_FILES_IN_MEMORY:
            files.pop(next(iter(files)))
        file_id = uuid.uuid4().hex
        files[file_id] = (name, data, file.content_type or "application/octet-stream")
        return {"id": file_id, "result": result}

    @app.get("/api/files/{file_id}")
    def original(file_id: str) -> Response:
        if file_id not in files:
            raise HTTPException(404)
        _name, data, _ = files[file_id]
        kind = "application/pdf" if data[:4] == b"%PDF" else "application/octet-stream"
        return Response(data, media_type=kind)

    @app.post("/api/export")
    async def export(
        request: Request, format: str = "xlsx", table: str = "invoices", dialect: str = "standard"
    ) -> Response:
        body = await request.json()
        docs = body.get("documents", [])
        if not isinstance(docs, list) or not docs:
            raise HTTPException(400, "No documents to export.")
        if format == "xlsx":
            return Response(
                to_xlsx(docs),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": 'attachment; filename="doctosheet.xlsx"'},
            )
        if format == "csv" and table in ("invoices", "lines", "vat") and dialect in ("standard", "eu"):
            return Response(
                to_csv(docs, table, dialect).encode("utf-8-sig"),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="doctosheet-{table}.csv"'},
            )
        raise HTTPException(400, "Unknown export format.")

    return app
