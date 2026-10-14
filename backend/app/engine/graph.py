"""Golden Path graph aggregation.

Every node and edge corresponds to transitions that exist in the individual
records. Nodes: (step column, label) with unique person counts. Edges:
(column k, A) -> (column k+1, B) counted as unique persons whose k-th item is A
and (k+1)-th item is B. The purchase outcome is attached only after a person's
LAST observed action; when the window cuts a journey, the terminal node is
``後続行動あり``.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field

from .. import config
from ..filters import Filters
from .base import Dataset, View, mean_or_none, rate, small_cell
from .paths import complete_path_persons, enumerate_paths

OUTCOME_BUY = "購入"
OUTCOME_NONBUY = "非購入／観測終了"
OUTCOME_MORE = "後続行動あり"
OTHER = "その他"
GraphMode = Literal["head", "tail", "anchor", "full"]


class NodeRef(BaseModel):
    step: int
    label: str


class EdgeRef(BaseModel):
    step: int
    source: str
    target: str


class GraphRequest(BaseModel):
    filters: Filters = Field(default_factory=Filters)
    steps: int = Field(default=5, ge=2, le=config.MAX_STEPS)
    mode: GraphMode = "head"
    anchor: str | None = None
    anchor_occurrence: Literal["first", "last"] = "first"
    top_n: int = Field(default=8, ge=3, le=15)
    min_count: int = Field(default=0, ge=0)
    min_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    show_other: bool = True
    selected_nodes: list[NodeRef] = Field(default_factory=list)
    selected_edges: list[EdgeRef] = Field(default_factory=list)
    include_rankings: bool = True


def _window(seq, req: GraphRequest) -> tuple[list, int, bool] | None:
    """Return (window items, start column (1-based), has_more_after) or None if the person has no window."""
    n = req.steps
    L = len(seq)
    if L == 0:
        return None
    if req.mode in ("head", "full"):
        if req.mode == "full":
            n = config.MAX_STEPS
        return seq[:n], 1, L > n
    if req.mode == "tail":
        w = seq[-n:]
        return w, n - len(w) + 1, False
    # anchor
    if not req.anchor:
        return None
    idxs = [i for i, it in enumerate(seq) if it[0] == req.anchor]
    if not idxs:
        return None
    i = idxs[0] if req.anchor_occurrence == "first" else idxs[-1]
    w = seq[i:i + n]
    return w, 1, (i + n) < L


def _is_buyer(ds: Dataset, pid: int) -> bool:
    return ds.person_index.at[pid, "purchase_status"] == config.BUYER_LABEL


def build_graph(ds: Dataset, req: GraphRequest) -> dict[str, Any]:
    f = req.filters
    view = ds.view(f)
    N = view.n
    steps = config.MAX_STEPS if req.mode == "full" else req.steps
    buyer_flags = (ds.persons.set_index("person_id")["purchase_status"] == config.BUYER_LABEL).to_dict()

    # --- per-person placement ------------------------------------------
    placements: dict[int, tuple[list, int, bool]] = {}
    for pid, seq in view.sequences.items():
        w = _window(seq, req)
        if w is not None:
            placements[pid] = w
    base_pids = set(placements.keys())

    # --- base keep-sets (top-n per column before selection; used to resolve 「その他」 selections)
    base_keep: dict[int, set[str]] = {}
    if req.selected_nodes or req.selected_edges:
        base_counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for pid in base_pids:
            w, start, _more = placements[pid]
            for j, it in enumerate(w):
                base_counts[start + j][it[0]] += 1
        for k, d in base_counts.items():
            ranked = sorted(d.items(), key=lambda x: (-x[1], x[0]))
            base_keep[k] = {lab for i, (lab, c) in enumerate(ranked) if i < req.top_n and c >= req.min_count}

    def label_matches(k: int, actual: str | None, wanted: str) -> bool:
        if actual is None:
            return False
        if wanted == OTHER:
            return actual not in base_keep.get(k, set())
        return actual == wanted

    # --- selection ---------------------------------------------------------
    selection_info: dict[str, Any] | None = None
    sel_pids = base_pids
    if req.selected_nodes or req.selected_edges:
        matched: set[int] = set()
        sel_nodes = sorted(req.selected_nodes, key=lambda x: x.step)
        for pid in base_pids:
            w, start, _more = placements[pid]
            col = {start + j: it[0] for j, it in enumerate(w)}
            ok = True
            if f.path_mode == "consecutive":
                for nref in sel_nodes:
                    if not label_matches(nref.step, col.get(nref.step), nref.label):
                        ok = False
                        break
                if ok:
                    for e in req.selected_edges:
                        if not (label_matches(e.step, col.get(e.step), e.source) and label_matches(e.step + 1, col.get(e.step + 1), e.target)):
                            ok = False
                            break
            else:
                # ordered: labels must appear in that order (not necessarily adjacent) within the window
                want: list[tuple[int, str]] = [(n.step, n.label) for n in sel_nodes]
                for e in req.selected_edges:
                    want += [(e.step, e.source), (e.step + 1, e.target)]
                j = 0
                for jj, it in enumerate(w):
                    if j < len(want) and label_matches(want[j][0], it[0], want[j][1]):
                        j += 1
                ok = j == len(want)
            if ok:
                matched.add(pid)
        sel_pids = matched
        sel_buyers = sum(1 for p in matched if buyer_flags.get(p, False))
        selection_info = {
            "count": len(matched),
            "rate_of_filtered": rate(len(matched), N),
            "denominator": N,
            "buyers": sel_buyers,
            "nonbuyers": len(matched) - sel_buyers,
            "path_definition": "連続パス（各ステップ位置で一致）" if f.path_mode == "consecutive" else "順序保持パス（選択順に出現、間に他行動を許容）",
            "selected_nodes": [n.model_dump() for n in sel_nodes],
            "selected_edges": [e.model_dump() for e in req.selected_edges],
            "avg_action_count": mean_or_none([float(ds.person_index.at[p, "recorded_action_count"]) for p in matched]) if matched else None,
            "avg_duration_days": mean_or_none([float(ds.person_index.at[p, "duration_days"]) for p in matched]) if matched else None,
        }

    # --- aggregation -------------------------------------------------------
    node_people: dict[tuple[int, str], set[int]] = defaultdict(set)
    node_dn: dict[tuple[int, str], list[int]] = defaultdict(list)
    edge_people: dict[tuple[int, str, str], set[int]] = defaultdict(set)
    reached: dict[int, set[int]] = defaultdict(set)
    outcome_col = steps + 1
    for pid in sel_pids:
        w, start, more = placements[pid]
        prev: tuple[int, str] | None = None
        for j, (lab, dn, _st) in enumerate(w):
            k = start + j
            node_people[(k, lab)].add(pid)
            if dn >= 0:
                node_dn[(k, lab)].append(dn)
            reached[k].add(pid)
            if prev is not None:
                edge_people[(prev[0], prev[1], lab)].add(pid)
            prev = (k, lab)
        # terminal
        if prev is not None:
            if more:
                term = OUTCOME_MORE
            else:
                term = OUTCOME_BUY if buyer_flags.get(pid, False) else OUTCOME_NONBUY
            node_people[(outcome_col, term)].add(pid)
            edge_people[(prev[0], prev[1], term)].add(pid)
            reached[outcome_col].add(pid)

    # --- pruning (top-n per column, min_count) -------------------------------
    keep: dict[int, set[str]] = {}
    other_members: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for k in range(1, outcome_col + 1):
        labels = [(lab, len(p)) for (kk, lab), p in node_people.items() if kk == k]
        labels.sort(key=lambda x: (-x[1], x[0]))
        if k == outcome_col:
            keep[k] = {lab for lab, _ in labels}
            continue
        kept = set()
        for i, (lab, c) in enumerate(labels):
            if i < req.top_n and c >= req.min_count:
                kept.add(lab)
            else:
                other_members[k].append({"label": lab, "count": c})
        keep[k] = kept

    def canon(k: int, lab: str) -> str | None:
        if lab in keep.get(k, set()):
            return lab
        return OTHER if (req.show_other and k != outcome_col) else None

    merged_nodes: dict[tuple[int, str], set[int]] = defaultdict(set)
    merged_dn: dict[tuple[int, str], list[int]] = defaultdict(list)
    for (k, lab), p in node_people.items():
        c = canon(k, lab)
        if c is None:
            continue
        merged_nodes[(k, c)] |= p
        merged_dn[(k, c)] += node_dn[(k, lab)]
    merged_edges: dict[tuple[int, str, str], set[int]] = defaultdict(set)
    for (k, a, b), p in edge_people.items():
        ca = canon(k, a)
        cb = canon(k + 1, b)
        if ca is None or cb is None:
            continue
        merged_edges[(k, ca, cb)] |= p

    sel_n = len(sel_pids)
    nodes = []
    for (k, lab), p in sorted(merged_nodes.items(), key=lambda x: (x[0][0], -len(x[1]), x[0][1])):
        c = len(p)
        kind = "outcome" if k == outcome_col else ("other" if lab == OTHER else "action")
        buyers = sum(1 for q in p if buyer_flags.get(q, False))
        nodes.append({
            "id": f"n{k}:{lab}",
            "step": k,
            "label": lab,
            "kind": kind,
            "count": c,
            "rate": rate(c, N),
            "share_of_step": rate(c, len(reached[k])),
            "share_of_selection": rate(c, sel_n),
            "buyers": buyers,
            "nonbuyers": c - buyers,
            "avg_dn": mean_or_none(merged_dn[(k, lab)]),
            "members": other_members[k] if lab == OTHER else None,
            "small_cell": small_cell(c),
        })
    edges = []
    for (k, a, b), p in sorted(merged_edges.items(), key=lambda x: (x[0][0], -len(x[1]))):
        c = len(p)
        src = len(merged_nodes[(k, a)])
        r = rate(c, src)
        if c < req.min_count and b not in (OUTCOME_BUY, OUTCOME_NONBUY, OUTCOME_MORE):
            continue
        if r is not None and r < req.min_rate:
            continue
        edges.append({
            "id": f"e{k}:{a}->{b}",
            "step": k,
            "source": f"n{k}:{a}",
            "target": f"n{k + 1}:{b}",
            "source_label": a,
            "target_label": b,
            "count": c,
            "denominator": src,
            "rate": r,
            "rate_of_filtered": rate(c, N),
            "small_cell": small_cell(c),
        })

    reached_counts = {k: len(v) for k, v in reached.items()}
    columns = [{"step": k, "label": _column_label(k, steps, req.mode), "reached": reached_counts.get(k, 0)} for k in range(1, outcome_col + 1)]

    result: dict[str, Any] = {
        "n": N,
        "n_placed": len(base_pids),
        "n_in_graph": sel_n,
        "steps": steps,
        "mode": req.mode,
        "anchor": req.anchor,
        "columns": columns,
        "nodes": nodes,
        "edges": edges,
        "selection": selection_info,
        "filters": f.describe(),
        "notes": list(view.note) + _mode_notes(req, N, len(base_pids)),
        "denominators": {
            "experience_rate": "フィルタ対象者数 n",
            "share_of_step": "当該ステップ到達者数",
            "edge_rate": "遷移元ノードの人数（条件付き遷移率）",
        },
        "censoring": {
            "more_actions": len(node_people.get((outcome_col, OUTCOME_MORE), set())),
            "buy": len(node_people.get((outcome_col, OUTCOME_BUY), set())),
            "nonbuy_end": len(node_people.get((outcome_col, OUTCOME_NONBUY), set())),
        },
    }
    if req.include_rankings:
        result["rankings"] = rankings(ds, view, sel_pids if selection_info else None)
    return result


def _column_label(k: int, steps: int, mode: str) -> str:
    if k == steps + 1:
        return "OUTCOME"
    if mode == "tail":
        return f"STEP −{steps - k}" if k != steps else "最終行動"
    return f"STEP {k}"


def _mode_notes(req: GraphRequest, n: int, placed: int) -> list[str]:
    notes = []
    if req.mode == "head":
        notes.append(f"行動01から先頭{req.steps}ステップ。購入Outcomeは最終観測行動の後にのみ接続し、{req.steps}ステップ以降も行動がある人は「後続行動あり」に接続。")
    elif req.mode == "tail":
        notes.append(f"最終観測行動から逆算した末尾{req.steps}ステップ。行動数が{req.steps}未満の人は途中の列から出現。")
    elif req.mode == "anchor":
        notes.append(f"起点「{req.anchor}」の{'初回' if req.anchor_occurrence == 'first' else '最終'}出現から{req.steps}ステップ。起点を経験した{placed}人のみ配置（経験率の分母は n={n} のまま）。")
    else:
        notes.append("全25ステップ（横スクロール）。")
    return notes


def rankings(ds: Dataset, view: View, restrict: set[int] | None) -> dict[str, Any]:
    f = view.filters
    N = view.n if restrict is None else len(restrict)
    out: dict[str, Any] = {"denominator": N, "top_paths": {}, "buyer_characteristic": {}}
    for k in (2, 3, 5):
        persons, occ, note = enumerate_paths(view, k, f.path_mode, restrict)
        rows = sorted(persons.items(), key=lambda x: (-len(x[1]), x[0]))[:15]
        out["top_paths"][str(k)] = {
            "note": note,
            "rows": [{"path": list(p), "count": len(s), "rate": rate(len(s), N), "occurrences": occ[p]} for p, s in rows],
        }
    # buyer-characteristic: compare buyers vs nonbuyers under same age/duration filters (ignore result filter)
    fb = f.model_copy(update={"result": "buyer"})
    fn = f.model_copy(update={"result": "nonbuyer"})
    vb = ds.view(fb)
    vn = ds.view(fn)
    for k in (2, 3):
        pb, _, note = enumerate_paths(vb, k, f.path_mode, None if restrict is None else [p for p in restrict if p in vb.sequences])
        pn, _, _ = enumerate_paths(vn, k, f.path_mode, None if restrict is None else [p for p in restrict if p in vn.sequences])
        nb = vb.n if restrict is None else len([p for p in restrict if p in vb.sequences])
        nn = vn.n if restrict is None else len([p for p in restrict if p in vn.sequences])
        rows = []
        for p, s in pb.items():
            cb = len(s)
            cn = len(pn.get(p, ()))
            rb = rate(cb, nb)
            rn = rate(cn, nn)
            if rb is None:
                continue
            rows.append({
                "path": list(p), "buyer_count": cb, "buyer_rate": rb, "nonbuyer_count": cn, "nonbuyer_rate": rn,
                "diff_pt": None if rn is None else (rb - rn) * 100,
                "ratio": None if (rn is None or rn == 0) else rb / rn,
                "small_cell": small_cell(cb, cn),
            })
        rows.sort(key=lambda r: (-(r["diff_pt"] or -999), -r["buyer_count"]))
        out["buyer_characteristic"][str(k)] = {
            "note": note,
            "buyer_n": nb,
            "nonbuyer_n": nn,
            "rows": rows[:15],
            "caveat": "購入者に多いパスは購買の因果効果ではなく、購入者サンプル内での出現率差です。",
        }
    return out
