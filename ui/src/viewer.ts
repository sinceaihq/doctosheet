// Shows the original document with boxes where values were read.
// PDFs are rendered with pdf.js (no scripting, no eval); images as <img>.

import * as pdfjs from "pdfjs-dist";
import type { Box, Confidence } from "./types";

pdfjs.GlobalWorkerOptions.workerSrc = "/static/pdf.worker.mjs";

export interface Marker {
  key: string;
  box: Box;
  confidence: Confidence;
  label: string;
}

export class Viewer {
  readonly root: HTMLElement;
  private pages: { el: HTMLElement; scale: number }[] = [];
  private onSelect: (key: string) => void;

  constructor(onSelect: (key: string) => void) {
    this.root = document.createElement("div");
    this.root.className = "viewer";
    this.onSelect = onSelect;
  }

  clear(message = ""): void {
    this.pages = [];
    const p = document.createElement("p");
    p.className = "viewer-empty";
    p.textContent = message;
    this.root.replaceChildren(p);
  }

  async showPdf(data: ArrayBuffer, pageSizes: { width: number; height: number }[]): Promise<void> {
    this.root.replaceChildren();
    this.pages = [];
    // pdf.js 6 never evaluates code from fonts; the app's CSP forbids eval anyway.
    const task = pdfjs.getDocument({
      data: new Uint8Array(data),
      enableXfa: false,
      disableAutoFetch: true,
      useSystemFonts: false,
    });
    const doc = await task.promise;
    const width = Math.max(320, this.root.clientWidth - 24);
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i);
      const base = page.getViewport({ scale: 1 });
      const scale = width / base.width;
      const viewport = page.getViewport({ scale: scale * (window.devicePixelRatio || 1) });
      const canvas = document.createElement("canvas");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.width = `${base.width * scale}px`;
      canvas.style.height = `${base.height * scale}px`;
      await page.render({ canvas, viewport }).promise;
      const wrap = document.createElement("div");
      wrap.className = "page";
      wrap.style.width = canvas.style.width;
      wrap.style.height = canvas.style.height;
      wrap.setAttribute("aria-label", `Page ${i}`);
      wrap.append(canvas);
      this.root.append(wrap);
      // Boxes from the server are in PDF points from the top-left of the page.
      const pointsWidth = pageSizes[i - 1]?.width ?? base.width;
      this.pages.push({ el: wrap, scale: (base.width * scale) / pointsWidth });
    }
    await task.destroy();
  }

  async showImage(blob: Blob, pageSizes: { width: number; height: number }[]): Promise<void> {
    this.root.replaceChildren();
    const url = URL.createObjectURL(blob);
    const img = document.createElement("img");
    img.alt = "Document";
    img.src = url;
    await img.decode();
    const width = Math.max(320, this.root.clientWidth - 24);
    const scale = width / (pageSizes[0]?.width ?? img.naturalWidth);
    img.style.width = `${width}px`;
    const wrap = document.createElement("div");
    wrap.className = "page";
    wrap.style.width = `${width}px`;
    wrap.append(img);
    this.root.append(wrap);
    this.pages = [{ el: wrap, scale }];
  }

  markers(list: Marker[], active: string | null): void {
    for (const { el } of this.pages) el.querySelectorAll(".marker").forEach((m) => m.remove());
    for (const m of list) {
      const page = this.pages[m.box.page];
      if (!page) continue;
      const pad = 2;
      const d = document.createElement("button");
      d.type = "button";
      d.className = `marker conf-${m.confidence}${m.key === active ? " active" : ""}`;
      d.style.left = `${m.box.x0 * page.scale - pad}px`;
      d.style.top = `${m.box.y0 * page.scale - pad}px`;
      d.style.width = `${(m.box.x1 - m.box.x0) * page.scale + 2 * pad}px`;
      d.style.height = `${(m.box.y1 - m.box.y0) * page.scale + 2 * pad}px`;
      d.title = m.label;
      d.setAttribute("aria-label", `Show ${m.label}`);
      d.addEventListener("click", () => this.onSelect(m.key));
      page.el.append(d);
      if (m.key === active) scrollWithin(this.root, d);
    }
  }
}

/** Scroll only `container` (not the window) so that `el` is visible. */
export function scrollWithin(container: HTMLElement, el: HTMLElement): void {
  const c = container.getBoundingClientRect();
  const r = el.getBoundingClientRect();
  if (r.top < c.top || r.bottom > c.bottom) {
    container.scrollBy({ top: r.top - c.top - c.height / 2 + r.height / 2, behavior: "smooth" });
  }
}
