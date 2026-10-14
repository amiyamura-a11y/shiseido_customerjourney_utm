"use client";
import { useEffect, useState } from "react";
import { Lightbulb } from "lucide-react";
import { api, type InsightRequestBody, type InsightResponse } from "@/lib/api";

/** 考察ボックス: 個票から再計算した数値のみで文章を生成する（ページ上段に表示）。 */
export function InsightBox({ request }: { request: InsightRequestBody }) {
  const [data, setData] = useState<InsightResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const key = JSON.stringify(request);
  useEffect(() => {
    let c = false;
    setState("loading");
    const t = setTimeout(() => {
      api.insights(JSON.parse(key)).then((d) => { if (c) return; setData(d); setState("ready"); }).catch(() => { if (!c) setState("error"); });
    }, 200);
    return () => { c = true; clearTimeout(t); };
  }, [key]);
  return (
    <div className="card mb-3 border-l-4 !border-l-accent">
      <div className="flex items-start justify-between gap-3 px-4 pt-3 pb-2 border-b border-n100">
        <div className="flex items-center gap-2">
          <Lightbulb size={14} className="text-accent" />
          <div>
            <div className="card-title">考察（年代別購入者の特徴）</div>
            <div className="card-sub">共通フィルタ条件の下で、各年代の購入者を同年代の非購入者と比較して自動生成</div>
          </div>
        </div>
        {state === "loading" && <span className="text-[10.5px] text-n500">集計中…</span>}
      </div>
      <div className="px-4 py-3">
        {state === "error" && <div className="text-[11px] text-[#9a3412]">考察を生成できませんでした。</div>}
        {data && (
          <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${Math.min(3, Math.max(1, data.sections.length))}, minmax(0, 1fr))` }}>
            {data.sections.map((s) => (
              <div key={s.title} className="bg-n25 border border-n100 rounded-[var(--r)] px-3 py-2">
                <div className="section-label mb-1 !text-accent">{s.title}</div>
                <div className="space-y-1 text-[11.5px] leading-relaxed text-n900">
                  {s.paragraphs.map((p, i) => (<p key={i}>{p}</p>))}
                </div>
              </div>
            ))}
          </div>
        )}
        {data && <div className="mt-2 text-[10px] text-n500">{data.caveat}</div>}
      </div>
    </div>
  );
}
