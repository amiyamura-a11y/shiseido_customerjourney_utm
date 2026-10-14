// Categorical palette for journey nodes (brand-neutral, readable with white text).
const PALETTE = ["#0f9d8a", "#d9a21b", "#4caf50", "#3b82c4", "#8b5cf6", "#e0557a", "#0891b2", "#f08a24", "#6b7f99", "#a3597c", "#5b8c3a", "#b4741a"];

const cache = new Map<string, string>();
export function colorFor(label0: string): string {
  const label = label0.replace(/ \d+回目$/, "");
  if (label === "その他") return "#9a9aa6";
  if (label === "購入") return "#059669";
  if (label === "非購入／観測終了") return "#64748b";
  if (label === "後続行動あり") return "#b8b8c2";
  if (label === "後続記録なし") return "#94a3b8";
  let c = cache.get(label);
  if (c) return c;
  let h = 0;
  for (let i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) >>> 0;
  c = PALETTE[h % PALETTE.length];
  cache.set(label, c);
  return c;
}
