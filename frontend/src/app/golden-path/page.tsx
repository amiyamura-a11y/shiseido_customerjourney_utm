"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Download, Image as ImageIcon, FileCode2, X, Maximize2 } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { FilterBar } from "@/components/layout/FilterBar";
import { InsightBox } from "@/components/ui/InsightBox";
import { Button, Callout, Card, Chip, Field, Kpi, Notes, Segmented, Select, SmallCell, StateBox } from "@/components/ui/primitives";
import { DataTable } from "@/components/ui/DataTable";
import { GoldenPathFlow, type GoldenPathFlowHandle } from "@/components/flow/GoldenPathFlow";
import { PathDiagram } from "@/components/flow/PathDiagram";
import { api, ApiError } from "@/lib/api";
import type { GraphResponse } from "@/lib/types";
import { useFilters } from "@/store/filters";
import { downloadCsv } from "@/lib/export";
import { num, pct, pt, ratio } from "@/lib/format";

const STEP_PRESETS = [2, 3, 4, 5, 6, 7, 8, 9, 10];

export default function GoldenPathPage() {
  const { filters, graph: gs, setGraph, setFilters, goldenPathResultInitialised, markGoldenPathInit, highlightPath, setHighlightPath } = useFilters();
  const [data, setData] = useState<GraphResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error" | "empty">("loading");
  const [error, setError] = useState<string | null>(null);
  const [selNodes, setSelNodes] = useState<{ step: number; label: string }[]>([]);
  const [selEdges, setSelEdges] = useState<{ step: number; source: string; target: string }[]>([]);
  const [labels, setLabels] = useState<string[]>([]);
  const [customSteps, setCustomSteps] = useState<string>("");
  const flowRef = useRef<GoldenPathFlowHandle>(null);
  const [tall, setTall] = useState(false);
  const [rankView, setRankView] = useState<"table" | "diagram">("table");
  const [openPath, setOpenPath] = useState<string | null>(null);

  // Golden Path initial value for 結果 is 購入者 (once)
  useEffect(() => {
    if (!goldenPathResultInitialised) {
      setFilters({ result: "buyer" });
      markGoldenPathInit();
    }
  }, [goldenPathResultInitialised, markGoldenPathInit, setFilters]);

  useEffect(() => {
    api.observedLabels(filters).then((r) => setLabels(r.labels)).catch(() => setLabels([]));
  }, [filters]);

  // reset selection when the base conditions change
  useEffect(() => {
    setSelNodes([]);
    setSelEdges([]);
  }, [filters, gs.steps, gs.mode, gs.anchor, gs.top_n, gs.min_count, gs.show_other, gs.other_mode]);

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    api
      .graph({ filters, steps: gs.steps, mode: gs.mode, anchor: gs.anchor, anchor_occurrence: gs.anchor_occurrence, top_n: gs.top_n, min_count: gs.min_count, min_rate: gs.min_rate, show_other: gs.show_other, other_mode: gs.other_mode, selected_nodes: selNodes, selected_edges: selEdges, include_rankings: true })
      .then((g) => {
        if (cancelled) return;
        setData(g);
        setState(g.n === 0 ? "empty" : "ready");
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof ApiError ? e.message : String(e));
        setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [filters, gs, selNodes, selEdges]);

  const onNodeClick = useCallback((step: number, label: string) => {
    setSelNodes((s) => (s.some((x) => x.step === step && x.label === label) ? s.filter((x) => !(x.step === step && x.label === label)) : [...s.filter((x) => x.step !== step), { step, label }]));
    setHighlightPath(null);
  }, [setHighlightPath]);
  const onEdgeClick = useCallback((step: number, source: string, target: string) => {
    setSelEdges((s) => (s.some((x) => x.step === step && x.source === source && x.target === target) ? s.filter((x) => !(x.step === step && x.source === source && x.target === target)) : [...s, { step, source, target }]));
    setHighlightPath(null);
  }, [setHighlightPath]);
  const clearSel = () => {
    setSelNodes([]);
    setSelEdges([]);
    setHighlightPath(null);
  };

  const exportCsv = () => {
    if (!data) return;
    const meta = { 条件: JSON.stringify(data.filters), モード: data.mode, ステップ数: data.steps, 対象者数n: data.n, 配置人数: data.n_placed, 選択: data.selection ? JSON.stringify(data.selection) : "なし", 注記: data.notes.join(" / ") };
    downloadCsv(
      "golden_path_nodes.csv",
      ["ステップ", "ノード", "種別", "人数", "経験率(分母n)", "ステップ到達者内構成比", "平均発生時期D-n", "購入者", "非購入者", "5人未満"],
      data.nodes.map((n) => [n.step, n.label, n.kind, n.count, n.rate, n.share_of_step, n.avg_dn, n.buyers, n.nonbuyers, n.small_cell ? "注意" : ""]),
      meta,
    );
    downloadCsv(
      "golden_path_edges.csv",
      ["ステップ", "遷移元", "遷移先", "人数", "分母(遷移元人数)", "条件付き遷移率", "全体に対する率", "5人未満"],
      data.edges.map((e) => [e.step, e.source_label, e.target_label, e.count, e.denominator, e.rate, e.rate_of_filtered, e.small_cell ? "注意" : ""]),
      meta,
    );
  };

  const summaryText = useMemo(() => {
    if (!data) return "";
    const seg = `${filters.age === "all" ? "全年代" : filters.age === "18-29" ? "18–29歳" : "30–49歳"}・${filters.result === "buyer" ? "購入者" : filters.result === "nonbuyer" ? "非購入者" : "全体"}`;
    return `${seg} n=${num(data.n)}。${data.mode === "head" ? `先頭${data.steps}ステップ` : data.mode === "tail" ? `末尾${data.steps}ステップ` : data.mode === "anchor" ? `起点「${data.anchor}」から${data.steps}ステップ` : "全25ステップ"}。Outcome 内訳：購入 ${num(data.censoring.buy)}／非購入・観測終了 ${num(data.censoring.nonbuy_end)}／後続行動あり ${num(data.censoring.more_actions)}。`;
  }, [data, filters]);

  return (
    <>
      <Header
        title="Golden Path"
        sub="STEP 1 → … → Outcome｜ノードの高さ＝経験率（分母：フィルタ対象者数）｜エッジ幅＝遷移人数｜ラベル＝条件付き遷移率｜クリックで絞り込み"
        actions={
          <div className="flex gap-1">
            <Button size="sm" onClick={() => flowRef.current?.exportPng("golden_path.png")} title="図全体をPNG出力"><ImageIcon size={12} /> PNG</Button>
            <Button size="sm" onClick={() => flowRef.current?.exportSvg("golden_path.svg")} title="図全体をSVG出力"><FileCode2 size={12} /> SVG</Button>
            <Button size="sm" onClick={exportCsv} title="ノード・エッジ集計をCSV出力"><Download size={12} /> CSV</Button>
          </div>
        }
      />
      <FilterBar />
      <InsightBox request={{ page: "golden-path", filters, steps: gs.steps, mode: gs.mode, anchor: gs.anchor, top_n: gs.top_n, other_mode: gs.other_mode }} />
      <div className="card px-4 py-3 mb-3">
        <div className="flex flex-wrap gap-x-5 gap-y-3 items-end">
          <Field label="表示モード">
            <Segmented value={gs.mode} onChange={(v) => setGraph({ mode: v })} options={[{ value: "head", label: "先頭nステップ" }, { value: "tail", label: "末尾nステップ" }, { value: "anchor", label: "任意起点" }, { value: "full", label: "全25ステップ" }]} />
          </Field>
          {gs.mode === "anchor" && (
            <>
              <Field label="起点">
                <Select className="min-w-[220px]" value={gs.anchor ?? ""} onChange={(v) => setGraph({ anchor: v || null })} options={labels.map((l) => ({ value: l, label: l }))} placeholder="起点を選択" />
              </Field>
              <Field label="起点の出現">
                <Segmented value={gs.anchor_occurrence} onChange={(v) => setGraph({ anchor_occurrence: v })} options={[{ value: "first", label: "初回" }, { value: "last", label: "最終" }]} />
              </Field>
            </>
          )}
          {gs.mode !== "full" && (
            <Field label="ステップ数">
              <div className="flex items-center gap-1">
                <Segmented value={String(gs.steps)} onChange={(v) => setGraph({ steps: Number(v) })} options={STEP_PRESETS.map((s) => ({ value: String(s), label: String(s) }))} />
                <input className="ctl w-16" type="number" min={2} max={25} placeholder="〜25" value={customSteps} onChange={(e) => setCustomSteps(e.target.value)} onBlur={() => { const v = Number(customSteps); if (v >= 2 && v <= 25) setGraph({ steps: v }); }} onKeyDown={(e) => { if (e.key === "Enter") { const v = Number(customSteps); if (v >= 2 && v <= 25) setGraph({ steps: v }); } }} />
              </div>
            </Field>
          )}
          <Field label="表示ノード上位数">
            <input className="ctl w-16" type="number" min={3} max={15} value={gs.top_n} onChange={(e) => setGraph({ top_n: Math.min(15, Math.max(3, Number(e.target.value) || 3)) })} />
          </Field>
          <Field label="最小人数">
            <input className="ctl w-16" type="number" min={0} value={gs.min_count} onChange={(e) => setGraph({ min_count: Math.max(0, Number(e.target.value) || 0) })} />
          </Field>
          <Field label="最小遷移率">
            <div className="flex items-center gap-1">
              <input className="ctl w-16" type="number" min={0} max={100} step={1} value={Math.round(gs.min_rate * 100)} onChange={(e) => setGraph({ min_rate: Math.min(1, Math.max(0, Number(e.target.value) / 100)) })} />
              <span className="text-[10px] text-n500">%</span>
            </div>
          </Field>
          <Field label="「その他」（上位N以外の行動）">
            <Segmented value={gs.other_mode ?? (gs.show_other ? "show" : "hide")} onChange={(v) => setGraph({ other_mode: v, show_other: v === "show" })} options={[{ value: "show", label: "表示" }, { value: "hide", label: "非表示" }, { value: "exclude", label: "除外して再集計", title: "経験人数上位N以外の行動をパスから除外し、残った行動を隣接として再集計" }]} />
          </Field>
          <div className="ml-auto flex gap-1">
            {(selNodes.length > 0 || selEdges.length > 0 || highlightPath) && (
              <Button size="sm" onClick={clearSel}><X size={12} /> 選択解除</Button>
            )}
            <Button size="sm" onClick={() => setTall((t) => !t)} title="描画領域の高さ切替"><Maximize2 size={12} /> {tall ? "標準" : "拡大"}</Button>
          </div>
        </div>
      </div>

      {data && (
        <div className="grid grid-cols-5 gap-2.5 mb-3">
          <Kpi label="対象者（分母 n）" value={num(data.n)} meta={`配置 ${num(data.n_placed)}人${data.selection ? `／選択後 ${num(data.n_in_graph)}人` : ""}`} tone="dark" />
          <Kpi label="ステップ数" value={data.steps} meta={data.mode === "head" ? "先頭" : data.mode === "tail" ? "末尾" : data.mode === "anchor" ? "起点から" : "全件"} />
          <Kpi label="購入 Outcome" value={num(data.censoring.buy)} meta="最終観測行動の後にのみ接続" tone="green" />
          <Kpi label="後続行動あり（打ち切り）" value={num(data.censoring.more_actions)} meta="表示範囲の後にも行動がある人" />
          <Kpi label="選択パス経験者" value={data.selection ? `${num(data.selection.count)}人` : "–"} meta={data.selection ? `${pct(data.selection.rate_of_filtered)}（分母 n=${num(data.selection.denominator)}）｜${data.selection.path_definition}` : "ノード／エッジをクリックして選択"} tone="cyan" />
        </div>
      )}

      <Card title="フロー" sub={summaryText} bodyClass="!p-2">
        <StateBox state={state} error={error}>
          {data && (
            <GoldenPathFlow ref={flowRef} graph={data} selectedNodes={selNodes} selectedEdges={selEdges} onNodeClick={onNodeClick} onEdgeClick={onEdgeClick} highlightPath={highlightPath} height={tall ? 860 : 560} />
          )}
        </StateBox>
        {data && (
          <div className="mt-2">
            <Notes notes={data.notes} />
          </div>
        )}
      </Card>

      {data?.selection && (
        <Card title="選択パス詳細" sub={data.selection.path_definition} className="mt-3" right={<Button size="sm" onClick={clearSel}><X size={12} /> 解除</Button>}>
          <div className="grid grid-cols-4 gap-2.5">
            <Kpi label="完全パス経験者（ユニーク）" value={`${num(data.selection.count)}人`} meta={`分母 n=${num(data.selection.denominator)}`} tone="cyan" />
            <Kpi label="完全パス経験率" value={pct(data.selection.rate_of_filtered)} meta="個票から直接計算（遷移率の積ではない）" />
            <Kpi label="購入者／非購入者" value={`${num(data.selection.buyers)}／${num(data.selection.nonbuyers)}`} meta="選択パス経験者の内訳" />
            <Kpi label="平均行動数／平均観測期間" value={`${num(data.selection.avg_action_count, 1)}／${num(data.selection.avg_duration_days, 1)}日`} meta="選択パス経験者" />
          </div>
          <div className="mt-2 text-[11px] text-n700">
            選択: {data.selection.selected_nodes.map((n) => `STEP${n.step}=${n.label}`).join("、")}
            {data.selection.selected_edges.length > 0 && ` ／ 遷移: ${data.selection.selected_edges.map((e) => `STEP${e.step} ${e.source}→${e.target}`).join("、")}`}
          </div>
        </Card>
      )}

      {data?.rankings && (
        <div className="grid grid-cols-2 gap-3 mt-3">
          <Card title="主要パス（連続／順序保持は共通フィルタに従う）" sub={`分母 n=${num(data.rankings.denominator)}${data.selection ? "（選択後）" : ""}。ユニーク人数ベース。行クリックでパス図を展開し、フロー上にハイライト。`} right={<Segmented value={rankView} onChange={setRankView} options={[{ value: "table", label: "表（クリックでパス図）" }, { value: "diagram", label: "パス図（すべて）" }]} size="sm" />}>
            {(["2", "3", "5"] as const).map((k) => (
              <div key={k} className="mb-3">
                <div className="section-label mb-1">{k}ステップ</div>
                {data.rankings!.top_paths[k].note && <div className="text-[10px] text-n500 mb-1">{data.rankings!.top_paths[k].note}</div>}
                {rankView === "diagram" ? (
                  <PathDiagram rows={data.rankings!.top_paths[k].rows.slice(0, 8)} onRowClick={(r) => setHighlightPath(r.path)} />
                ) : (
                <DataTable
                  rows={data.rankings!.top_paths[k].rows}
                  rowKey={(r) => r.path.join(">")}
                  maxHeight={360}
                  selectedKey={openPath}
                  expandRender={(r) => <PathDiagram rows={[r]} />}
                  onRowClick={(r) => { const key = r.path.join(">"); setOpenPath((o) => (o === key ? null : key)); setHighlightPath(r.path); }}
                  columns={[
                    { key: "path", header: "パス", render: (r) => <span>{r.path.join(" → ")}</span>, value: (r) => r.path.join(" → ") },
                    { key: "count", header: "人数", num: true, value: (r) => r.count },
                    { key: "rate", header: "経験率", num: true, render: (r) => pct(r.rate), value: (r) => r.rate },
                    { key: "occ", header: "延べ回数", num: true, value: (r) => r.occurrences },
                  ]}
                />
                )}
              </div>
            ))}
          </Card>
          <Card title="購入者に特徴的なパス" sub="同じ年代・期間条件の購入者 vs 非購入者の出現率差（pt）。因果効果ではありません。">
            {(["2", "3"] as const).map((k) => {
              const b = data.rankings!.buyer_characteristic[k];
              return (
                <div key={k} className="mb-3">
                  <div className="section-label mb-1">{k}ステップ｜購入者 n={num(b.buyer_n)}／非購入者 n={num(b.nonbuyer_n)}</div>
                  {rankView === "diagram" ? (
                    <PathDiagram statLabel="購入者 人数（率）／非購入者率・差pt" rows={b.rows.slice(0, 8).map((r) => ({ path: r.path, count: r.buyer_count, rate: r.buyer_rate, secondary: `vs ${pct(r.nonbuyer_rate)} ${pt(r.diff_pt)}`, small_cell: r.small_cell }))} onRowClick={(r) => setHighlightPath(r.path)} />
                  ) : (
                  <DataTable
                    rows={b.rows}
                    rowKey={(r) => r.path.join(">")}
                    maxHeight={360}
                    selectedKey={openPath}
                    expandRender={(r) => <PathDiagram statLabel="購入者 人数（率）／非購入者率・差pt" rows={[{ path: r.path, count: r.buyer_count, rate: r.buyer_rate, secondary: `vs ${pct(r.nonbuyer_rate)} ${pt(r.diff_pt)}`, small_cell: r.small_cell }]} />}
                    onRowClick={(r) => { const key = r.path.join(">"); setOpenPath((o) => (o === key ? null : key)); setHighlightPath(r.path); }}
                    columns={[
                      { key: "path", header: "パス", value: (r) => r.path.join(" → ") },
                      { key: "b", header: "購入者", num: true, render: (r) => `${num(r.buyer_count)}（${pct(r.buyer_rate)}）`, value: (r) => r.buyer_rate },
                      { key: "n", header: "非購入者", num: true, render: (r) => `${num(r.nonbuyer_count)}（${pct(r.nonbuyer_rate)}）`, value: (r) => r.nonbuyer_rate },
                      { key: "d", header: "差pt", num: true, render: (r) => pt(r.diff_pt), value: (r) => r.diff_pt },
                      { key: "r", header: "倍率", num: true, render: (r) => ratio(r.ratio), value: (r) => r.ratio },
                      { key: "s", header: "", render: (r) => <SmallCell flag={r.small_cell} /> },
                    ]}
                  />
                  )}
                </div>
              );
            })}
            <Callout kind="warn">{data.rankings.buyer_characteristic["2"].caveat}</Callout>
          </Card>
        </div>
      )}
      {data && (
        <div className="mt-3 text-[10.5px] text-n500 flex gap-3 flex-wrap">
          <Chip kind="neutral">経験率の分母: {data.denominators.experience_rate}</Chip>
          <Chip kind="neutral">構成比の分母: {data.denominators.share_of_step}</Chip>
          <Chip kind="neutral">遷移率の分母: {data.denominators.edge_rate}</Chip>
          <Chip kind="neutral">ノードのホバーで人数・分母・経験率・平均発生時期を表示</Chip>
        </div>
      )}
    </>
  );
}
