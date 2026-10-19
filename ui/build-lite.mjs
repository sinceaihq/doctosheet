// Build the web demo (DocToSheet Lite) into ../dist-lite: the review app, the
// in-browser backend, pdf.js, pinned pure-Python wheels and synthetic samples.
//   node build-lite.mjs <path to doctosheet wheel>
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { basename } from "node:path";
import { build } from "esbuild";

const out = "../dist-lite";
const wheel = process.argv[2];
if (!wheel) throw new Error("usage: node build-lite.mjs dist/doctosheet-<v>-py3-none-any.whl");
rmSync(out, { recursive: true, force: true });
mkdirSync(`${out}/static`, { recursive: true });
mkdirSync(`${out}/wheels`, { recursive: true });
mkdirSync(`${out}/samples`, { recursive: true });
await build({ entryPoints: ["src/lite-main.ts"], bundle: true, minify: true, format: "esm", target: ["es2022"],
  outfile: `${out}/static/app.js`, legalComments: "linked", logLevel: "warning" });
copyFileSync("node_modules/pdfjs-dist/build/pdf.worker.min.mjs", `${out}/static/pdf.worker.mjs`);
for (const f of ["index.html", "styles.css", "icon.svg"]) copyFileSync(f, `${out}/${f === "index.html" ? f : `static/${f}`}`);
// Pure-Python dependencies, pinned (Pyodide provides lxml, Pillow, cryptography, charset-normalizer).
const pins = ["pdfminer.six==20260107", "pdfplumber==0.11.10", "pypdf==6.21.1", "python-stdnum==2.2",
  "defusedxml==0.7.1", "openpyxl==3.1.5", "et-xmlfile==2.0.0"];
execFileSync(process.env.PIP ?? "pip", ["download", "--no-deps", "--only-binary=:all:", "-d", `${out}/wheels`, ...pins], { stdio: "inherit" });
copyFileSync(wheel, `${out}/wheels/${basename(wheel)}`);
writeFileSync(`${out}/wheels/wheels.json`, JSON.stringify(readdirSync(`${out}/wheels`).filter((f) => f.endsWith(".whl")).sort()));
for (const f of ["invoice-fi.pdf", "invoice-de-zugferd.pdf", "invoice-nl-peppol.xml"]) copyFileSync(`../tests/samples/${f}`, `${out}/samples/${f}`);
console.log("built", out);
