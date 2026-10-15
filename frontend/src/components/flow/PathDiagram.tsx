"use client";
import { colorFor } from "./palette";
import { num, pct } from "@/lib/format";

export interface PathRow {
  path: string[];
  count: number;
  rate: number | null;
  /** optional secondary stat shown after the main one (e.g. 非購入者率) */
  secondary?: string;
  small_cell?: boolean;
}

const NW = 150;
const NH = 46;
const GAP = 34;
const ROW = 60;
const STAT_W = 190;

function wrap(text: string, max: number): string[] {
  const base = text.replace(/ (\d+回目)$/, "");
  const lines: string[] = [];
  for (let i = 0; i < base.length && lines.length < 2; i += max) lines.push(base.slice(i, i + max));
  if (base.length > max * 2) lines[1] = lines[1].slice(0, max - 1) + "…";
  return lines;
}

/** Horizontal path diagrams (one row per path) in the same visual language as the Golden Path nodes. */
export function PathDiagram({ rows, onRowClick, statLabel = "人数（経験率）" }: { rows: PathRow[]; onRowClick?: (row: PathRow) => void; statLabel?: string }) {
  if (rows.length === 0) return <div className="text-[11px] text-n500 py-4 text-center">対象なし</div>;
  const k = Math.max(...rows.map((r) => r.path.length));
  const W = 16 + k * NW + (k - 1) * GAP + STAT_W;
  const H = rows.length * ROW + 8;
  return (
    <div className="overflow-auto border border-n150 rounded-[var(--r)] bg-white">
      <svg width="100%" style={{ maxWidth: W, display: "block" }} viewBox={`0 0 ${W} ${H}`} fontFamily="Inter,'Hiragino Sans','Noto Sans JP',sans-serif">
        <defs>
          <marker id="pdArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill="#8a8a98" />
          </marker>
        </defs>
        <text x={16 + k * NW + (k - 1) * GAP + 12} y={14} fontSize={9.5} fontWeight={700} fill="#7a7a88">{statLabel}</text>
        {rows.map((r, i) => {
          const y = 8 + i * ROW + 4;
          const cy = y + NH / 2;
          return (
            <g key={i} style={{ cursor: onRowClick ? "pointer" : "default" }} onClick={() => onRowClick?.(r)}>
              <rect x={4} y={y - 4} width={W - 8} height={ROW - 4} rx={6} fill="transparent" className="hover:fill-n25" />
              {r.path.map((lab, j) => {
                const x = 16 + j * (NW + GAP);
                const m = lab.match(/ (\d+回目)$/);
                const lines = wrap(lab, 13);
                return (
                  <g key={j}>
                    {j > 0 && <line x1={x - GAP + 2} y1={cy} x2={x - 3} y2={cy} stroke="#8a8a98" strokeWidth={2.5} markerEnd="url(#pdArrow)" />}
                    <rect x={x} y={y} width={NW} height={NH} rx={8} fill={colorFor(lab)} stroke="#fff" strokeWidth={2} />
                    {lines.map((ln, li) => (
                      <text key={li} x={x + NW / 2} y={y + (lines.length === 1 ? (m ? 20 : 28) : 18 + li * 12) - (m && lines.length === 2 ? 4 : 0)} textAnchor="middle" fontSize={10.5} fontWeight={700} fill="#fff">{ln}</text>
                    ))}
                    {m && <text x={x + NW / 2} y={y + NH - 7} textAnchor="middle" fontSize={9.5} fontWeight={600} fill="#fff" opacity={0.92}>{m[1]}</text>}
                  </g>
                );
              })}
              <text x={16 + k * NW + (k - 1) * GAP + 12} y={cy + 1} fontSize={12} fontWeight={700} fill="#101016">{num(r.count)}人</text>
              <text x={16 + k * NW + (k - 1) * GAP + 12 + 52} y={cy + 1} fontSize={11} fill="#474755">（{pct(r.rate)}）{r.secondary ? ` ${r.secondary}` : ""}</text>
              {r.small_cell && <text x={16 + k * NW + (k - 1) * GAP + 12} y={cy + 15} fontSize={9.5} fill="#b45309">5人未満：参考値</text>}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
