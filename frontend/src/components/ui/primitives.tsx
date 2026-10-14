"use client";
import { Loader2, AlertTriangle, Info } from "lucide-react";
import type { ReactNode } from "react";

export function Card({ title, sub, right, children, className = "", bodyClass = "" }: { title?: ReactNode; sub?: ReactNode; right?: ReactNode; children: ReactNode; className?: string; bodyClass?: string }) {
  return (
    <div className={`card ${className}`}>
      {(title || right) && (
        <div className="flex items-start justify-between gap-3 px-4 pt-3 pb-2 border-b border-n100">
          <div>
            {title && <div className="card-title">{title}</div>}
            {sub && <div className="card-sub">{sub}</div>}
          </div>
          {right && <div className="flex items-center gap-2 shrink-0">{right}</div>}
        </div>
      )}
      <div className={`px-4 py-3 ${bodyClass}`}>{children}</div>
    </div>
  );
}

export function Kpi({ label, value, meta, tone = "dark" }: { label: ReactNode; value: ReactNode; meta?: ReactNode; tone?: "dark" | "green" | "cyan" }) {
  return (
    <div className="card px-4 py-3">
      <div className="section-label mb-1">{label}</div>
      <div className={`kpi-value ${tone === "green" ? "green" : tone === "cyan" ? "cyan" : ""}`}>{value}</div>
      {meta && <div className="text-[10.5px] text-n600 mt-1">{meta}</div>}
    </div>
  );
}

export function Segmented<T extends string>({ value, options, onChange, size = "md" }: { value: T; options: { value: T; label: string; title?: string }[]; onChange: (v: T) => void; size?: "sm" | "md" }) {
  return (
    <div className="seg">
      {options.map((o) => (
        <button key={o.value} type="button" title={o.title} className={`${value === o.value ? "active" : ""} ${size === "sm" ? "!h-[24px] !px-2 !text-[10.5px]" : ""}`} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Field({ label, children, className = "" }: { label: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <span className="ctl-label">{label}</span>
      {children}
    </div>
  );
}

export function Select({ value, onChange, options, className = "", placeholder }: { value: string; onChange: (v: string) => void; options: { value: string; label: string; group?: string }[]; className?: string; placeholder?: string }) {
  const groups = new Map<string, { value: string; label: string }[]>();
  for (const o of options) {
    const g = o.group ?? "";
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g)!.push(o);
  }
  return (
    <select className={`ctl ${className}`} value={value} onChange={(e) => onChange(e.target.value)}>
      {placeholder && <option value="">{placeholder}</option>}
      {[...groups.entries()].map(([g, os]) =>
        g ? (
          <optgroup key={g} label={g}>
            {os.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </optgroup>
        ) : (
          os.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))
        ),
      )}
    </select>
  );
}

export function Button({ children, onClick, variant = "default", size = "md", disabled, title, type = "button" }: { children: ReactNode; onClick?: () => void; variant?: "default" | "primary"; size?: "md" | "sm"; disabled?: boolean; title?: string; type?: "button" | "submit" }) {
  return (
    <button type={type} title={title} disabled={disabled} onClick={onClick} className={`btn ${variant === "primary" ? "btn-primary" : ""} ${size === "sm" ? "btn-sm" : ""}`}>
      {children}
    </button>
  );
}

export function Callout({ kind = "note", children }: { kind?: "note" | "insight" | "warn"; children: ReactNode }) {
  if (kind === "insight") return <div className="insight">{children}</div>;
  if (kind === "warn")
    return (
      <div className="note flex gap-2 items-start !bg-[#fff7ed] !border-[#fed7aa] !text-[#9a3412]">
        <AlertTriangle size={13} className="mt-[2px] shrink-0" />
        <div>{children}</div>
      </div>
    );
  return (
    <div className="note flex gap-2 items-start">
      <Info size={13} className="mt-[2px] shrink-0 text-n500" />
      <div>{children}</div>
    </div>
  );
}

export function Notes({ notes }: { notes?: string[] }) {
  if (!notes || notes.length === 0) return null;
  return (
    <Callout>
      <ul className="list-disc pl-4 space-y-0.5">
        {notes.map((n, i) => (
          <li key={i}>{n}</li>
        ))}
      </ul>
    </Callout>
  );
}

export function StateBox({ state, error, empty, children }: { state: "loading" | "error" | "empty" | "ready" | "nodata"; error?: string | null; empty?: string; children?: ReactNode }) {
  if (state === "loading")
    return (
      <div className="flex items-center gap-2 text-n500 text-[11.5px] py-10 justify-center">
        <Loader2 size={14} className="animate-spin" /> 集計中…
      </div>
    );
  if (state === "error")
    return (
      <div className="py-6 flex justify-center">
        <Callout kind="warn">データエラー: {error || "不明なエラー"}</Callout>
      </div>
    );
  if (state === "empty") return <div className="text-center text-n500 text-[11.5px] py-10">{empty || "対象なし（条件に該当する人がいません）"}</div>;
  if (state === "nodata") return <div className="text-center text-n500 text-[11.5px] py-10">計算不可（分母が 0 です）</div>;
  return <>{children}</>;
}

export function Chip({ kind, children }: { kind: "ok" | "warn" | "err" | "neutral"; children: ReactNode }) {
  return <span className={`chip chip-${kind}`}>{children}</span>;
}

export function SmallCell({ flag }: { flag: boolean }) {
  return flag ? <Chip kind="warn">5人未満</Chip> : null;
}
