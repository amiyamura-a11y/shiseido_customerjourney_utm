export type Age = "all" | "18-29" | "30-49";
export type Result = "all" | "buyer" | "nonbuyer";
export type DurationPreset = "all" | "0-7" | "8-14" | "15-21" | "22-30" | "custom";
export type TimingPreset = "all" | "30-15" | "14-8" | "7-0" | "custom";
export type Granularity = "variable" | "category" | "broad";
export type Dedupe = "keep_all" | "collapse_consecutive" | "first_only";
export type PathMode = "consecutive" | "ordered";

export type MatchType = "select" | "prefix" | "contains" | "regex";

export interface GroupRule {
  name: string;
  enabled: boolean;
  members: string[];
  match_type: MatchType;
  pattern: string;
  dn_min: number | null;
  dn_max: number | null;
}

export interface Filters {
  age: Age;
  result: Result;
  duration_preset: DurationPreset;
  duration_min: number | null;
  duration_max: number | null;
  timing_preset: TimingPreset;
  timing_min: number | null;
  timing_max: number | null;
  granularity: Granularity;
  dedupe: Dedupe;
  path_mode: PathMode;
  groups: GroupRule[];
  grouping_enabled: boolean;
  collapse_groups: boolean;
  show_repeat: boolean;
  exclude_labels: string[];
}

export interface GraphNode {
  id: string;
  step: number;
  label: string;
  kind: "action" | "other" | "outcome";
  count: number;
  rate: number | null;
  share_of_step: number | null;
  share_of_selection: number | null;
  buyers: number;
  nonbuyers: number;
  avg_dn: number | null;
  members: { label: string; count: number }[] | null;
  small_cell: boolean;
}

export interface GraphEdge {
  id: string;
  step: number;
  source: string;
  target: string;
  source_label: string;
  target_label: string;
  count: number;
  denominator: number;
  rate: number | null;
  rate_of_filtered: number | null;
  small_cell: boolean;
}

export interface GraphResponse {
  n: number;
  n_placed: number;
  n_in_graph: number;
  steps: number;
  mode: string;
  anchor: string | null;
  columns: { step: number; label: string; reached: number }[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  selection: null | {
    count: number;
    rate_of_filtered: number | null;
    denominator: number;
    buyers: number;
    nonbuyers: number;
    path_definition: string;
    selected_nodes: { step: number; label: string }[];
    selected_edges: { step: number; source: string; target: string }[];
    avg_action_count: number | null;
    avg_duration_days: number | null;
  };
  filters: Record<string, unknown>;
  notes: string[];
  denominators: Record<string, string>;
  censoring: { more_actions: number; buy: number; nonbuy_end: number };
  rankings?: {
    denominator: number;
    top_paths: Record<string, { note: string | null; rows: { path: string[]; count: number; rate: number | null; occurrences: number }[] }>;
    buyer_characteristic: Record<string, { note: string | null; buyer_n: number; nonbuyer_n: number; caveat: string; rows: { path: string[]; buyer_count: number; buyer_rate: number | null; nonbuyer_count: number; nonbuyer_rate: number | null; diff_pt: number | null; ratio: number | null; small_cell: boolean }[] }>;
  };
  _timing_ms?: number;
}

export interface Meta {
  app: string;
  loaded_at: string | null;
  error: string | null;
  inputs: Record<string, { role: string; name: string | null; path: string | null; exists: boolean; size_bytes: number; modified: string | null; note: string }>;
  summary: { persons: number; buyers: number; nonbuyers: number; events: number; variables: number; categories: number } | null;
  quality: Record<string, unknown> | null;
  data_dir: string;
}
