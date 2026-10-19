// DocToSheet review app. Talks only to the local server that served it.

import { FIELD_LABELS, LINE_COLUMNS, type Doc, type Field, type LineItem, type Result } from "./types";
import { api, hasToken, isLite } from "./api";
import { scrollWithin, Viewer, type Marker } from "./viewer";

const h = <K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Record<string, string> = {},
  ...children: (Node | string)[]
): HTMLElementTagNameMap[K] => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v;
    else el.setAttribute(k, v);
  }
  el.append(...children);
  return el;
};

const docs: Doc[] = [];
let current: Doc | null = null;
let activeKey: string | null = null;

const docList = h("ul", { class: "doc-list", "aria-label": "Documents" });
const fileInput = h("input", { type: "file", multiple: "", accept: ".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp,.xml", hidden: "" });
const drop = h(
  "label",
  { class: "drop", tabindex: "0" },
  h("strong", {}, "Drop invoices or receipts here"),
  h("span", {}, "or click to choose files — PDF, image or e-invoice XML"),
);
const viewer = new Viewer((key) => select(key));
const panel = h("section", { class: "panel", "aria-live": "polite" });
const status = h("p", { class: "status", role: "status" });

const exportButton = h("button", { type: "button", class: "primary", disabled: "" }, "Export XLSX");
const csvSelect = h(
  "select",
  { "aria-label": "Export CSV" },
  h("option", { value: "" }, "Export CSV…"),
  h("option", { value: "invoices:standard" }, "Invoices (comma, 1234.56)"),
  h("option", { value: "invoices:eu" }, "Invoices (semicolon, 1234,56)"),
  h("option", { value: "lines:standard" }, "Line items (comma)"),
  h("option", { value: "lines:eu" }, "Line items (semicolon)"),
);

drop.append(fileInput);
drop.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});
fileInput.addEventListener("change", () => {
  void addFiles([...(fileInput.files ?? [])]);
  fileInput.value = "";
});
for (const t of [drop, document.body]) {
  t.addEventListener("dragover", (e) => {
    e.preventDefault();
    drop.classList.add("over");
  });
  t.addEventListener("dragleave", () => drop.classList.remove("over"));
  t.addEventListener("drop", (e) => {
    e.preventDefault();
    drop.classList.remove("over");
    void addFiles([...((e as DragEvent).dataTransfer?.files ?? [])]);
  });
}

async function addFiles(files: File[]): Promise<void> {
  for (const file of files) {
    const doc: Doc = { id: crypto.randomUUID(), name: file.name, status: "processing", file, reviewed: false };
    docs.push(doc);
    renderList();
    if (!current) void open(doc);
    try {
      const body = new FormData();
      body.append("file", file);
      const res = (await (await api("/api/extract", { method: "POST", body })).json()) as { id: string; result: Result };
      doc.id = res.id;
      doc.result = res.result;
      doc.status = "ready";
    } catch (err) {
      doc.status = "error";
      doc.error = (err as Error).message;
    }
    renderList();
    if (current === doc) void open(doc);
  }
}

function lowCount(r: Result): number {
  return (
    Object.values(r.fields).filter((f) => f.value !== null && (f.confidence === "low" || f.computed)).length +
    r.checks.filter((c) => c.status === "failed").length
  );
}

function renderList(): void {
  docList.replaceChildren(
    ...docs.map((d) => {
      const badge =
        d.status === "processing"
          ? h("span", { class: "badge" }, "reading…")
          : d.status === "error"
            ? h("span", { class: "badge conf-low" }, "failed")
            : d.reviewed
              ? h("span", { class: "badge conf-high" }, "reviewed")
              : lowCount(d.result!) > 0
                ? h("span", { class: "badge conf-low" }, `${lowCount(d.result!)} to check`)
                : h("span", { class: "badge conf-high" }, "looks complete");
      const b = h("button", { type: "button", class: d === current ? "doc current" : "doc" }, h("span", { class: "name" }, d.name), badge);
      b.addEventListener("click", () => void open(d));
      return h("li", {}, b);
    }),
  );
  const ready = docs.filter((d) => d.status === "ready");
  exportButton.toggleAttribute("disabled", ready.length === 0);
  csvSelect.toggleAttribute("disabled", ready.length === 0);
  status.textContent = docs.length ? `${ready.length} of ${docs.length} document(s) ready` : "";
}

async function open(doc: Doc): Promise<void> {
  current = doc;
  activeKey = null;
  renderList();
  if (doc.status === "processing") {
    viewer.clear("Reading the document…");
    panel.replaceChildren(h("p", { class: "muted" }, "Reading the document. Scanned pages take a few seconds each."));
    return;
  }
  if (doc.status === "error") {
    viewer.clear("");
    panel.replaceChildren(h("p", { class: "error" }, `Could not read ${doc.name}: ${doc.error}`));
    return;
  }
  const r = doc.result!;
  renderPanel();
  try {
    if (r.kind === "pdf") {
      const data = await (await api(`/api/files/${doc.id}`)).arrayBuffer();
      await viewer.showPdf(data, r.pages);
    } else if (r.kind === "image" && doc.file) {
      await viewer.showImage(doc.file, r.pages);
    } else {
      viewer.clear("An e-invoice (XML) has no page to show: the values were read exactly from its data.");
    }
  } catch (err) {
    viewer.clear(`The document could not be displayed (${(err as Error).message}).`);
  }
  drawMarkers();
}

function markers(r: Result): Marker[] {
  const out: Marker[] = [];
  for (const [k, f] of Object.entries(r.fields)) {
    if (f.box && f.value !== null) out.push({ key: `f:${k}`, box: f.box, confidence: f.confidence, label: FIELD_LABELS[k] });
  }
  r.lines.forEach((li, i) => {
    if (li.box) out.push({ key: `l:${i}`, box: li.box, confidence: li.amount.confidence, label: `Line ${i + 1}` });
  });
  return out;
}

function drawMarkers(): void {
  if (current?.result) viewer.markers(markers(current.result), activeKey);
}

function select(key: string): void {
  activeKey = key;
  drawMarkers();
  const el = panel.querySelector<HTMLElement>(`[data-key="${CSS.escape(key)}"]`);
  if (el) scrollWithin(panel, el);
  el?.querySelector<HTMLInputElement>("input")?.focus({ preventScroll: true });
}

const CONF_TEXT = { high: "✓", medium: "?", low: "!" } as const;
const CONF_TITLE = { high: "confident", medium: "please check", low: "check carefully" } as const;

function edited(f: Field, value: string): void {
  f.value = value.trim() === "" ? null : value.trim();
  f.source = "user";
  f.confidence = "high";
  f.computed = false;
  f.evidence = ["edited by you"];
}

function fieldRow(key: string, f: Field): HTMLElement {
  const id = `field-${key}`;
  const input = h("input", { id, type: "text", value: f.computed ? "" : (f.value ?? ""), autocomplete: "off" });
  if (f.computed) input.placeholder = "not on the document";
  input.addEventListener("focus", () => {
    activeKey = `f:${key}`;
    drawMarkers();
  });
  input.addEventListener("change", () => {
    edited(f, input.value);
    renderPanel();
    renderList();
  });
  const badge = h(
    "span",
    { class: `conf conf-${f.value === null ? "none" : f.confidence}`, title: f.value === null ? "not found" : CONF_TITLE[f.confidence] },
    f.value === null ? "–" : f.computed ? "!" : CONF_TEXT[f.confidence],
  );
  const why = h("small", { class: "evidence" }, f.value === null ? "not found" : f.evidence.join(" · "));
  const row = h("div", { class: "field", "data-key": `f:${key}` }, h("label", { for: id }, FIELD_LABELS[key]), h("div", { class: "input-row" }, badge, input), why);
  if (f.computed && f.value) {
    const accept = h("button", { type: "button" }, `Use ${f.value}`);
    accept.addEventListener("click", () => {
      edited(f, f.value ?? "");
      f.evidence = ["computed from the other amounts, accepted by you"];
      renderPanel();
      renderList();
    });
    row.append(h("div", { class: "suggestion" }, `Suggestion (not printed on the document): ${f.value} `, accept));
  }
  return row;
}

function lineTable(r: Result): HTMLElement {
  const head = h("tr", {}, ...LINE_COLUMNS.map(([, label]) => h("th", { scope: "col" }, label)), h("th", {}, h("span", { class: "sr-only" }, "Remove")));
  const body = h("tbody");
  r.lines.forEach((li, i) => {
    const tr = h("tr", { "data-key": `l:${i}` });
    for (const [k] of LINE_COLUMNS) {
      const f = li[k];
      const input = h("input", { type: "text", value: f.value ?? "", "aria-label": `${k} line ${i + 1}`, class: `conf-cell conf-${f.value === null ? "none" : f.confidence}` });
      input.title = f.evidence.join(" · ");
      input.addEventListener("focus", () => {
        activeKey = `l:${i}`;
        drawMarkers();
      });
      input.addEventListener("change", () => edited(f, input.value));
      tr.append(h("td", {}, input));
    }
    const del = h("button", { type: "button", class: "icon", "aria-label": `Remove line ${i + 1}` }, "×");
    del.addEventListener("click", () => {
      r.lines.splice(i, 1);
      renderPanel();
    });
    tr.append(h("td", {}, del));
    body.append(tr);
  });
  const add = h("button", { type: "button" }, "Add line");
  add.addEventListener("click", () => {
    const empty = (): Field => ({ value: null, raw: null, source: "user", box: null, confidence: "high", evidence: [], computed: false });
    const li: LineItem = { description: empty(), quantity: empty(), unit: empty(), unit_price: empty(), vat_rate: empty(), amount: empty(), box: null };
    r.lines.push(li);
    renderPanel();
  });
  return h("div", { class: "lines" }, h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, head), body)), add);
}

function renderPanel(): void {
  if (!current?.result) return;
  const r = current.result;
  const source =
    r.method === "xml"
      ? `Read exactly from e-invoice data (${r.einvoice}).`
      : r.method === "ocr"
        ? "Read with OCR from a scanned page or photo — check the values."
        : "Read from the PDF's text.";
  const checks = r.checks
    .filter((c) => c.status !== "not_applicable")
    .map((c) => h("li", { class: c.status === "ok" ? "ok" : "failed" }, `${c.status === "ok" ? "✓" : "✗"} ${c.name}: `, h("span", { class: "muted" }, c.detail)));
  const reviewed = h("button", { type: "button", class: current.reviewed ? "" : "primary" }, current.reviewed ? "Reviewed ✓" : "Mark as reviewed");
  reviewed.addEventListener("click", () => {
    current!.reviewed = !current!.reviewed;
    renderPanel();
    renderList();
    const next = docs.find((d) => d.status === "ready" && !d.reviewed);
    if (current!.reviewed && next) void open(next);
  });
  panel.replaceChildren(
    h("header", { class: "panel-head" }, h("h2", {}, r.file_name), h("p", { class: "muted" }, source)),
    ...r.warnings.map((w) => h("p", { class: "warning" }, w)),
    h("div", { class: "fields" }, ...Object.entries(r.fields).map(([k, f]) => fieldRow(k, f))),
    h("h3", {}, `Line items (${r.lines.length})`),
    lineTable(r),
    ...(r.vat_breakdown.length
      ? [h("h3", {}, "VAT"), h("ul", { class: "vat" }, ...r.vat_breakdown.map((v) => h("li", {}, `${v.rate.value ?? "?"} %: ${v.base.value ? `${v.base.value} → ` : ""}${v.vat.value ?? "?"}`)))]
      : []),
    ...(checks.length ? [h("h3", {}, "Checks"), h("ul", { class: "checks" }, ...checks)] : []),
    h("div", { class: "row" }, reviewed),
  );
}

async function download(path: string, name: string): Promise<void> {
  const documents = docs.filter((d) => d.status === "ready").map((d) => d.result);
  const res = await api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ documents }) });
  const url = URL.createObjectURL(await res.blob());
  const a = h("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

exportButton.addEventListener("click", () => void download("/api/export?format=xlsx", "doctosheet.xlsx").catch((e) => alert(e.message)));
csvSelect.addEventListener("change", () => {
  const [table, dialect] = csvSelect.value.split(":");
  csvSelect.value = "";
  if (table) void download(`/api/export?format=csv&table=${table}&dialect=${dialect}`, `doctosheet-${table}.csv`).catch((e) => alert(e.message));
});

document.getElementById("app")!.replaceChildren(
  h(
    "header",
    { class: "top" },
    h("div", { class: "brand" }, h("strong", {}, "DocToSheet"), h("span", { class: "muted" }, "Invoices to spreadsheets, on this computer")),
    h("div", { class: "row" }, status, csvSelect, exportButton),
  ),
  h("main", { class: "layout" }, h("aside", { class: "side" }, drop, docList), viewer.root, panel),
);
viewer.clear(
  isLite()
    ? "Web demo: everything runs in this page. Nothing is uploaded. Python is loading in the background…"
    : "Your documents stay on this computer. Nothing is uploaded to the internet.",
);
panel.replaceChildren(
  h("h2", {}, "How it works"),
  h(
    "ol",
    {},
    h("li", {}, "Drop invoices, receipts or e-invoice XML files on the left."),
    h("li", {}, "Check the values: ✓ confident, ? please check, ! check carefully. Click a value to see where it was read."),
    h("li", {}, "Correct anything that is wrong, then export to Excel or CSV."),
  ),
  h("p", { class: "muted" }, "Amounts are never guessed: if a total is not printed, DocToSheet suggests one and you decide."),
);
if (isLite()) {
  const samples: [string, string][] = [
    ["Finnish invoice (PDF)", "samples/invoice-fi.pdf"],
    ["German ZUGFeRD e-invoice (PDF with XML)", "samples/invoice-de-zugferd.pdf"],
    ["Dutch Peppol e-invoice (XML)", "samples/invoice-nl-peppol.xml"],
  ];
  const buttons = samples.map(([label, url]) => {
    const b = h("button", { type: "button" }, label);
    b.addEventListener("click", async () => {
      const blob = await (await fetch(url)).blob();
      void addFiles([new File([blob], url.split("/").pop()!, { type: blob.type })]);
    });
    return b;
  });
  // In the sidebar, so the samples stay available after a document is opened.
  drop.after(
    h(
      "div",
      { class: "samples" },
      h("strong", {}, "Try a sample (synthetic)"),
      ...buttons,
      h("small", { class: "muted" }, "This web demo reads e-invoice XML and PDFs with a text layer. Scans and photos (OCR) need the installed app."),
    ),
  );
}
if (!hasToken && !isLite()) {
  panel.prepend(h("p", { class: "error" }, "Open DocToSheet with the address printed by “doctosheet serve” (it contains an access token)."));
}
