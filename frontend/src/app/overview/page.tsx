"use client";
import { useEffect, useState } from "react";
import { Header } from "@/components/layout/Header";
import { FilterBar } from "@/components/layout/FilterBar";
import { InsightBox } from "@/components/ui/InsightBox";
import { Card, Chip, Kpi, Notes, SmallCell, StateBox } from "@/components/ui/primitives";
import { DataTable } from "@/components/ui/DataTable";
import { Histogram, HBar } from "@/components/charts/Charts";
import { api, ApiError, type OverviewResponse } from "@/lib/api";
import { useFilters } from "@/store/filters";
import { num, pct, pt, ratio, days } from "@/lib/format";

export default function OverviewPage() {
  const { filters } = useFilters();
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error" | "empty">("loading");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let c = false;
    setState("loading");
    api.overview(filters).then((d) => { if (c) return; setData(d); setState(d.n === 0 ? "empty" : "ready"); }).catch((e) => { if (c) return; setError(e instanceof ApiError ? e.message : String(e)); setState("error"); });
    return () => { c = true; };
  }, [filters]);
  const q = (data?.quality ?? {}) as Record<string, unknown>;
  return (
    <>
      <Header title="データ概観" sub="母数・分布・行動カテゴリ一覧・データ品質。すべて個票CSVから再計算。" />
      <FilterBar show={{ pathMode: false }} />
      <InsightBox request={{ page: "overview", filters }} />
      <StateBox state={state} error={error}>
        {data && (
          <>
            <div className="grid grid-cols-6 gap-2.5 mb-3">
              <Kpi label="総人数（フィルタ後）" value={num(data.n)} meta={`購入 ${num(data.buyers)}／非購入 ${num(data.nonbuyers)}`} tone="green" />
              <Kpi label="年代別人数" value={<span className="text-[15px]">{Object.entries(data.by_age).map(([a, c]) => `${a} ${num(c)}`).join(" / ") || "–"}</span>} meta={Object.entries(data.by_age_result).map(([a, r]) => `${a}: 購入${num(r.buyers)}／非購入${num(r.nonbuyers)}`).join("、")} />
              <Kpi label="行動数（平均／中央値）" value={`${num(data.action_count.mean, 2)} / ${num(data.action_count.median, 1)}`} meta={`指示書の目安 ${data.expected.mean_action_count}`} />
              <Kpi label="観測期間（平均／中央値）" value={`${num(data.duration_days.mean, 2)} / ${num(data.duration_days.median, 1)}日`} meta="日数列。意思決定期間と断定しない（定義未確定）" />
              <Kpi label="ユニーク個別変数" value={num(data.unique_variables)} meta="フィルタ対象者が経験した変数" tone="cyan" />
              <Kpi label="ユニーク分析カテゴリ" value={num(data.unique_categories)} meta="マスタ『分析用カテゴリ』" tone="cyan" />
            </div>
            <div className="grid grid-cols-3 gap-3 mb-3">
              <Card title="行動数ヒストグラム" sub="行動01〜25の記録数（25列上限到達あり）">
                <Histogram data={data.hist_action_count} xLabel="行動数" />
              </Card>
              <Card title="観測期間分布" sub="日数（行動01のD−n）">
                <Histogram data={data.hist_duration} xLabel="日数" color="#0891b2" />
              </Card>
              <Card title="タイプ分類構成比" sub="CSVの『タイプ分類』列">
                <HBar data={data.journey_type_share.map((t) => ({ label: t.type, rate: t.rate, count: t.count }))} height={200} />
                <div className="mt-2 flex flex-wrap gap-1">
                  {data.start_period_share.map((s) => (
                    <Chip key={s.period} kind="neutral">開始期 {s.period}: {num(s.count)}（{pct(s.rate)}）</Chip>
                  ))}
                </div>
              </Card>
            </div>
            <Card title="行動カテゴリ一覧" sub={`人数・経験率（分母 n=${num(data.category_table_denominators.all)}）・平均発生時期・購入者（n=${num(data.category_table_denominators.buyers)}）／非購入者（n=${num(data.category_table_denominators.nonbuyers)}）差。粒度は共通フィルタに従う。`} className="mb-3">
              <DataTable
                rows={data.category_table}
                rowKey={(r) => r.label}
                exportName="overview_categories.csv"
                exportMeta={{ filters: JSON.stringify(filters), n: data.n, buyers_n: data.category_table_denominators.buyers, nonbuyers_n: data.category_table_denominators.nonbuyers }}
                maxHeight={520}
                columns={[
                  { key: "label", header: "行動", value: (r) => r.label },
                  { key: "count", header: "経験人数", num: true, value: (r) => r.count },
                  { key: "rate", header: "経験率", num: true, render: (r) => pct(r.rate), value: (r) => r.rate },
                  { key: "events", header: "延べ回数", num: true, value: (r) => r.events },
                  { key: "dn", header: "平均発生時期", num: true, render: (r) => days(r.avg_dn), value: (r) => r.avg_dn },
                  { key: "b", header: "購入者 経験率", num: true, render: (r) => `${pct(r.buyer_rate)} (${num(r.buyer_count)})`, value: (r) => r.buyer_rate },
                  { key: "nb", header: "非購入者 経験率", num: true, render: (r) => `${pct(r.nonbuyer_rate)} (${num(r.nonbuyer_count)})`, value: (r) => r.nonbuyer_rate },
                  { key: "d", header: "差pt", num: true, render: (r) => pt(r.diff_pt), value: (r) => r.diff_pt },
                  { key: "r", header: "倍率", num: true, render: (r) => ratio(r.ratio), value: (r) => r.ratio },
                  { key: "s", header: "", render: (r) => <SmallCell flag={r.small_cell} /> },
                ]}
              />
            </Card>
            <Card title="データ品質" sub="読み込み時の検査結果（全データ）">
              <div className="grid grid-cols-4 gap-2 text-[11px]">
                {[
                  ["文字コード", String(q.encoding ?? "–")],
                  ["行数／イベント数", `${num(q.rows as number)}／${num(q.events as number)}`],
                  ["行動列数", String(q.action_columns ?? "–")],
                  ["行動数と非欠損列数の不一致", `${num(q.action_count_mismatch_rows as number)} 行`],
                  ["D−n解析エラー", `${num(q.parse_error_events as number)} 件`],
                  ["マスタ未対応変数", `${((q.unmapped_variables as string[]) ?? []).length} 種（${num(q.unmapped_events as number)} 件）`],
                  ["25列上限到達", `${num(q.reached_25_rows as number)} 人`],
                  ["空白列の後に行動あり", `${num(q.gap_rows as number)} 行`],
                  ["D−nが時系列順でない行", `${num(q.non_monotonic_dn_rows as number)} 行`],
                  ["年代／結果／日数／行動数の欠損", `${num(q.missing_age as number)}／${num(q.missing_result as number)}／${num(q.missing_duration as number)}／${num(q.missing_action_count as number)}`],
                  ["行動01のD−n＝日数の行", `${num(q.first_dn_equals_duration_rows as number)} 行`],
                  ["未知の年代／結果値", `${((q.unknown_age_values as string[]) ?? []).join(",") || "なし"}／${((q.unknown_result_values as string[]) ?? []).join(",") || "なし"}`],
                ].map(([k, v]) => (
                  <div key={k} className="border border-n100 rounded px-2 py-1.5">
                    <div className="section-label">{k}</div>
                    <div className="font-bold text-n900">{v}</div>
                  </div>
                ))}
              </div>
              {((q.unmapped_variables as string[]) ?? []).length > 0 && <div className="mt-2 text-[11px] text-[#9a3412]">未分類変数: {(q.unmapped_variables as string[]).join(", ")}</div>}
              <div className="mt-2"><Notes notes={data.notes} /></div>
            </Card>
          </>
        )}
      </StateBox>
    </>
  );
}
