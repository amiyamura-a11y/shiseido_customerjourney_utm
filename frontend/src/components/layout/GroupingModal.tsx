"use client";
import { useEffect, useMemo, useState } from "react";
import { X, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Filters, GroupRule, MatchType } from "@/lib/types";
import { Button, Segmented } from "@/components/ui/primitives";

const EMPTY: GroupRule = { name: "", enabled: true, members: [], match_type: "select", pattern: "", dn_min: null, dn_max: null };

export function timingPresetGroups(): GroupRule[] {
  return [
    { ...EMPTY, name: "D−30〜15の行動", match_type: "prefix", pattern: "", dn_min: 15, dn_max: 30, members: [] },
    { ...EMPTY, name: "D−14〜8の行動", match_type: "prefix", pattern: "", dn_min: 8, dn_max: 14, members: [] },
    { ...EMPTY, name: "D−7〜0の行動", match_type: "prefix", pattern: "", dn_min: 0, dn_max: 7, members: [] },
  ].map((g) => ({ ...g, match_type: "regex", pattern: "." }));
}

export function GroupingModal({ filters, onApply, onClose }: { filters: Filters; onApply: (patch: Partial<Filters>) => void; onClose: () => void }) {
  const [groups, setGroups] = useState<GroupRule[]>(filters.groups.length ? filters.groups.map((g) => ({ ...g })) : [{ ...EMPTY, name: "グループ1" }]);
  const [enabled, setEnabled] = useState(filters.grouping_enabled);
  const [collapse, setCollapse] = useState(filters.collapse_groups);
  const [showRepeat, setShowRepeat] = useState(filters.show_repeat);
  const [cands, setCands] = useState<{ variables: string[]; categories: string[]; broads: string[] }>({ variables: [], categories: [], broads: [] });
  const [preview, setPreview] = useState<Record<string, { variables: number; events: number; persons: number }>>({});
  const [q, setQ] = useState<Record<number, string>>({});

  useEffect(() => {
    const t = setTimeout(() => {
      api.groupsPreview({ ...filters, groups, grouping_enabled: true }).then((r) => { setPreview(r.groups); setCands(r.candidates); }).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [groups, filters]);

  const upd = (i: number, patch: Partial<GroupRule>) => setGroups((gs) => gs.map((g, j) => (j === i ? { ...g, ...patch } : g)));
  const candidates = useMemo(() => [...cands.categories.map((c) => ({ v: c, g: "分析カテゴリ" })), ...cands.broads.map((c) => ({ v: c, g: "大分類" })), ...cands.variables.map((c) => ({ v: c, g: "個別変数" }))], [cands]);

  return (
    <div className="fixed inset-0 z-40 bg-black/30 flex items-start justify-center overflow-auto py-8" onClick={onClose}>
      <div className="card w-[820px] max-w-[95vw]" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between px-4 pt-3 pb-2 border-b border-n100">
          <div>
            <div className="card-title">変数の統合・グルーピング設定</div>
            <div className="card-sub">任意の行動（個別変数・分析カテゴリ・大分類・名前パターン・D−n範囲）を1つの名前に括って分析します。統合後のラベルは全ページの集計に反映されます。</div>
          </div>
          <button className="btn btn-sm" onClick={onClose}><X size={12} /></button>
        </div>
        <div className="px-4 py-3 space-y-3">
          <div className="flex flex-wrap gap-4 items-center text-[11.5px]">
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> 変数統合: {enabled ? "有効" : "無効"}</label>
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={collapse} onChange={(e) => setCollapse(e.target.checked)} /> 連続する同一グループを1つに集約</label>
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={showRepeat} onChange={(e) => setShowRepeat(e.target.checked)} /> 表示名に回数（n回目）を含める</label>
            <span className="ml-auto text-n500">プリセット:</span>
            <Button size="sm" onClick={() => setGroups(timingPresetGroups())}>D−n日数帯で分類</Button>
            <Button size="sm" onClick={() => setGroups([{ ...EMPTY, name: "グループ1" }])}>初期化</Button>
          </div>
          {groups.map((g, i) => {
            const pv = preview[g.name];
            const query = q[i] ?? "";
            const list = query ? candidates.filter((c) => c.v.toLowerCase().includes(query.toLowerCase())).slice(0, 40) : [];
            return (
              <div key={i} className="border border-n150 rounded-[var(--r)] p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <input type="checkbox" checked={g.enabled} onChange={(e) => upd(i, { enabled: e.target.checked })} />
                  <input className="ctl w-64" placeholder="グループ名（例: サイト行動）" value={g.name} onChange={(e) => upd(i, { name: e.target.value })} />
                  <span className="chip chip-neutral">{pv ? `該当: ${pv.variables} 変数 / ${pv.events.toLocaleString()} 行動 / ${pv.persons.toLocaleString()} 人` : "該当: –"}</span>
                  <button className="btn btn-sm ml-auto" onClick={() => setGroups((gs) => gs.filter((_, j) => j !== i))}><Trash2 size={12} /></button>
                </div>
                <div className="flex flex-wrap gap-4 items-end">
                  <div className="flex flex-col gap-1">
                    <span className="ctl-label">一致方式</span>
                    <Segmented<MatchType> value={g.match_type} onChange={(v) => upd(i, { match_type: v })} options={[{ value: "select", label: "変数を選択" }, { value: "prefix", label: "前方一致" }, { value: "contains", label: "部分一致" }, { value: "regex", label: "正規表現" }]} size="sm" />
                  </div>
                  {g.match_type !== "select" && (
                    <div className="flex flex-col gap-1">
                      <span className="ctl-label">名前パターン（個別変数名に適用）</span>
                      <input className="ctl w-72" placeholder={g.match_type === "prefix" ? "例: 外部サイト_大衆向けEC" : g.match_type === "contains" ? "例: 資生堂" : "例: ^検索_(効能|成分)"} value={g.pattern} onChange={(e) => upd(i, { pattern: e.target.value })} />
                    </div>
                  )}
                  <div className="flex flex-col gap-1">
                    <span className="ctl-label">D−n 範囲（任意）</span>
                    <div className="flex items-center gap-1 text-[11px]">D−<input className="ctl w-14" type="number" min={0} max={30} value={g.dn_max ?? ""} onChange={(e) => upd(i, { dn_max: e.target.value === "" ? null : Number(e.target.value) })} /> 〜 D−<input className="ctl w-14" type="number" min={0} max={30} value={g.dn_min ?? ""} onChange={(e) => upd(i, { dn_min: e.target.value === "" ? null : Number(e.target.value) })} /></div>
                  </div>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="ctl-label">統合する変数（検索して追加。個別変数・分析カテゴリ・大分類を混在可）</span>
                  <div className="relative">
                    <input className="ctl w-full" placeholder="名前で検索…" value={query} onChange={(e) => setQ({ ...q, [i]: e.target.value })} />
                    {list.length > 0 && (
                      <div className="absolute z-10 left-0 right-0 card max-h-56 overflow-auto shadow-lg">
                        {list.map((c) => (
                          <div key={c.g + c.v} className="px-2 py-1 text-[11px] hover:bg-n50 cursor-pointer flex justify-between" onClick={() => { if (!g.members.includes(c.v)) upd(i, { members: [...g.members, c.v] }); setQ({ ...q, [i]: "" }); }}>
                            <span>{c.v}</span><span className="text-n400">{c.g}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1 min-h-[22px]">
                    {g.members.map((m) => (
                      <span key={m} className="chip chip-neutral cursor-pointer" title="クリックで削除" onClick={() => upd(i, { members: g.members.filter((x) => x !== m) })}>{m} ×</span>
                    ))}
                    {g.members.length === 0 && g.match_type === "select" && <span className="text-[10.5px] text-n500">未選択</span>}
                  </div>
                </div>
              </div>
            );
          })}
          <button className="btn w-full justify-center" onClick={() => setGroups((gs) => [...gs, { ...EMPTY, name: `グループ${gs.length + 1}` }])}><Plus size={12} /> 新しいグループを追加</button>
        </div>
        <div className="flex items-center justify-between px-4 py-3 border-t border-n100 text-[11px] text-n600">
          <span>{groups.filter((g) => g.enabled && g.name.trim()).length} 件の統合ルール{enabled ? "が適用されます" : "（統合は無効）"}。ルールは上から順に評価され、最初に一致したグループ名になります。</span>
          <div className="flex gap-2">
            <Button onClick={onClose}>キャンセル</Button>
            <Button variant="primary" onClick={() => { onApply({ groups: groups.filter((g) => g.name.trim()), grouping_enabled: enabled, collapse_groups: collapse, show_repeat: showRepeat }); onClose(); }}>統合設定を適用</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
