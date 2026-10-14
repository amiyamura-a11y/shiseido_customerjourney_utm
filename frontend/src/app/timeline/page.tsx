"use client";
import { useEffect, useState } from "react";
import { Header } from "@/components/layout/Header";
import { FilterBar } from "@/components/layout/FilterBar";
import { InsightBox } from "@/components/ui/InsightBox";
import { Card, Kpi, Notes, StateBox } from "@/components/ui/primitives";
import { DataTable } from "@/components/ui/DataTable";
import { Heatmap } from "@/components/charts/Charts";
import { api, ApiError, type TimelineResponse } from "@/lib/api";
import { useFilters } from "@/store/filters";
import { num, pct } from "@/lib/format";
import { downloadCsv } from "@/lib/export";

export default function TimelinePage() {
  const { filters } = useFilters();
  const [data, setData] = useState<TimelineResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error" | "empty">("loading");
  const [error, setError] = useState<string | null>(null);
  const [topN, setTopN] = useState(15);
  useEffect(() => {
    let c = false;
    setState("loading");
    api.timeline(filters, topN).then((d) => { if (c) return; setData(d); setState(d.n === 0 ? "empty" : "ready"); }).catch((e) => { if (c) return; setError(e instanceof ApiError ? e.message : String(e)); setState("error"); });
    return () => { c = true; };
  }, [filters, topN]);
  const daysAxis = Array.from({ length: 31 }, (_, i) => 30 - i);
  return (
    <>
      <Header title="時系列分析" sub="D−30〜D−0 のカテゴリ別ヒートマップ・時期別ランキング・観測期間別比較" actions={data ? <button className="btn btn-sm" onClick={() => downloadCsv("timeline_heatmap.csv", ["行動", ...daysAxis.map((d) => `D-${d}`)], data.heatmap.map((r) => [r.label, ...r.cells.map((c) => c.count)]), { filters: JSON.stringify(filters), n: data.n, 値: "ユニーク人数" })}>CSV</button> : null} />
      <FilterBar show={{ timing: false, dedupe: false, pathMode: false }} />
      <InsightBox request={{ page: "timeline", filters }} />
      <StateBox state={state} error={error}>
        {data && (
          <>
            <div className="grid grid-cols-4 gap-2.5 mb-3">
              <Kpi label="対象者 n" value={num(data.n)} tone="green" />
              <Kpi label="表示カテゴリ数" value={<input className="ctl w-20" type="number" min={3} max={40} value={topN} onChange={(e) => setTopN(Math.min(40, Math.max(3, Number(e.target.value) || 3)))} />} meta="経験人数上位" />
              <Kpi label="基準日" value="D−0" meta="非購入者の基準日は購入日ではない（定義未確認）" />
              <Kpi label="値の定義" value="ユニーク人数÷n" meta="同一人物の同日複数行動は1人" tone="cyan" />
            </div>
            <Card title="カテゴリ × 日（D−n）ヒートマップ" sub="セル＝その日に当該行動を経験したユニーク人数÷n。ホバーで数値。" className="mb-3">
              <Heatmap rows={data.heatmap} days={daysAxis} />
            </Card>
            <div className="mb-3">
              <Card title="時期別ランキング" sub="各ウィンドウ内に1回以上経験したユニーク人数÷n">
                <div className="grid grid-cols-3 gap-2">
                  {data.window_rankings.map((w) => (
                    <div key={w.window}>
                      <div className="section-label mb-1">{w.window}</div>
                      <table className="tbl">
                        <tbody>
                          {w.rows.slice(0, 10).map((r) => (
                            <tr key={r.label}>
                              <td className="!py-1">{r.label}</td>
                              <td className="num !py-1">{pct(r.rate)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
            <Card title="人の観測期間別の比較" sub="観測期間（日数）区分ごとの経験率（分母＝各区分の人数）" className="mb-3">
              <DataTable
                rows={data.labels.map((lab) => ({ label: lab, ...Object.fromEntries(data.duration_buckets.map((b) => [b.bucket, b.rows.find((r) => r.label === lab)?.rate ?? null])) }))}
                rowKey={(r) => r.label as string}
                exportName="timeline_duration_buckets.csv"
                exportMeta={{ filters: JSON.stringify(filters), buckets: data.duration_buckets.map((b) => `${b.bucket}: n=${b.n}`).join("; ") }}
                columns={[
                  { key: "label", header: "行動", value: (r) => r.label as string },
                  ...data.duration_buckets.map((b) => ({ key: b.bucket, header: `${b.bucket}（n=${num(b.n)}）`, num: true, render: (r: Record<string, unknown>) => pct(r[b.bucket] as number | null), value: (r: Record<string, unknown>) => r[b.bucket] as number | null })),
                ]}
              />
            </Card>
            <Notes notes={data.notes} />
          </>
        )}
      </StateBox>
    </>
  );
}
