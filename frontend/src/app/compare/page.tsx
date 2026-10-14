"use client";
import { useEffect, useRef, useState } from "react";
import { Image as ImageIcon, FileCode2 } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { FilterBar } from "@/components/layout/FilterBar";
import { Button, Callout, Card, Field, Kpi, Notes, Segmented, SmallCell, StateBox } from "@/components/ui/primitives";
import { DataTable } from "@/components/ui/DataTable";
import { GoldenPathFlow, type GoldenPathFlowHandle } from "@/components/flow/GoldenPathFlow";
import { api, ApiError, type CompareResponse } from "@/lib/api";
import type { Filters } from "@/lib/types";
import { useFilters } from "@/store/filters";
import { num, pct, pt, ratio, days } from "@/lib/format";

type Preset = "buyer_vs_nonbuyer" | "age" | "short_vs_long" | "custom";

function label(f: Filters): string {
  const a = f.age === "all" ? "全年代" : f.age === "18-29" ? "18–29歳" : "30–49歳";
  const r = f.result === "all" ? "全体" : f.result === "buyer" ? "購入者" : "非購入者";
  const d = f.duration_preset === "all" ? "全期間" : f.duration_preset === "custom" ? `${f.duration_min ?? 0}〜${f.duration_max ?? "∞"}日` : `${f.duration_preset}日`;
  return `${a}・${r}・${d}`;
}

export default function ComparePage() {
  const { filters, graph: gs } = useFilters();
  const [preset, setPreset] = useState<Preset>("buyer_vs_nonbuyer");
  const [custom, setCustom] = useState<{ a: Partial<Filters>; b: Partial<Filters> }>({ a: { age: "18-29" }, b: { age: "30-49" } });
  const [data, setData] = useState<CompareResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error" | "empty">("loading");
  const [error, setError] = useState<string | null>(null);
  const refA = useRef<GoldenPathFlowHandle>(null);
  const refB = useRef<GoldenPathFlowHandle>(null);

  const build = (): { a: Filters; b: Filters } => {
    const base = { ...filters };
    switch (preset) {
      case "buyer_vs_nonbuyer":
        return { a: { ...base, result: "buyer" }, b: { ...base, result: "nonbuyer" } };
      case "age":
        return { a: { ...base, age: "18-29" }, b: { ...base, age: "30-49" } };
      case "short_vs_long":
        return { a: { ...base, duration_preset: "0-7", duration_min: null, duration_max: null }, b: { ...base, duration_preset: "22-30", duration_min: null, duration_max: null } };
      default:
        return { a: { ...base, ...custom.a }, b: { ...base, ...custom.b } };
    }
  };

  useEffect(() => {
    let c = false;
    const { a, b } = build();
    setState("loading");
    api.compare({ a, b, label_a: label(a), label_b: label(b), steps: gs.steps, mode: gs.mode === "anchor" && !gs.anchor ? "head" : gs.mode, anchor: gs.anchor, top_n: gs.top_n, min_count: gs.min_count, show_other: gs.show_other })
      .then((d) => { if (c) return; setData(d); setState(d.summary.n_a === 0 && d.summary.n_b === 0 ? "empty" : "ready"); })
      .catch((e) => { if (c) return; setError(e instanceof ApiError ? e.message : String(e)); setState("error"); });
    return () => { c = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, preset, custom, gs.steps, gs.mode, gs.anchor, gs.top_n, gs.min_count, gs.show_other]);

  const scale = data ? { maxRate: data.scale.max_rate, maxCount: data.scale.max_count } : null;
  return (
    <>
      <Header title="パス比較" sub="左右同条件のフローを比較。ノード位置・色・サイズスケール・ステップ数を揃えて表示。" />
      <FilterBar />
      <div className="card px-4 py-3 mb-3 flex flex-wrap gap-5 items-end">
        <Field label="プリセット">
          <Segmented<Preset> value={preset} onChange={setPreset} options={[{ value: "buyer_vs_nonbuyer", label: "購入者 vs 非購入者" }, { value: "age", label: "18–29歳 vs 30–49歳" }, { value: "short_vs_long", label: "短期(0–7日) vs 長期(22–30日)" }, { value: "custom", label: "任意A/B" }]} />
        </Field>
        {preset === "custom" && (
          <>
            {(["a", "b"] as const).map((side) => (
              <div key={side} className="flex gap-3 items-end border-l border-n150 pl-3">
                <span className="section-label pb-2">{side.toUpperCase()}</span>
                <Field label="年代"><Segmented value={custom[side].age ?? filters.age} onChange={(v) => setCustom((c) => ({ ...c, [side]: { ...c[side], age: v } }))} options={[{ value: "all", label: "全体" }, { value: "18-29", label: "18–29" }, { value: "30-49", label: "30–49" }]} size="sm" /></Field>
                <Field label="結果"><Segmented value={custom[side].result ?? filters.result} onChange={(v) => setCustom((c) => ({ ...c, [side]: { ...c[side], result: v } }))} options={[{ value: "buyer", label: "購入" }, { value: "nonbuyer", label: "非購入" }, { value: "all", label: "全体" }]} size="sm" /></Field>
                <Field label="期間"><Segmented value={custom[side].duration_preset ?? filters.duration_preset} onChange={(v) => setCustom((c) => ({ ...c, [side]: { ...c[side], duration_preset: v } }))} options={[{ value: "all", label: "全" }, { value: "0-7", label: "0–7" }, { value: "8-14", label: "8–14" }, { value: "15-21", label: "15–21" }, { value: "22-30", label: "22–30" }]} size="sm" /></Field>
              </div>
            ))}
          </>
        )}
        <div className="text-[10.5px] text-n500 ml-auto">ステップ数・モード・上位数は Golden Path の設定（{gs.steps}ステップ／{gs.mode}）を共用</div>
      </div>
      <StateBox state={state} error={error}>
        {data && (
          <>
            <div className="grid grid-cols-6 gap-2.5 mb-3">
              <Kpi label={`A: ${data.label_a}`} value={`n=${num(data.summary.n_a)}`} meta={`平均行動数 ${num(data.summary.avg_action_count_a, 2)}／平均観測期間 ${num(data.summary.avg_duration_a, 2)}日`} tone="green" />
              <Kpi label={`B: ${data.label_b}`} value={`n=${num(data.summary.n_b)}`} meta={`平均行動数 ${num(data.summary.avg_action_count_b, 2)}／平均観測期間 ${num(data.summary.avg_duration_b, 2)}日`} tone="cyan" />
              <Kpi label="平均行動数 差" value={data.summary.avg_action_count_a !== null && data.summary.avg_action_count_b !== null ? num(data.summary.avg_action_count_a - data.summary.avg_action_count_b, 2) : "算出不可"} meta="A − B" />
              <Kpi label="平均観測期間 差" value={data.summary.avg_duration_a !== null && data.summary.avg_duration_b !== null ? `${num(data.summary.avg_duration_a - data.summary.avg_duration_b, 2)}日` : "算出不可"} meta="A − B" />
              <Kpi label="購入 Outcome A／B" value={`${num(data.graph_a.censoring.buy)}／${num(data.graph_b.censoring.buy)}`} meta="最終観測行動の後" />
              <Kpi label="後続行動あり A／B" value={`${num(data.graph_a.censoring.more_actions)}／${num(data.graph_b.censoring.more_actions)}`} meta="打ち切り" />
            </div>
            <div className="grid grid-cols-2 gap-3 mb-3">
              {([["A", data.graph_a, data.label_a, refA], ["B", data.graph_b, data.label_b, refB]] as const).map(([k, g, l, r]) => (
                <Card key={k} title={`${k}: ${l}`} sub={`n=${num(g.n)}｜${g.steps}ステップ`} bodyClass="!p-2" right={<div className="flex gap-1"><Button size="sm" onClick={() => r.current?.exportPng(`compare_${k}.png`)}><ImageIcon size={12} /></Button><Button size="sm" onClick={() => r.current?.exportSvg(`compare_${k}.svg`)}><FileCode2 size={12} /></Button></div>}>
                  <GoldenPathFlow ref={r} graph={g} selectedNodes={[]} selectedEdges={[]} height={460} scale={scale} nodeOrder={data.node_order} compact />
                </Card>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <Card title="経験率の比較（行動単体）" sub="1回以上経験したユニーク人数÷各セグメント人数。差pt＝A−B、倍率＝A÷B。">
                <DataTable
                  rows={data.experience_rows}
                  rowKey={(r) => r.label}
                  exportName="compare_experience.csv"
                  exportMeta={{ A: data.label_a, B: data.label_b, n_a: data.summary.n_a, n_b: data.summary.n_b, filters_a: JSON.stringify(data.filters_a), filters_b: JSON.stringify(data.filters_b) }}
                  maxHeight={380}
                  columns={[
                    { key: "label", header: "行動", value: (r) => r.label },
                    { key: "a", header: "A 人数(率)", num: true, render: (r) => `${num(r.count_a)} (${pct(r.rate_a)})`, value: (r) => r.rate_a },
                    { key: "b", header: "B 人数(率)", num: true, render: (r) => `${num(r.count_b)} (${pct(r.rate_b)})`, value: (r) => r.rate_b },
                    { key: "d", header: "差pt", num: true, render: (r) => pt(r.diff_pt), value: (r) => r.diff_pt },
                    { key: "r", header: "倍率", num: true, render: (r) => ratio(r.ratio), value: (r) => r.ratio },
                    { key: "dn", header: "平均時期 A／B", num: true, render: (r) => `${days(r.avg_dn_a)}／${days(r.avg_dn_b)}`, value: (r) => r.avg_dn_a },
                    { key: "s", header: "", render: (r) => <SmallCell flag={r.small_cell} /> },
                  ]}
                />
              </Card>
              <Card title="条件付き遷移率の差（表示中のエッジ）" sub="遷移率＝遷移人数÷遷移元ノード人数。|差pt| 降順。">
                <DataTable
                  rows={data.edge_rows}
                  rowKey={(r) => `${r.step}:${r.source}>${r.target}`}
                  exportName="compare_edges.csv"
                  exportMeta={{ A: data.label_a, B: data.label_b }}
                  maxHeight={380}
                  columns={[
                    { key: "e", header: "遷移", render: (r) => `STEP${r.step} ${r.source} → ${r.target}`, value: (r) => `STEP${r.step} ${r.source} → ${r.target}` },
                    { key: "a", header: "A", num: true, render: (r) => `${pct(r.rate_a)} (${num(r.count_a)}/${num(r.den_a)})`, value: (r) => r.rate_a },
                    { key: "b", header: "B", num: true, render: (r) => `${pct(r.rate_b)} (${num(r.count_b)}/${num(r.den_b)})`, value: (r) => r.rate_b },
                    { key: "d", header: "差pt", num: true, render: (r) => pt(r.diff_pt), value: (r) => r.diff_pt },
                    { key: "s", header: "", render: (r) => <SmallCell flag={r.small_cell} /> },
                  ]}
                />
              </Card>
            </div>
            <Card title="差分ランキング（パス）" sub="A・Bそれぞれの経験率（ユニーク人数÷n）。|差pt| 降順。" className="mb-3">
              <div className="grid grid-cols-2 gap-3">
                {(["2", "3"] as const).map((k) => (
                  <div key={k}>
                    <div className="section-label mb-1">{k}ステップ {data.path_rows[k].note ? `｜${data.path_rows[k].note}` : ""}</div>
                    <DataTable
                      rows={data.path_rows[k].rows}
                      rowKey={(r) => r.path.join(">")}
                      exportName={`compare_paths_${k}.csv`}
                      exportMeta={{ A: data.label_a, B: data.label_b, n_a: data.summary.n_a, n_b: data.summary.n_b }}
                      maxHeight={320}
                      columns={[
                        { key: "p", header: "パス", value: (r) => r.path.join(" → ") },
                        { key: "a", header: "A", num: true, render: (r) => `${num(r.count_a)} (${pct(r.rate_a)})`, value: (r) => r.rate_a },
                        { key: "b", header: "B", num: true, render: (r) => `${num(r.count_b)} (${pct(r.rate_b)})`, value: (r) => r.rate_b },
                        { key: "d", header: "差pt", num: true, render: (r) => pt(r.diff_pt), value: (r) => r.diff_pt },
                        { key: "r", header: "倍率", num: true, render: (r) => ratio(r.ratio), value: (r) => r.ratio },
                        { key: "s", header: "", render: (r) => <SmallCell flag={r.small_cell} /> },
                      ]}
                    />
                  </div>
                ))}
              </div>
            </Card>
            <Callout kind="warn">{data.caveats.join(" ")}</Callout>
            <div className="mt-2"><Notes notes={[...data.graph_a.notes]} /></div>
          </>
        )}
      </StateBox>
    </>
  );
}
