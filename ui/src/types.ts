// Shapes of the JSON returned by /api/extract (see src/doctosheet/model.py).

export type Confidence = "high" | "medium" | "low";

export interface Box {
  page: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface Field {
  value: string | null;
  raw: string | null;
  source: "xml" | "text" | "ocr" | "computed" | "user" | null;
  box: Box | null;
  confidence: Confidence;
  evidence: string[];
  computed: boolean;
}

export interface LineItem {
  description: Field;
  quantity: Field;
  unit: Field;
  unit_price: Field;
  vat_rate: Field;
  amount: Field;
  box: Box | null;
}

export interface VatRow {
  rate: Field;
  base: Field;
  vat: Field;
}

export interface Check {
  name: string;
  status: "ok" | "failed" | "not_applicable";
  detail: string;
}

export interface Result {
  file_name: string;
  kind: "pdf" | "image" | "xml";
  pages: { width: number; height: number }[];
  method: "xml" | "text" | "ocr";
  einvoice: string | null;
  fields: Record<string, Field>;
  lines: LineItem[];
  vat_breakdown: VatRow[];
  checks: Check[];
  warnings: string[];
}

export interface Doc {
  id: string; // server file id, or a local id while processing
  name: string;
  status: "processing" | "ready" | "error";
  error?: string;
  result?: Result;
  file?: File;
  reviewed: boolean;
}

export const FIELD_LABELS: Record<string, string> = {
  invoice_number: "Invoice number",
  issue_date: "Invoice date",
  due_date: "Due date",
  currency: "Currency",
  seller_name: "Seller",
  seller_vat_id: "Seller VAT number",
  buyer_name: "Buyer",
  buyer_vat_id: "Buyer VAT number",
  iban: "IBAN",
  net_amount: "Net amount",
  vat_amount: "VAT amount",
  total_amount: "Total amount",
};

export const LINE_COLUMNS: [keyof Omit<LineItem, "box">, string][] = [
  ["description", "Description"],
  ["quantity", "Qty"],
  ["unit", "Unit"],
  ["unit_price", "Unit price"],
  ["vat_rate", "VAT %"],
  ["amount", "Amount"],
];
