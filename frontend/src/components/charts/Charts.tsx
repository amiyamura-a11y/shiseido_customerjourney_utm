"use client";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, LineChart, Line, Legend } from "recharts";
import { num, pct } from "@/lib/format";

const ACCENT = "#059669";
const CYAN = "#0891b2";
const SERIES = ["#059669", "#0891b2", "#d9a21b", "#8b5cf6", "#e0557a", "#4caf50", "#f08a24", "#6b7f99"];

export function Histogram({ data, xLabel, color = ACCENT, height = 180 }: { data: { bin: number | string; count: number }[]; xLabel?: string; color?: string; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 6, right: 8, left: -18, bottom: 4 }}>
        <CartesianGrid vertical={false} stroke="#eeeeef" />
        <XAxis dataKey="bin" tick={{ fontSize: 10, fill: "#7a7a88" }} label={xLabel ? { value: xLabel, position: "insideBottom", offset: -2, fontSize: 10, fill: "#7a7a88" } : undefined} />
        <YAxis tick={{ fontSize: 10, fill: "#7a7a88" }} />
        <Tooltip formatter={(v) => [num(Number(v)) + "人", "人数"]} contentStyle={{ fontSize: 11 }} />
        <Bar dataKey="count" fill={color} radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function HBar({ data, valueKey = "rate", labelKey = "label", height = 220, color = ACCENT, asPct = true }: { data: Record<string, unknown>[]; valueKey?: string; labelKey?: string; height?: number; color?: string; asPct?: boolean }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 2, right: 40, left: 10, bottom: 2 }}>
        <CartesianGrid horizontal={false} stroke="#eeeeef" />
        <XAxis type="number" tick={{ fontSize: 10, fill: "#7a7a88" }} tickFormatter={(v) => (asPct ? `${Math.round(v * 100)}%` : num(v))} />
        <YAxis type="category" dataKey={labelKey} width={170} tick={{ fontSize: 10, fill: "#474755" }} />
        <Tooltip formatter={(v) => [asPct ? pct(Number(v)) : num(Number(v)), ""]} contentStyle={{ fontSize: 11 }} />
        <Bar dataKey={valueKey} fill={color} radius={[0, 2, 2, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function DailyLines({ data, series, height = 220 }: { data: Record<string, number | null>[]; series: string[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 6, right: 8, left: -18, bottom: 4 }}>
        <CartesianGrid vertical={false} stroke="#eeeeef" />
        <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#7a7a88" }} tickFormatter={(v) => `D−${v}`} reversed />
        <YAxis tick={{ fontSize: 10, fill: "#7a7a88" }} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
        <Tooltip formatter={(v, name) => [pct(Number(v)), String(name)]} labelFormatter={(l) => `D−${l}`} contentStyle={{ fontSize: 11 }} />
        <Legend wrapperStyle={{ fontSize: 10 }} />
        {series.map((s, i) => (
          <Line key={s} type="monotone" dataKey={s} stroke={SERIES[i % SERIES.length]} dot={false} strokeWidth={s === "全行動" ? 2.5 : 1.5} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function Heatmap({ rows, days }: { rows: { label: string; cells: { day: number; count: number; rate: number | null }[] }[]; days: number[] }) {
  const max = Math.max(...rows.flatMap((r) => r.cells.map((c) => c.rate ?? 0)), 0.0001);
  return (
    <div className="overflow-auto">
      <table className="border-collapse text-[10px]">
        <thead>
          <tr>
            <th className="text-left text-n600 pr-2 sticky left-0 bg-white font-bold">カテゴリ</th>
            {days.map((d) => (
              <th key={d} className="text-n500 font-normal px-[1px] min-w-[22px] text-center">{d % 5 === 0 ? `D−${d}` : ""}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <td className="pr-2 whitespace-nowrap text-n800 sticky left-0 bg-white">{r.label}</td>
              {r.cells.map((c) => {
                const t = (c.rate ?? 0) / max;
                return (
                  <td key={c.day} title={`${r.label} D−${c.day}: ${num(c.count)}人 (${pct(c.rate)})`} className="p-[1px]">
                    <div style={{ width: 20, height: 16, borderRadius: 2, background: `rgba(5,150,105,${0.06 + 0.9 * t})` }} />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const CHART_COLORS = { ACCENT, CYAN, SERIES };
