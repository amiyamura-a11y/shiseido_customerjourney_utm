import { Sidebar } from "./Sidebar";
import type { ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 min-w-0 px-5 py-4">{children}</main>
    </div>
  );
}
