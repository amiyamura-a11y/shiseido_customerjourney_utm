export const pct = (v: number | null | undefined, digits = 1): string => (v === null || v === undefined || Number.isNaN(v) ? "算出不可" : `${(v * 100).toFixed(digits)}%`);
export const num = (v: number | null | undefined, digits = 0): string => (v === null || v === undefined || Number.isNaN(v) ? "–" : v.toLocaleString("ja-JP", { maximumFractionDigits: digits, minimumFractionDigits: digits }));
export const pt = (v: number | null | undefined, digits = 1): string => (v === null || v === undefined || Number.isNaN(v) ? "算出不可" : `${v > 0 ? "+" : ""}${v.toFixed(digits)}pt`);
export const ratio = (v: number | null | undefined): string => (v === null || v === undefined || Number.isNaN(v) ? "算出不可" : `${v.toFixed(2)}×`);
export const days = (v: number | null | undefined): string => (v === null || v === undefined || Number.isNaN(v) ? "–" : `D−${v.toFixed(1)}`);
