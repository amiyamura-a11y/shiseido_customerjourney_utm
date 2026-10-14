"use client";
import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Download } from "lucide-react";
import { downloadCsv } from "@/lib/export";
import type { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: string;
  num?: boolean;
  render?: (row: T) => ReactNode;
  value?: (row: T) => string | number | null | undefined;
  sortValue?: (row: T) => number | string | null;
  width?: string;
}

export function DataTable<T>({ rows, columns, rowKey, onRowClick, selectedKey, exportName, exportMeta, maxHeight = 420, pageSize }: { rows: T[]; columns: Column<T>[]; rowKey: (r: T, i: number) => string; onRowClick?: (r: T) => void; selectedKey?: string | null; exportName?: string; exportMeta?: Record<string, unknown>; maxHeight?: number; pageSize?: number }) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);
  const [page, setPage] = useState(0);
  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return rows;
    const sv = col.sortValue ?? col.value ?? (() => null);
    return [...rows].sort((a, b) => {
      const va = sv(a);
      const vb = sv(b);
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      if (typeof va === "number" && typeof vb === "number") return (va - vb) * sort.dir;
      return String(va).localeCompare(String(vb), "ja") * sort.dir;
    });
  }, [rows, sort, columns]);
  const paged = pageSize ? sorted.slice(page * pageSize, (page + 1) * pageSize) : sorted;
  const doExport = () => {
    if (!exportName) return;
    downloadCsv(
      exportName,
      columns.map((c) => c.header),
      sorted.map((r) => columns.map((c) => (c.value ? c.value(r) : ""))),
      exportMeta,
    );
  };
  return (
    <div>
      {exportName && (
        <div className="flex justify-end mb-1">
          <button type="button" className="btn btn-sm" onClick={doExport}>
            <Download size={12} /> CSV
          </button>
        </div>
      )}
      <div className="overflow-auto border border-n150 rounded-[var(--r)]" style={{ maxHeight }}>
        <table className="tbl">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} className={c.num ? "num" : ""} style={{ width: c.width, cursor: c.sortValue || c.value ? "pointer" : "default" }} onClick={() => (c.sortValue || c.value) && setSort((s) => (s?.key === c.key ? { key: c.key, dir: s.dir === 1 ? -1 : 1 } : { key: c.key, dir: -1 }))}>
                  <span className="inline-flex items-center gap-1">
                    {c.header}
                    {sort?.key === c.key && (sort.dir === 1 ? <ArrowUp size={10} /> : <ArrowDown size={10} />)}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="text-center text-n500 py-6">対象なし</td>
              </tr>
            )}
            {paged.map((r, i) => {
              const k = rowKey(r, i);
              return (
                <tr key={k} className={`${onRowClick ? "clickable" : ""} ${selectedKey === k ? "selected" : ""}`} onClick={() => onRowClick?.(r)}>
                  {columns.map((c) => (
                    <td key={c.key} className={c.num ? "num" : ""}>
                      {c.render ? c.render(r) : c.value ? (c.value(r) as ReactNode) : null}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {pageSize && sorted.length > pageSize && (
        <div className="flex items-center justify-end gap-2 mt-1 text-[11px] text-n600">
          <button type="button" className="btn btn-sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>前へ</button>
          <span>{page * pageSize + 1}–{Math.min((page + 1) * pageSize, sorted.length)} / {sorted.length}</span>
          <button type="button" className="btn btn-sm" disabled={(page + 1) * pageSize >= sorted.length} onClick={() => setPage((p) => p + 1)}>次へ</button>
        </div>
      )}
    </div>
  );
}
