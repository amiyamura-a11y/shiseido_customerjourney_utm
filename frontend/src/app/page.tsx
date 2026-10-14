"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/golden-path");
  }, [router]);
  return <div className="text-[11.5px] text-n500 p-4">Golden Path へ移動しています…</div>;
}
