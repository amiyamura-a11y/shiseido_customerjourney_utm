"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Route } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { FilterBar } from "@/components/layout/FilterBar";
import { Button, Callout, Card, Field, Kpi, Notes, Segmented, Select, SmallCell, StateBox } from "@/components/ui/primitives";
import { DataTable } from "@/components/ui/DataTable";
import { api, ApiError, type DetailResponse, type SearchResponse, type SearchRow } from "@/lib/api";
import { useFilters } from "@/store/filters";
import { num, pct, pt, ratio, days } from "@/lib/format";

export default function SearchPage() {
  const { filters, setHighlightPath, setGraph } = useFilters();
  const router = useRouter();
  const [labels, setLabels] = useState<string[]>([]);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [via, setVia] = useState<string[]>([]);
  const [viaPick, setViaPick] = useState("");
  const [minSteps, setMinSteps] = useState(2);
  const [maxSteps, setMaxSteps] = useState(3);
  const [minCount, setMinCount] = useState(10);
  const [sort, setSort] = useState("count");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error" | "empty">("loading");
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<DetailResponse | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    api.labels(filters.granularity).then((r) => setLabels(r.labels));
  }, [filters.granularity]);

  useEffect(() => {
    let c = false;
    setState("loading");
    api.search({ filters, start: start || null, end: end || null, via, min_steps: minSteps, max_steps: Math.max(minSteps, maxSteps), min_count: minCount, limit: 200, sort })
      .then((d) => { if (c) return; setData(d); setState(d.n === 0 ? "empty" : "ready"); })
      .catch((e) => { if (c) return; setError(e instanceof ApiError ? e.message : String(e)); setState("error"); });
    return () => { c = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, tick, sort]);

  const openDetail = (r: SearchRow) => {
    setSelected(r.path_str);
    setDetail(null);
    api.detail({ filters, path: r.path, examples: 5 }).then(setDetail).catch(() => setDetail(null));
  };
  const toGoldenPath = (p: string[]) => {
    setHighlightPath(p);
    setGraph({ mode: "anchor", anchor: p[0], steps: Math.max(p.length, 3) });
    router.push("/golden-path");
  };

  return (
    <>
      <Header title="パス詳細探索" sub="起点・終点・経由・ステップ数・人数閾値で検索。行クリックで匿名の実行動例と内訳を表示。" />
      <FilterBar />
      <div className="card px-4 py-3 mb-3 flex flex-wrap gap-4 items-end">
        <Field label="起点"><Select className="min-w-[200px]" value={start} onChange={setStart} options={labels.map((l) => ({ value: l, label: l }))} placeholder="（指定なし）" /></Field>
        <Field label="終点"><Select className="min-w-[200px]" value={end} onChange={setEnd} options={labels.map((l) => ({ value: l, label: l }))} placeholder="（指定なし）" /></Field>
        <Field label="経由（中間に含む）">
          <div className="flex gap-1 items-center flex-wrap">
            <Select className="min-w-[180px]" value={viaPick} onChange={(v) => { if (v && !via.includes(v)) setVia([...via, v]); setViaPick(""); }} options={labels.map((l) => ({ value: l, label: l }))} placeholder="追加…" />
            {via.map((v) => (
              <span key={v} className="chip chip-neutral cursor-pointer" onClick={() => setVia(via.filter((x) => x !== v))} title="クリックで削除">{v} ×</span>
            ))}
          </div>
        </Field>
        <Field label="ステップ数">
          <div className="flex items-center gap-1">
            <input className="ctl w-14" type="number" min={2} max={10} value={minSteps} onChange={(e) => setMinSteps(Math.max(2, Math.min(10, Number(e.target.value) || 2)))} />
            <span className="text-n500">〜</span>
            <input className="ctl w-14" type="number" min={2} max={10} value={maxSteps} onChange={(e) => setMaxSteps(Math.max(2, Math.min(10, Number(e.target.value) || 2)))} />
          </div>
        </Field>
        <Field label="最小人数"><input className="ctl w-16" type="number" min={0} value={minCount} onChange={(e) => setMinCount(Math.max(0, Number(e.target.value) || 0))} /></Field>
        <Field label="並び順">
          <Segmented value={sort} onChange={setSort} options={[{ value: "count", label: "人数" }, { value: "rate", label: "経験率" }, { value: "diff_pt", label: "差pt" }, { value: "ratio", label: "倍率" }, { value: "buyer_rate", label: "購入者率" }]} />
        </Field>
        <Button variant="primary" onClick={() => setTick((t) => t + 1)}>検索</Button>
      </div>
      <StateBox state={state} error={error}>
        {data && (
          <>
            <div className="grid grid-cols-4 gap-2.5 mb-3">
              <Kpi label="対象者 n" value={num(data.n)} />
              <Kpi label="該当パス数" value={num(data.total_matches)} meta="上位200件表示" tone="green" />
              <Kpi label="購入者 n／非購入者 n" value={`${num(data.buyer_n)}／${num(data.nonbuyer_n)}`} meta="同条件（年代・期間）での分母" tone="cyan" />
              <Kpi label="パス定義" value={filters.path_mode === "consecutive" ? "連続パス" : "順序保持パス"} meta={filters.path_mode === "consecutive" ? "隣接遷移のみ" : "間に他行動を許容（初回出現ベース）"} />
            </div>
            <div className={`grid ${selected ? "grid-cols-[3fr_2fr]" : "grid-cols-1"} gap-3`}>
              <Card title="検索結果" sub="経験率の分母＝n。購入者率／非購入者率の分母は同条件の購入者／非購入者。">
                <DataTable
                  rows={data.rows}
                  rowKey={(r) => r.path_str}
                  selectedKey={selected}
                  onRowClick={openDetail}
                  exportName="path_search.csv"
                  exportMeta={{ filters: JSON.stringify(data.filters), n: data.n, buyer_n: data.buyer_n, nonbuyer_n: data.nonbuyer_n, start, end, via: via.join("|"), min_steps: minSteps, max_steps: maxSteps, min_count: minCount }}
                  maxHeight={620}
                  pageSize={50}
                  columns={[
                    { key: "p", header: "パス", render: (r) => <span className="whitespace-normal">{r.path_str}</span>, value: (r) => r.path_str },
                    { key: "k", header: "ステップ", num: true, value: (r) => r.steps },
                    { key: "c", header: "人数", num: true, value: (r) => r.count },
                    { key: "r", header: "経験率", num: true, render: (r) => pct(r.rate), value: (r) => r.rate },
                    { key: "b", header: "購入者率", num: true, render: (r) => `${pct(r.buyer_rate)} (${num(r.buyer_count)})`, value: (r) => r.buyer_rate },
                    { key: "nb", header: "非購入者率", num: true, render: (r) => `${pct(r.nonbuyer_rate)} (${num(r.nonbuyer_count)})`, value: (r) => r.nonbuyer_rate },
                    { key: "d", header: "差pt", num: true, render: (r) => pt(r.diff_pt), value: (r) => r.diff_pt },
                    { key: "x", header: "倍率", num: true, render: (r) => ratio(r.ratio), value: (r) => r.ratio },
                    { key: "dur", header: "平均期間", num: true, render: (r) => `${num(r.avg_duration, 1)}日`, value: (r) => r.avg_duration },
                    { key: "ac", header: "平均行動数", num: true, render: (r) => num(r.avg_action_count, 1), value: (r) => r.avg_action_count },
                    { key: "s", header: "", render: (r) => <SmallCell flag={r.small_cell} /> },
                  ]}
                />
                <div className="mt-2"><Notes notes={data.notes} /></div>
              </Card>
              {selected && (
                <Card title="パス詳細" sub={selected} right={detail ? <Button size="sm" onClick={() => toGoldenPath(detail.path)}><Route size={12} /> Golden Pathでハイライト</Button> : null}>
                  {!detail ? (
                    <div className="text-[11px] text-n500">読み込み中…</div>
                  ) : (
                    <>
                      <div className="grid grid-cols-2 gap-2 mb-2">
                        <Kpi label="経験者（ユニーク）" value={`${num(detail.count)}人`} meta={`${pct(detail.rate)}（/n=${num(detail.n)}）`} tone="green" />
                        <Kpi label="平均期間／平均行動数" value={`${num(detail.avg_duration, 1)}日／${num(detail.avg_action_count, 1)}`} />
                      </div>
                      <div className="section-label mb-1">ステップ別発生時期（初回一致位置）</div>
                      <table className="tbl mb-2"><tbody>{detail.step_timing.map((s) => (<tr key={s.step}><td>{s.step}. {s.label}</td><td className="num">{days(s.avg_dn)}</td><td className="num">{num(s.n)}人</td></tr>))}</tbody></table>
                      <div className="section-label mb-1">セグメント比較（各セグメントの分母で再計算）</div>
                      <table className="tbl mb-2"><tbody>{detail.segments.map((s) => (<tr key={s.segment}><td>{s.segment}</td><td className="num">{num(s.count)}／{num(s.n)}</td><td className="num">{pct(s.rate)}</td></tr>))}</tbody></table>
                      <div className="section-label mb-1">匿名の実行動例（カテゴリ変換前後）</div>
                      <div className="space-y-2 max-h-[420px] overflow-auto">
                        {detail.examples.map((ex) => (
                          <div key={ex.person} className="border border-n150 rounded p-2 text-[10.5px]">
                            <div className="font-bold text-n800 mb-1">{ex.person}｜{ex.age_group}・{ex.purchase_status}・{ex.duration_days}日・{ex.action_count}行動</div>
                            <ol className="space-y-0.5">
                              {ex.sequence.map((s, i) => {
                                const hit = ex.matched_positions?.includes(i);
                                return (
                                  <li key={s.step} className={`flex gap-2 ${hit ? "bg-accent-bg rounded px-1" : ""}`}>
                                    <span className="text-n500 w-7">{s.step}.</span>
                                    <span className="text-n500 w-10">D−{s.dn}</span>
                                    <span className="text-n900">{s.variable}<span className="text-n500">（{s.repeat}回目）</span></span>
                                    <span className="text-accent ml-auto whitespace-nowrap">{s.label}</span>
                                  </li>
                                );
                              })}
                            </ol>
                          </div>
                        ))}
                      </div>
                      <div className="mt-2"><Callout>匿名例は個票の行番号ベースの仮IDで表示しています。実行動例の位置ハイライトは選択パスの初回一致箇所です。</Callout></div>
                    </>
                  )}
                </Card>
              )}
            </div>
          </>
        )}
      </StateBox>
    </>
  );
}
