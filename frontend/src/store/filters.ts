"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Filters } from "@/lib/types";

export const DEFAULT_FILTERS: Filters = {
  age: "all",
  result: "all",
  duration_preset: "all",
  duration_min: null,
  duration_max: null,
  timing_preset: "all",
  timing_min: null,
  timing_max: null,
  granularity: "category",
  dedupe: "keep_all",
  path_mode: "consecutive",
};

export interface GraphSettings {
  steps: number;
  mode: "head" | "tail" | "anchor" | "full";
  anchor: string | null;
  anchor_occurrence: "first" | "last";
  top_n: number;
  min_count: number;
  min_rate: number;
  show_other: boolean;
}

export const DEFAULT_GRAPH: GraphSettings = { steps: 5, mode: "head", anchor: null, anchor_occurrence: "first", top_n: 8, min_count: 0, min_rate: 0, show_other: true };

interface State {
  filters: Filters;
  graph: GraphSettings;
  goldenPathResultInitialised: boolean;
  setFilters: (patch: Partial<Filters>) => void;
  resetFilters: () => void;
  setGraph: (patch: Partial<GraphSettings>) => void;
  markGoldenPathInit: () => void;
  highlightPath: string[] | null;
  setHighlightPath: (p: string[] | null) => void;
}

export const useFilters = create<State>()(
  persist(
    (set) => ({
      filters: DEFAULT_FILTERS,
      graph: DEFAULT_GRAPH,
      goldenPathResultInitialised: false,
      highlightPath: null,
      setFilters: (patch) => set((s) => ({ filters: { ...s.filters, ...patch } })),
      resetFilters: () => set({ filters: DEFAULT_FILTERS, graph: DEFAULT_GRAPH, highlightPath: null }),
      setGraph: (patch) => set((s) => ({ graph: { ...s.graph, ...patch } })),
      markGoldenPathInit: () => set({ goldenPathResultInitialised: true }),
      setHighlightPath: (p) => set({ highlightPath: p }),
    }),
    { name: "utm-journey-filters-v1" },
  ),
);
