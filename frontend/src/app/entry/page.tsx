"use client";
import { useEffect, useMemo, useState } from "react";
import { Header } from "@/components/layout/Header";
import { FilterBar } from "@/components/layout/FilterBar";
import { Callout, Card, Field, Kpi, Notes, Segmented, Select, StateBox } from "@/components/ui/primitives";
import { DataTable } from "@/components/ui/DataTable";
import { api, ApiError, type EntryResponse, type ValidationResponse } from "@/lib/api";
import { useFilters } from "@/store/filters";
import { num, pct, days } from "@/lib/format";

const WORRY = "肌悩み検索ALL（5変数統合）";

export default function EntryPage() {
  const { filters } = useFilters();
  const [options, setOptions] = useState<{ value: string; label: string; group: string }[]>([]);
  const [anchor, setAnchor] = useState<string>("");
  const [query, setQuery] = useState("");
  const [steps, setSteps] = useState(3);
  const [occurrence, setOccurrence] = useState<"first" | "last" | "all">("first");
  const [follow, setFollow] = useState<"next" | "next_in_category" | "within_days">("next");
  const [target, setTarget] = useState("");
  const [within, setWithin] = useState(7);
  const [categories, setCategories] = useState<string[]>([]);
  const [data, setData] = useState<EntryResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error" | "empty">("loading");
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationResponse | null>(null);

  useEffect(() => {
    api.entryOptions(filters.granularity).then((r) => {
      setOptions(r.options);
      setAnchor((a) => {
        if (r.options.some((o) => o.value === a)) return a;
        const prefer = [WORRY, "悩み・成分・カテゴリ検索", "検索_効能/肌悩み系_エイジング", "検索"];
        return prefer.map((p) => r.options.find((o) => o.value === p)?.value).find(Boolean) ?? r.options[0]?.value ?? "";
      });
    });
    api.labels("category").then((r) => setCategories(r.labels));
  }, [filters.granularity]);

  useEffect(() => {
    if (!anchor) return;
    let c = false;
    setState("loading");
    api.entry({ filters, anchor, steps, occurrence, follow, target_category: target || null, within_days: within, top_n: 12 })
      .then((d) => { if (c) return; setData(d); setState(d.n === 0 ? "empty" : "ready"); })
      .catch((e) => { if (c) return; setError(e instanceof ApiError ? e.message : String(e)); setState("error"); });
    return () => { c = true; };
  }, [filters, anchor, steps, occurrence, follow, target, within]);

  useEffect(() => {
    if (anchor === WORRY && !validation) api.validation().then(setValidation).catch(() => {});
  }, [anchor, validation]);

  const filtered = useMemo(() => options.filter((o) => !query || o.label.toLowerCase().includes(query.toLowerCase())), [options, query]);
  const worryRows = useMemo(() => (validation?.rows ?? []).filter((r) => r.section.startsWith("追加集計：悩み検索起点") && ((filters.age === "18-29" && r.segment.startsWith("18")) || (filters.age === "30-49" && r.segment.startsWith("30")))), [validation, filters.age]);

  return (
    <>
      <Header title="起点行動分析" sub="起点 → 2番目 → 3番目…。各率の分母を明示（起点単体経験率／起点経験者／直前パス経験者／全対象者）。" />
      <FilterBar />
      <div className="card px-4 py-3 mb-3 flex flex-wrap gap-5 items-end">
        <Field label="起点（検索可・実マスタに存在する項目のみ）">
          <div className="flex gap-1">
            <input className="ctl w-40" placeholder="絞り込み…" value={query} onChange={(e) => setQuery(e.target.value)} />
            <Select className="min-w-[280px]" value={anchor} onChange={setAnchor} options={filtered.map((o) => ({ value: o.value, label: o.label, group: o.group }))} />
          </div>
        </Field>
        <Field label="ステップ数">
          <Segmented value={String(steps)} onChange={(v) => setSteps(Number(v))} options={[2, 3, 4, 5, 6, 7, 8, 9, 10].map((s) => ({ value: String(s), label: String(s) }))} />
        </Field>
        <Field label="起点の出現">
          <Segmented value={occurrence} onChange={setOccurrence} options={[{ value: "first", label: "初回出現" }, { value: "last", label: "最終出現" }, { value: "all", label: "全出現" }]} />
        </Field>
        <Field label="後続の定義">
          <Segmented value={follow} onChange={setFollow} options={[{ value: "next", label: "直後の行動" }, { value: "next_in_category", label: "次に指定カテゴリが現れる行動" }, { value: "within_days", label: "指定日数内の後続行動" }]} />
        </Field>
        {follow === "next_in_category" && (
          <Field label="指定カテゴリ"><Select className="min-w-[200px]" value={target} onChange={setTarget} options={categories.map((c) => ({ value: c, label: c }))} placeholder="（未指定＝直後）" /></Field>
        )}
        {follow === "within_days" && (
          <Field label="日数以内"><input className="ctl w-16" type="number" min={0} max={30} value={within} onChange={(e) => setWithin(Math.max(0, Math.min(30, Number(e.target.value) || 0)))} /></Field>
        )}
      </div>
      <StateBox state={state} error={error}>
        {data && (
          <>
            <div className="grid grid-cols-5 gap-2.5 mb-3">
              <Kpi label="対象者 n" value={num(data.n)} />
              <Kpi label="起点単体経験率" value={pct(data.anchor_rate)} meta={`${num(data.anchor_count)}人 ÷ n`} tone="green" />
              <Kpi label="起点イベント件数" value={num(data.anchor_events)} meta={data.occurrence === "all" ? "全出現（延べ）" : data.occurrence === "first" ? "初回出現のみ" : "最終出現のみ"} />
              <Kpi label="2接点率の分母" value={num(data.anchor_count)} meta="起点経験者" tone="cyan" />
              <Kpi label="完全パス経験率の分母" value={num(data.n)} meta="フィルタ対象者数" />
            </div>
            {data.levels.map((lv) => (
              <Card key={lv.depth} title={`${lv.depth}接点パス（起点 → … → ${lv.depth}番目）`} sub={lv.depth === 2 ? "条件付き率の分母＝起点経験者" : `条件付き率の分母＝${lv.depth - 1}番目までのパスを経験した人`} className="mb-3">
                <DataTable
                  rows={lv.rows}
                  rowKey={(r) => r.path.join(">")}
                  exportName={`entry_${lv.depth}.csv`}
                  exportMeta={{ anchor: data.anchor, filters: JSON.stringify(data.filters), n: data.n, anchor_count: data.anchor_count, occurrence: data.occurrence, follow: data.follow }}
                  maxHeight={360}
                  columns={[
                    { key: "p", header: "パス", value: (r) => r.path.join(" → ") },
                    { key: "c", header: "ユニーク人数", num: true, value: (r) => r.count },
                    ...(data.occurrence === "all" ? [{ key: "ev", header: "イベント件数", num: true, value: (r: (typeof lv.rows)[number]) => r.events }] : []),
                    { key: "rp", header: "条件付き率", num: true, render: (r) => `${pct(r.rate_of_parent)}（/${num(r.parent_count)}）`, value: (r) => r.rate_of_parent },
                    { key: "ra", header: "起点経験者内率", num: true, render: (r) => pct(r.rate_of_anchor), value: (r) => r.rate_of_anchor },
                    { key: "rn", header: "完全パス経験率（/n）", num: true, render: (r) => pct(r.rate_of_all), value: (r) => r.rate_of_all },
                    { key: "dn", header: `${lv.depth}番目の平均時期`, num: true, render: (r) => days(r.avg_dn), value: (r) => r.avg_dn },
                  ]}
                />
              </Card>
            ))}
            <Notes notes={data.notes} />
            {anchor === WORRY && filters.result === "buyer" && filters.age !== "all" && (
              <Card title="追加集計Excel（悩み系KW起点）との照合" sub="Excel値／再計算値／差分／分母／定義／不一致理由" className="mt-3">
                {!validation ? (
                  <div className="text-[11px] text-n500">照合中…</div>
                ) : (
                  <DataTable
                    rows={worryRows}
                    rowKey={(r, i) => `${r.section}-${r.item}-${i}`}
                    exportName="entry_validation.csv"
                    maxHeight={360}
                    columns={[
                      { key: "sec", header: "区分", value: (r) => r.section.replace("追加集計：", "") },
                      { key: "item", header: "項目", value: (r) => r.item },
                      { key: "xl", header: "Excel値", num: true, render: (r) => pct(r.excel, 2), value: (r) => r.excel },
                      { key: "re", header: "再計算値", num: true, render: (r) => pct(r.recalc, 2), value: (r) => r.recalc },
                      { key: "diff", header: "差分", num: true, render: (r) => (r.diff === null ? "–" : `${(r.diff * 100).toFixed(2)}pt`), value: (r) => r.diff },
                      { key: "den", header: "分母", num: true, value: (r) => r.denominator },
                      { key: "def", header: "定義", value: (r) => r.definition },
                      { key: "m", header: "判定", render: (r) => (r.match ? <span className="chip chip-ok">一致</span> : <span className="chip chip-warn">不一致</span>) },
                      { key: "why", header: "不一致理由", value: (r) => r.reason },
                    ]}
                  />
                )}
                <div className="mt-2"><Callout>2接点は定義（初回出現の直後行動）が一致します。3接点はExcel側が率の積で算出された形跡があるため一致させず、差分理由を表示しています。</Callout></div>
              </Card>
            )}
            {anchor === WORRY && !(filters.result === "buyer" && filters.age !== "all") && <div className="mt-3"><Callout>Excelとの照合は「結果＝購入者」かつ年代を指定した場合に表示されます（追加集計Excelは年代別購入者の集計のため）。</Callout></div>}
          </>
        )}
      </StateBox>
    </>
  );
}
