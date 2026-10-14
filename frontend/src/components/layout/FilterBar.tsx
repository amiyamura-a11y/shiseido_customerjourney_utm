"use client";
import { RotateCcw } from "lucide-react";
import { useFilters } from "@/store/filters";
import { Field, Segmented } from "@/components/ui/primitives";
import type { Age, Dedupe, DurationPreset, Granularity, PathMode, Result, TimingPreset } from "@/lib/types";

export function FilterBar({ show = {} }: { show?: Partial<Record<"timing" | "granularity" | "dedupe" | "pathMode", boolean>> }) {
  const { filters, setFilters, resetFilters } = useFilters();
  const s = { timing: true, granularity: true, dedupe: true, pathMode: true, ...show };
  return (
    <div className="card px-4 py-3 mb-3">
      <div className="flex flex-wrap gap-x-5 gap-y-3 items-end">
        <Field label="年代">
          <Segmented<Age> value={filters.age} onChange={(v) => setFilters({ age: v })} options={[{ value: "all", label: "全体" }, { value: "18-29", label: "18–29歳" }, { value: "30-49", label: "30–49歳" }]} />
        </Field>
        <Field label="結果">
          <Segmented<Result> value={filters.result} onChange={(v) => setFilters({ result: v })} options={[{ value: "buyer", label: "購入者" }, { value: "nonbuyer", label: "非購入者" }, { value: "all", label: "全体" }]} />
        </Field>
        <Field label="人の期間（観測期間）">
          <div className="flex items-center gap-1">
            <Segmented<DurationPreset> value={filters.duration_preset} onChange={(v) => setFilters({ duration_preset: v })} options={[{ value: "all", label: "全期間" }, { value: "0-7", label: "0–7日" }, { value: "8-14", label: "8–14日" }, { value: "15-21", label: "15–21日" }, { value: "22-30", label: "22–30日" }, { value: "custom", label: "カスタム" }]} />
            {filters.duration_preset === "custom" && (
              <>
                <input className="ctl w-14" type="number" min={0} max={365} value={filters.duration_min ?? ""} onChange={(e) => setFilters({ duration_min: e.target.value === "" ? null : Number(e.target.value) })} />
                <span className="text-n500">〜</span>
                <input className="ctl w-14" type="number" min={0} max={365} value={filters.duration_max ?? ""} onChange={(e) => setFilters({ duration_max: e.target.value === "" ? null : Number(e.target.value) })} />
                <span className="text-[10px] text-n500">日</span>
              </>
            )}
          </div>
        </Field>
        {s.timing && (
          <Field label="行動発生時期（D−n）">
            <div className="flex items-center gap-1">
              <Segmented<TimingPreset> value={filters.timing_preset} onChange={(v) => setFilters({ timing_preset: v })} options={[{ value: "all", label: "全期間" }, { value: "30-15", label: "D−30〜15" }, { value: "14-8", label: "D−14〜8" }, { value: "7-0", label: "D−7〜0" }, { value: "custom", label: "カスタム" }]} />
              {filters.timing_preset === "custom" && (
                <>
                  <span className="text-[10px] text-n500">D−</span>
                  <input className="ctl w-14" type="number" min={0} max={365} value={filters.timing_max ?? ""} onChange={(e) => setFilters({ timing_max: e.target.value === "" ? null : Number(e.target.value) })} />
                  <span className="text-n500">〜 D−</span>
                  <input className="ctl w-14" type="number" min={0} max={365} value={filters.timing_min ?? ""} onChange={(e) => setFilters({ timing_min: e.target.value === "" ? null : Number(e.target.value) })} />
                </>
              )}
            </div>
          </Field>
        )}
        {s.granularity && (
          <Field label="粒度">
            <Segmented<Granularity> value={filters.granularity} onChange={(v) => setFilters({ granularity: v })} options={[{ value: "variable", label: "個別変数" }, { value: "category", label: "分析カテゴリ" }, { value: "broad", label: "大分類" }]} />
          </Field>
        )}
        {s.pathMode && (
          <Field label="パス定義">
            <Segmented<PathMode> value={filters.path_mode} onChange={(v) => setFilters({ path_mode: v })} options={[{ value: "consecutive", label: "連続パス", title: "A→B は隣接遷移" }, { value: "ordered", label: "順序保持パス", title: "A→B は間に他行動を挟んでもよい順序" }]} />
          </Field>
        )}
        {s.dedupe && (
          <Field label="同一行動">
            <Segmented<Dedupe> value={filters.dedupe} onChange={(v) => setFilters({ dedupe: v })} options={[{ value: "keep_all", label: "すべて保持" }, { value: "collapse_consecutive", label: "連続重複統合" }, { value: "first_only", label: "初回のみ" }]} />
          </Field>
        )}
        <button type="button" className="btn btn-sm ml-auto" onClick={resetFilters} title="共通フィルタをリセット">
          <RotateCcw size={12} /> リセット
        </button>
      </div>
    </div>
  );
}
