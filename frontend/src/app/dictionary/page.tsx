"use client";
import { useEffect, useRef, useState } from "react";
import { RefreshCw, Upload, Trash2 } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { InsightBox } from "@/components/ui/InsightBox";
import { DEFAULT_FILTERS } from "@/store/filters";
import { Button, Callout, Card, Chip, Kpi, StateBox } from "@/components/ui/primitives";
import { DataTable } from "@/components/ui/DataTable";
import { api, ApiError, type DictionaryResponse, type ValidationResponse } from "@/lib/api";
import { num, pct } from "@/lib/format";

export default function DictionaryPage() {
  const [data, setData] = useState<DictionaryResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationResponse | null>(null);
  const [vstate, setVstate] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [msg, setMsg] = useState<string | null>(null);
  const [filterText, setFilterText] = useState("");
  const [sectionFilter, setSectionFilter] = useState("all");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => {
    setState("loading");
    api.dictionary().then((d) => { setData(d); setState("ready"); }).catch((e) => { setError(e instanceof ApiError ? e.message : String(e)); setState("error"); });
  };
  useEffect(load, []);
  const loadValidation = () => {
    setVstate("loading");
    api.validation().then((v) => { setValidation(v); setVstate("ready"); }).catch(() => setVstate("error"));
  };
  const reload = async () => { setMsg("再読み込み中…"); try { await api.reload(); setMsg("再読み込み完了"); load(); setValidation(null); setVstate("idle"); } catch (e) { setMsg(`再読み込み失敗: ${e instanceof ApiError ? e.message : String(e)}`); } };
  const clearCache = async () => { await api.clearCache(); setMsg("集計キャッシュを無効化しました"); setValidation(null); setVstate("idle"); };
  const upload = async (f: File) => { setMsg(`アップロード中: ${f.name}`); try { const r = await api.upload(f); setMsg(r.ok ? `読み込み完了: ${r.saved_to}（${r.role}）` : `保存のみ: ${r.message}`); load(); } catch (e) { setMsg(`失敗: ${e instanceof ApiError ? e.message : String(e)}`); } };

  const q = (data?.quality ?? {}) as Record<string, unknown>;
  const sections = validation ? Array.from(new Set(validation.rows.map((r) => r.section))) : [];
  const vrows = (validation?.rows ?? []).filter((r) => (sectionFilter === "all" || r.section === sectionFilter) && (!filterText || r.item.includes(filterText) || r.segment.includes(filterText)));

  return (
    <>
      <Header title="データ・変数定義" sub="入力ファイル・読み込み状況・個別変数→分析カテゴリ→大分類の対応表・未分類／不一致・品質検査・既存Excel照合" actions={<div className="flex gap-1"><Button size="sm" onClick={reload}><RefreshCw size={12} /> 再読み込み</Button><Button size="sm" onClick={clearCache}><Trash2 size={12} /> キャッシュ無効化</Button><Button size="sm" variant="primary" onClick={() => fileRef.current?.click()}><Upload size={12} /> CSV/Excelアップロード</Button><input ref={fileRef} type="file" accept=".csv,.xlsx" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} /></div>} />
      <InsightBox request={{ page: "dictionary", filters: DEFAULT_FILTERS }} />
      {msg && <div className="mb-3"><Callout>{msg}</Callout></div>}
      <StateBox state={state} error={error}>
        {data && (
          <>
            <Card title="入力ファイル" sub={`データディレクトリ内の検出結果。元ファイルは上書きしません（アップロードは data/uploads に保存）。読み込み: ${data.loaded_at ?? "–"}`} className="mb-3">
              <table className="tbl">
                <thead><tr><th>役割</th><th>ファイル名</th><th>状態</th><th className="num">サイズ</th><th>更新日時</th><th>備考</th></tr></thead>
                <tbody>
                  {Object.values(data.inputs).map((f) => (
                    <tr key={f.role}><td>{f.role}</td><td>{f.name ?? "–"}</td><td>{f.exists ? <Chip kind="ok">検出</Chip> : <Chip kind="err">未検出</Chip>}</td><td className="num">{f.size_bytes ? `${(f.size_bytes / 1024 / 1024).toFixed(2)} MB` : "–"}</td><td>{f.modified ?? "–"}</td><td>{f.note}</td></tr>
                  ))}
                </tbody>
              </table>
            </Card>
            <div className="grid grid-cols-6 gap-2.5 mb-3">
              <Kpi label="文字コード" value={String(q.encoding ?? "–")} />
              <Kpi label="行数／イベント数" value={`${num(q.rows as number)}／${num(q.events as number)}`} tone="green" />
              <Kpi label="列マッピング" value={Object.keys((q.column_mapping as Record<string, string>) ?? {}).length + " 列"} meta={Object.entries((q.column_mapping as Record<string, string>) ?? {}).map(([k, v]) => (k === v ? k : `${v}→${k}`)).join(", ")} />
              <Kpi label="マスタ変数数" value={num(data.table.length)} meta={`${data.categories.length} 分析カテゴリ／${data.broad_categories.length} 大分類`} tone="cyan" />
              <Kpi label="未分類変数" value={num(((q.unmapped_variables as string[]) ?? []).length)} meta={`${num(q.unmapped_events as number)} イベント`} />
              <Kpi label="定義不一致（06 Excel）" value={num(data.mismatches.length)} meta="マスタは上書きしない" />
            </div>
            <Card title="変数対応表（個別変数 → 分析カテゴリ → 大分類）" sub={`元シート: ${String(data.source.file ?? "")} / ${String(data.source.master_sheet ?? "")}（列: ${String(data.source.variable_column ?? "")} → ${String(data.source.category_column ?? "")}）。大分類ルール: ${String(data.source.broad_rule ?? "")}`} className="mb-3">
              <DataTable
                rows={data.table}
                rowKey={(r) => r.individual_variable}
                exportName="dictionary.csv"
                maxHeight={460}
                pageSize={60}
                columns={[
                  { key: "v", header: "個別変数", value: (r) => r.individual_variable },
                  { key: "c", header: "分析カテゴリ", value: (r) => r.analysis_category },
                  { key: "b", header: "大分類", value: (r) => r.broad_category },
                  { key: "p", header: "経験人数", num: true, value: (r) => r.persons },
                  { key: "e", header: "延べ回数", num: true, value: (r) => r.events },
                  { key: "in", header: "CSV出現", render: (r) => (r.in_csv ? <Chip kind="ok">あり</Chip> : <Chip kind="warn">なし</Chip>), value: (r) => (r.in_csv ? 1 : 0) },
                ]}
              />
            </Card>
            <Card title="加工定義Excel（06）との不一致一覧" sub="加工定義から導かれる変数名とマスタの差。表記揺れ・定義のみ・マスタのみ・粒度差を列挙（自動上書きはしません）。" className="mb-3">
              <DataTable
                rows={data.mismatches}
                rowKey={(r, i) => `${r.sheet}-${r.defined_name}-${i}`}
                exportName="dictionary_mismatches.csv"
                maxHeight={360}
                columns={[
                  { key: "k", header: "種別", render: (r) => <Chip kind={r.kind.startsWith("表記") ? "warn" : "neutral"}>{r.kind}</Chip>, value: (r) => r.kind },
                  { key: "n", header: "定義側の名称", value: (r) => r.defined_name },
                  { key: "s", header: "シート", value: (r) => r.sheet },
                  { key: "m", header: "近いマスタ変数", value: (r) => r.master_variable ?? "" },
                  { key: "r", header: "理由", value: (r) => r.reason },
                ]}
              />
            </Card>
            <Card title="既存Excelとの照合レポート" sub="Excel値／再計算値／差分／分母／定義／不一致理由。初回は数秒かかります。" className="mb-3" right={<Button size="sm" onClick={loadValidation} disabled={vstate === "loading"}>{vstate === "loading" ? "照合中…" : "照合を実行"}</Button>}>
              {vstate === "idle" && <div className="text-[11px] text-n500">「照合を実行」で既存Excel（追加集計・パス優先度）と再計算値を突き合わせます。</div>}
              {vstate === "error" && <Callout kind="warn">照合に失敗しました。</Callout>}
              {validation && (
                <>
                  <div className="grid grid-cols-4 gap-2 mb-2">
                    <Kpi label="照合件数" value={num(validation.summary.total)} />
                    <Kpi label="一致" value={num(validation.summary.match)} tone="green" />
                    <Kpi label="不一致（定義差を含む）" value={num(validation.summary.mismatch)} />
                    <Kpi label="推計UTM購買率の推計前提" value={Object.entries(validation.implied_prior.implied_prior_by_age ?? {}).map(([a, v]) => `${a.replace("歳", "")}: p≈${(v.prior * 100).toFixed(2)}%`).join(" / ") || "–"} meta={validation.implied_prior.formula ?? ""} tone="cyan" />
                  </div>
                  {validation.implied_prior.note && <div className="mb-2"><Callout>{validation.implied_prior.note}</Callout></div>}
                  <div className="flex gap-2 mb-2 items-center">
                    <select className="ctl" value={sectionFilter} onChange={(e) => setSectionFilter(e.target.value)}>
                      <option value="all">すべての区分</option>
                      {sections.map((s) => (<option key={s} value={s}>{s}</option>))}
                    </select>
                    <input className="ctl w-60" placeholder="項目・セグメントで絞り込み" value={filterText} onChange={(e) => setFilterText(e.target.value)} />
                    <span className="text-[11px] text-n500">{num(vrows.length)} 件</span>
                  </div>
                  <DataTable
                    rows={vrows}
                    rowKey={(r, i) => `${r.section}-${r.segment}-${r.item}-${i}`}
                    exportName="validation_report.csv"
                    maxHeight={480}
                    pageSize={100}
                    columns={[
                      { key: "sec", header: "区分", value: (r) => r.section },
                      { key: "seg", header: "セグメント", value: (r) => r.segment },
                      { key: "item", header: "項目", value: (r) => r.item },
                      { key: "xl", header: "Excel値", num: true, render: (r) => (r.section.startsWith("基本件数") || r.section.includes("平均発生時期") ? num(r.excel, 3) : pct(r.excel, 2)), value: (r) => r.excel },
                      { key: "re", header: "再計算値", num: true, render: (r) => (r.section.startsWith("基本件数") || r.section.includes("平均発生時期") ? num(r.recalc, 3) : pct(r.recalc, 2)), value: (r) => r.recalc },
                      { key: "diff", header: "差分", num: true, render: (r) => (r.diff === null ? "–" : r.section.startsWith("基本件数") || r.section.includes("平均発生時期") ? num(r.diff, 3) : `${(r.diff * 100).toFixed(2)}pt`), value: (r) => r.diff },
                      { key: "den", header: "分母", num: true, value: (r) => r.denominator },
                      { key: "def", header: "定義", value: (r) => r.definition },
                      { key: "m", header: "判定", render: (r) => (r.match ? <Chip kind="ok">一致</Chip> : <Chip kind="warn">不一致</Chip>), value: (r) => (r.match ? 1 : 0) },
                      { key: "why", header: "不一致理由", value: (r) => r.reason },
                    ]}
                  />
                </>
              )}
            </Card>
          </>
        )}
      </StateBox>
    </>
  );
}
