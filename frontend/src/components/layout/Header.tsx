"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Meta } from "@/lib/types";
import type { ReactNode } from "react";
import { num } from "@/lib/format";

export function Header({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api.meta().then(setMeta).catch((e) => setErr(String(e.message || e)));
  }, []);
  return (
    <div className="card flex items-start justify-between gap-4 px-4 py-3 mb-3">
      <div>
        <div className="section-label">ULTIMUNE | JOURNEY ANALYTICS</div>
        <div className="text-[16px] font-bold text-n1250 leading-tight">{title}</div>
        {sub && <div className="text-[10.5px] text-n600 mt-0.5">{sub}</div>}
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <div className="text-[10px] text-n500 text-right">
          {meta?.error && <div className="chip chip-err">データ読込エラー: {meta.error}</div>}
          {err && <div className="chip chip-err">API未接続: {err}</div>}
          {meta?.loaded_at && (
            <>
              <div>データ更新: {meta.loaded_at}</div>
              <div>
                {meta.inputs?.csv?.name} ｜ {num(meta.summary?.persons)}人 / {num(meta.summary?.events)}行動
              </div>
            </>
          )}
        </div>
        {actions}
      </div>
    </div>
  );
}
