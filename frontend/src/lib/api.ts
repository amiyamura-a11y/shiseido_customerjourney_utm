import type { Filters, GraphResponse, Meta } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { ...init, headers: { "content-type": "application/json", ...(init?.headers || {}) }, cache: "no-store" });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  meta: () => request<Meta>("/api/meta"),
  health: () => request<{ ok: boolean; error: string | null }>("/api/health"),
  overview: (filters: Filters) => request<OverviewResponse>("/api/overview", { method: "POST", body: JSON.stringify({ filters }) }),
  graph: (body: GraphRequestBody) => request<GraphResponse>("/api/paths/graph", { method: "POST", body: JSON.stringify(body) }),
  compare: (body: CompareRequestBody) => request<CompareResponse>("/api/paths/compare", { method: "POST", body: JSON.stringify(body) }),
  entry: (body: EntryRequestBody) => request<EntryResponse>("/api/paths/entry", { method: "POST", body: JSON.stringify(body) }),
  entryOptions: (granularity: string) => request<{ options: { value: string; label: string; group: string }[] }>(`/api/paths/entry/options?granularity=${granularity}`),
  search: (body: SearchRequestBody) => request<SearchResponse>("/api/paths/search", { method: "POST", body: JSON.stringify(body) }),
  detail: (body: { filters: Filters; path: string[]; examples?: number }) => request<DetailResponse>("/api/paths/detail", { method: "POST", body: JSON.stringify(body) }),
  timeline: (filters: Filters, top_n = 15) => request<TimelineResponse>("/api/timeline", { method: "POST", body: JSON.stringify({ filters, top_n }) }),
  labels: (granularity: string) => request<{ labels: string[] }>(`/api/labels?granularity=${granularity}`),
  insights: (body: InsightRequestBody) => request<InsightResponse>("/api/insights", { method: "POST", body: JSON.stringify(body) }),
  observedLabels: (filters: Filters) => request<{ labels: string[]; base_labels: string[] }>("/api/labels", { method: "POST", body: JSON.stringify({ filters }) }),
  groupsPreview: (filters: Filters) => request<{ groups: Record<string, { variables: number; events: number; persons: number }>; candidates: { variables: string[]; categories: string[]; broads: string[] } }>("/api/groups/preview", { method: "POST", body: JSON.stringify({ filters }) }),
  dictionary: () => request<DictionaryResponse>("/api/dictionary"),
  validation: () => request<ValidationResponse>("/api/validation"),
  reload: () => request<Meta>("/api/reload?force=true", { method: "POST" }),
  clearCache: () => request<{ ok: boolean }>("/api/cache/clear", { method: "POST" }),
  upload: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    const j = await res.json();
    if (!res.ok) throw new ApiError(res.status, typeof j.detail === "string" ? j.detail : JSON.stringify(j));
    return j as { ok: boolean; saved_to: string; role: string | null; message?: string; meta?: Meta };
  },
};

export interface GraphRequestBody {
  filters: Filters;
  steps: number;
  mode: "head" | "tail" | "anchor" | "full";
  anchor?: string | null;
  anchor_occurrence?: "first" | "last";
  top_n: number;
  min_count: number;
  min_rate: number;
  show_other: boolean;
  other_mode?: "show" | "hide" | "exclude";
  selected_nodes: { step: number; label: string }[];
  selected_edges: { step: number; source: string; target: string }[];
  include_rankings?: boolean;
}

export interface CompareRequestBody {
  a: Filters;
  b: Filters;
  label_a: string;
  label_b: string;
  steps: number;
  mode: string;
  anchor?: string | null;
  top_n: number;
  min_count: number;
  show_other: boolean;
  other_mode?: "show" | "hide" | "exclude";
}

export interface CompareResponse {
  label_a: string;
  label_b: string;
  graph_a: GraphResponse;
  graph_b: GraphResponse;
  node_order: Record<string, string[]>;
  scale: { max_count: number; max_rate: number };
  summary: { n_a: number; n_b: number; avg_action_count_a: number | null; avg_action_count_b: number | null; avg_duration_a: number | null; avg_duration_b: number | null };
  experience_rows: { label: string; count_a: number; count_b: number; rate_a: number | null; rate_b: number | null; diff_pt: number | null; ratio: number | null; avg_dn_a: number | null; avg_dn_b: number | null; small_cell: boolean }[];
  edge_rows: { step: number; source: string; target: string; count_a: number; den_a: number; rate_a: number; count_b: number; den_b: number; rate_b: number; diff_pt: number | null; small_cell: boolean }[];
  path_rows: Record<string, { note: string | null; rows: { path: string[]; count_a: number; count_b: number; rate_a: number | null; rate_b: number | null; diff_pt: number | null; ratio: number | null; small_cell: boolean }[] }>;
  filters_a: Record<string, unknown>;
  filters_b: Record<string, unknown>;
  caveats: string[];
}

export interface EntryRequestBody {
  filters: Filters;
  anchor: string;
  steps: number;
  occurrence: "first" | "last" | "all";
  follow: "next" | "next_in_category" | "within_days";
  target_category?: string | null;
  within_days?: number;
  top_n?: number;
}

export interface EntryRow {
  path: string[];
  count: number;
  events: number;
  rate_of_parent: number | null;
  parent_count: number;
  rate_of_anchor: number | null;
  rate_of_all: number | null;
  avg_dn: number | null;
}

export interface EntryResponse {
  anchor: string;
  n: number;
  anchor_count: number;
  anchor_rate: number | null;
  anchor_events: number;
  occurrence: string;
  follow: string;
  levels: { depth: number; rows: EntryRow[] }[];
  filters: Record<string, unknown>;
  notes: string[];
  denominators: Record<string, string>;
}

export interface SearchRequestBody {
  filters: Filters;
  start?: string | null;
  end?: string | null;
  via: string[];
  min_steps: number;
  max_steps: number;
  min_count: number;
  limit: number;
  sort: string;
}

export interface SearchRow {
  path: string[];
  path_str: string;
  steps: number;
  count: number;
  rate: number | null;
  occurrences: number;
  buyer_count: number;
  buyer_rate: number | null;
  nonbuyer_count: number;
  nonbuyer_rate: number | null;
  diff_pt: number | null;
  ratio: number | null;
  avg_duration: number | null;
  avg_action_count: number | null;
  small_cell: boolean;
}

export interface SearchResponse {
  n: number;
  buyer_n: number;
  nonbuyer_n: number;
  total_matches: number;
  rows: SearchRow[];
  filters: Record<string, unknown>;
  notes: string[];
  denominators: Record<string, string>;
}

export interface DetailResponse {
  path: string[];
  mode: string;
  n: number;
  count: number;
  rate: number | null;
  avg_duration: number | null;
  avg_action_count: number | null;
  step_timing: { step: number; label: string; avg_dn: number | null; n: number }[];
  segments: { segment: string; count: number; n: number; rate: number | null }[];
  examples: { person: string; age_group: string; purchase_status: string; duration_days: number; action_count: number; matched_positions: number[] | null; sequence: { step: number; dn: number; variable: string; category: string; label: string; repeat: number }[] }[];
  notes: string[];
}

export interface TimelineResponse {
  n: number;
  labels: string[];
  heatmap: { label: string; total: number; cells: { day: number; count: number; rate: number | null }[] }[];
  daily: { day: number; count: number; rate: number | null }[];
  daily_by_label: Record<string, { day: number; count: number; rate: number | null }[]>;
  window_rankings: { window: string; rows: { label: string; count: number; rate: number | null }[] }[];
  duration_buckets: { bucket: string; n: number; rows: { label: string; count: number; rate: number | null }[] }[];
  notes: string[];
}

export interface OverviewResponse {
  n: number;
  buyers: number;
  nonbuyers: number;
  by_age: Record<string, number>;
  by_age_result: Record<string, { buyers: number; nonbuyers: number }>;
  action_count: { mean: number | null; median: number | null };
  duration_days: { mean: number | null; median: number | null; label: string };
  unique_variables: number;
  unique_categories: number;
  hist_action_count: { bin: number; count: number }[];
  hist_duration: { bin: number; count: number }[];
  journey_type_share: { type: string; count: number; rate: number | null }[];
  start_period_share: { period: string; count: number; rate: number | null }[];
  category_table: { label: string; count: number; rate: number | null; events: number; avg_dn: number | null; buyer_count: number; buyer_rate: number | null; nonbuyer_count: number; nonbuyer_rate: number | null; diff_pt: number | null; ratio: number | null; small_cell: boolean }[];
  category_table_denominators: { all: number; buyers: number; nonbuyers: number };
  notes: string[];
  quality: Record<string, unknown>;
  expected: Record<string, number>;
}

export interface DictionaryResponse {
  source: Record<string, unknown>;
  table: { individual_variable: string; analysis_category: string; broad_category: string; events: number; persons: number; in_csv: boolean }[];
  categories: string[];
  broad_categories: string[];
  mismatches: { kind: string; defined_name: string; sheet: string; reason: string; master_variable: string | null }[];
  processing_summary: Record<string, unknown>;
  quality: Record<string, unknown>;
  inputs: Meta["inputs"];
  loaded_at: string | null;
}

export interface ValidationResponse {
  rows: { section: string; segment: string; item: string; excel: number | null; recalc: number | null; diff: number | null; denominator: number | null; definition: string; match: boolean; reason: string }[];
  summary: { total: number; match: number; mismatch: number };
  implied_prior: { formula?: string; implied_prior_by_age?: Record<string, { prior: number; min: number; max: number; rows: number }>; note?: string };
}

export interface InsightRequestBody {
  page: string;
  filters: Filters;
  steps?: number;
  mode?: string;
  anchor?: string | null;
  top_n?: number;
  other_mode?: string;
  entry_anchor?: string | null;
  compare_a?: Filters | null;
  compare_b?: Filters | null;
  label_a?: string;
  label_b?: string;
}

export interface InsightResponse {
  sections: { title: string; paragraphs: string[] }[];
  caveat: string;
  basis: Record<string, unknown>;
}
