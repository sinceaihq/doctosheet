// Build the review app into the Python package (src/doctosheet/static).
import { copyFileSync, mkdirSync } from "node:fs";
import { build } from "esbuild";

const out = "../src/doctosheet/static";
mkdirSync(out, { recursive: true });
await build({ entryPoints: ["src/app.ts"], bundle: true, minify: true, format: "esm", target: ["es2022"], outfile: `${out}/app.js`, legalComments: "linked", logLevel: "warning" });
copyFileSync("node_modules/pdfjs-dist/build/pdf.worker.min.mjs", `${out}/pdf.worker.mjs`);
for (const f of ["index.html", "styles.css", "icon.svg"]) copyFileSync(f, `${out}/${f}`);
console.log("built", out);
