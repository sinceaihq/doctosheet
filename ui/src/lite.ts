// DocToSheet Lite: the same review app with DocToSheet's Python code running in
// the browser (Pyodide). Files never leave the page. OCR (scans and photos)
// needs the installed app; e-invoice XML and PDFs with a text layer work here.

import { setBackend } from "./api";

(globalThis as { DOCTOSHEET_LITE?: boolean }).DOCTOSHEET_LITE = true;

const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";
// Pure-Python wheels served next to this page (see build.mjs and wheels.json).
const WHEELS_LIST = "wheels/wheels.json";

interface Py {
  runPythonAsync(code: string): Promise<unknown>;
  loadPackage(names: string[]): Promise<void>;
  globals: { set(name: string, value: unknown): void };
  pyimport(name: string): { install(urls: string[], opts?: unknown): Promise<void> };
}

let ready: Promise<Py> | null = null;
const files = new Map<string, Blob>();

function boot(): Promise<Py> {
  ready ??= (async () => {
    const mod = (await import(/* @vite-ignore */ `${PYODIDE}pyodide.mjs`)) as { loadPyodide(o: object): Promise<Py> };
    const py = await mod.loadPyodide({ indexURL: PYODIDE });
    await py.loadPackage(["micropip", "lxml", "pillow", "cryptography", "charset-normalizer"]);
    const wheels = (await (await fetch(WHEELS_LIST)).json()) as string[];
    const base = new URL("wheels/", location.href).href;
    await py.pyimport("micropip").install(
      wheels.map((w) => base + w),
      { deps: false },
    );
    await py.runPythonAsync(`
import json
from doctosheet import extract
from doctosheet.export import to_csv, to_xlsx

def _extract(data, name):
    return json.dumps(extract(bytes(data.to_py()), name).to_dict())

def _xlsx(docs):
    return to_xlsx(json.loads(docs))

def _csv(docs, table, dialect):
    return to_csv(json.loads(docs), table, dialect)
`);
    return py;
  })();
  return ready;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

async function call(py: Py, expr: string, args: Record<string, unknown>): Promise<unknown> {
  for (const [k, v] of Object.entries(args)) py.globals.set(k, v);
  return py.runPythonAsync(expr);
}

setBackend(async (path, init) => {
  const url = new URL(path, location.href);
  if (url.pathname === "/api/extract") {
    const form = init.body as FormData;
    const file = form.get("file") as File;
    if (/\.(png|jpe?g|tiff?|webp)$/i.test(file.name)) {
      return json({ detail: "Photos and scans need OCR, which is only in the installed app (pip install \"doctosheet[ocr]\")." }, 422);
    }
    try {
      const py = await boot();
      const data = new Uint8Array(await file.arrayBuffer());
      const out = (await call(py, "_extract(_data, _name)", { _data: data, _name: file.name })) as string;
      const id = crypto.randomUUID();
      files.set(id, file);
      return json({ id, result: JSON.parse(out) });
    } catch (err) {
      const message = String((err as Error).message ?? err);
      const last = message.trim().split("\n").pop() ?? message;
      return json({ detail: last.replace(/^\w+(Error|Exception|Unavailable|File): /, "") }, 422);
    }
  }
  const fileMatch = url.pathname.match(/^\/api\/files\/(.+)$/);
  if (fileMatch) {
    const blob = files.get(fileMatch[1]);
    return blob ? new Response(blob) : json({ detail: "Not found" }, 404);
  }
  if (url.pathname === "/api/export") {
    const py = await boot();
    const docs = JSON.parse(init.body as string).documents as unknown[];
    const payload = JSON.stringify(docs);
    if (url.searchParams.get("format") === "xlsx") {
      const bytes = (await call(py, "_xlsx(_docs)", { _docs: payload })) as { toJs(): Uint8Array };
      return new Response(new Blob([bytes.toJs() as Uint8Array<ArrayBuffer>]), {
        headers: { "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
      });
    }
    const csv = (await call(py, "_csv(_docs, _table, _dialect)", {
      _docs: payload,
      _table: url.searchParams.get("table") ?? "invoices",
      _dialect: url.searchParams.get("dialect") ?? "standard",
    })) as string;
    return new Response("﻿" + csv, { headers: { "Content-Type": "text/csv; charset=utf-8" } });
  }
  return json({ detail: "Not available in the web demo" }, 404);
});

// Start loading Python while the user picks files.
void boot();
