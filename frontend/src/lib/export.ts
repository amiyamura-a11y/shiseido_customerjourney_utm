import { toPng, toSvg } from "html-to-image";

export function downloadCsv(filename: string, header: string[], rows: (string | number | null | undefined)[][], meta?: Record<string, unknown>) {
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines: string[] = [];
  if (meta) {
    for (const [k, v] of Object.entries(meta)) lines.push(`# ${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`);
  }
  lines.push(header.map(esc).join(","));
  for (const r of rows) lines.push(r.map(esc).join(","));
  const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  trigger(blob, filename);
}

export function downloadJson(filename: string, data: unknown) {
  trigger(new Blob([JSON.stringify(data, null, 1)], { type: "application/json" }), filename);
}

export async function exportElementPng(el: HTMLElement, filename: string) {
  const url = await toPng(el, { backgroundColor: "#ffffff", pixelRatio: 2, cacheBust: true });
  triggerUrl(url, filename);
}

export async function exportElementSvg(el: HTMLElement, filename: string) {
  const url = await toSvg(el, { backgroundColor: "#ffffff", cacheBust: true });
  triggerUrl(url, filename);
}

function trigger(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  triggerUrl(url, filename);
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function triggerUrl(url: string, filename: string) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}
