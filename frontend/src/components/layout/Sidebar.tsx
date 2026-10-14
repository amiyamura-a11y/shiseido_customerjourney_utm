"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Route, Columns2, Clock, Flag, Search, BookOpen } from "lucide-react";

export const NAV = [
  { href: "/overview", idx: "01", label: "データ概観", icon: LayoutDashboard },
  { href: "/golden-path", idx: "02", label: "Golden Path", icon: Route },
  { href: "/compare", idx: "03", label: "パス比較", icon: Columns2 },
  { href: "/timeline", idx: "04", label: "時系列分析", icon: Clock },
  { href: "/entry", idx: "05", label: "起点行動分析", icon: Flag },
  { href: "/search", idx: "06", label: "パス詳細探索", icon: Search },
  { href: "/dictionary", idx: "07", label: "データ・変数定義", icon: BookOpen },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-[220px] shrink-0 bg-white border-r border-n150 flex flex-col h-screen sticky top-0">
      <div className="px-4 py-4 border-b border-n100">
        <div className="section-label !text-accent">ULTIMUNE</div>
        <div className="text-[14px] font-bold text-n1250 leading-tight">Journey Analytics</div>
        <div className="text-[10px] text-n500 mt-1">Customer Journey & Golden Path</div>
      </div>
      <nav className="p-2 flex flex-col gap-0.5">
        {NAV.map((n) => {
          const active = path?.startsWith(n.href);
          const Icon = n.icon;
          return (
            <Link key={n.href} href={n.href} className={`side-item ${active ? "active" : ""}`}>
              <span className="idx">{n.idx}</span>
              <Icon size={14} />
              <span>{n.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto p-3 text-[10px] text-n500 border-t border-n100">
        <div>集計は個票CSVから都度再計算</div>
        <div>推計値・ダミー値は使用していません</div>
      </div>
    </aside>
  );
}
