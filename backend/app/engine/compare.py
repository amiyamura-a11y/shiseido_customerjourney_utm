"""A/B comparison of two filter sets with aligned graphs and difference tables."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from .. import config
from ..filters import Filters
from .base import Dataset, mean_or_none, rate, ratio, small_cell
from .graph import GraphRequest, build_graph
from .paths import enumerate_paths


class CompareRequest(BaseModel):
    a: Filters
    b: Filters
    label_a: str = "A"
    label_b: str = "B"
    steps: int = Field(default=5, ge=2, le=config.MAX_STEPS)
    mode: str = "head"
    anchor: str | None = None
    top_n: int = Field(default=8, ge=3, le=15)
    min_count: int = 0
    show_other: bool = True
    other_mode: str | None = None


def _experience(ds: Dataset, f: Filters) -> tuple[dict[str, set[int]], int, dict[str, list[int]]]:
    view = ds.view(f)
    exp: dict[str, set[int]] = defaultdict(set)
    dn: dict[str, list[int]] = defaultdict(list)
    for pid, seq in view.sequences.items():
        for lab, d, _ in seq:
            exp[lab].add(pid)
            if d >= 0:
                dn[lab].append(d)
    return exp, view.n, dn


def compare(ds: Dataset, req: CompareRequest) -> dict[str, Any]:
    # align granularity & modes between A and B
    fb = req.b.model_copy(update={"granularity": req.a.granularity, "dedupe": req.a.dedupe, "path_mode": req.a.path_mode})
    ga = build_graph(ds, GraphRequest(filters=req.a, steps=req.steps, mode=req.mode, anchor=req.anchor, top_n=req.top_n, min_count=req.min_count, show_other=req.show_other, other_mode=req.other_mode, include_rankings=False))
    gb = build_graph(ds, GraphRequest(filters=fb, steps=req.steps, mode=req.mode, anchor=req.anchor, top_n=req.top_n, min_count=req.min_count, show_other=req.show_other, other_mode=req.other_mode, include_rankings=False))
    # shared node order per column: union sorted by combined count, so both sides align
    order: dict[int, list[str]] = {}
    combined: dict[tuple[int, str], int] = defaultdict(int)
    for g in (ga, gb):
        for n in g["nodes"]:
            combined[(n["step"], n["label"])] += n["count"]
    for (k, lab), c in sorted(combined.items(), key=lambda x: (x[0][0], -x[1], x[0][1])):
        order.setdefault(k, []).append(lab)
    max_count = max([n["count"] for n in ga["nodes"] + gb["nodes"]] or [1])
    max_rate = max([n["rate"] or 0 for n in ga["nodes"] + gb["nodes"]] or [1])

    ea, na, dna = _experience(ds, req.a)
    eb, nb, dnb = _experience(ds, fb)
    rows = []
    for lab in sorted(set(ea) | set(eb), key=lambda l: -(len(ea.get(l, ())) + len(eb.get(l, ())))):
        ca, cb = len(ea.get(lab, ())), len(eb.get(lab, ()))
        ra, rb = rate(ca, na), rate(cb, nb)
        rows.append({
            "label": lab, "count_a": ca, "count_b": cb, "rate_a": ra, "rate_b": rb,
            "diff_pt": None if (ra is None or rb is None) else (ra - rb) * 100,
            "ratio": ratio(ra, rb),
            "avg_dn_a": mean_or_none(dna.get(lab, [])), "avg_dn_b": mean_or_none(dnb.get(lab, [])),
            "small_cell": small_cell(ca, cb),
        })
    # edge (conditional transition rate) differences on the aligned graphs
    from .graph import OUTCOME_BUY, OUTCOME_MORE, OUTCOME_NONBUY
    _outcomes = {OUTCOME_BUY, OUTCOME_MORE, OUTCOME_NONBUY}
    ea_map = {(e["step"], e["source_label"], e["target_label"]): e for e in ga["edges"] if e["target_label"] not in _outcomes}
    eb_map = {(e["step"], e["source_label"], e["target_label"]): e for e in gb["edges"] if e["target_label"] not in _outcomes}
    edge_rows = []
    for key in set(ea_map) | set(eb_map):
        x, y = ea_map.get(key), eb_map.get(key)
        ra = x["rate"] if x else 0.0
        rb = y["rate"] if y else 0.0
        edge_rows.append({
            "step": key[0], "source": key[1], "target": key[2],
            "count_a": x["count"] if x else 0, "den_a": x["denominator"] if x else 0, "rate_a": ra,
            "count_b": y["count"] if y else 0, "den_b": y["denominator"] if y else 0, "rate_b": rb,
            "diff_pt": None if (ra is None or rb is None) else (ra - rb) * 100,
            "small_cell": small_cell(x["count"] if x else 0, y["count"] if y else 0),
        })
    edge_rows.sort(key=lambda r: -abs(r["diff_pt"] or 0))
    # path difference ranking (2 and 3 steps)
    va, vb = ds.view(req.a), ds.view(fb)
    path_rows: dict[str, Any] = {}
    for k in (2, 3):
        pa, _, note = enumerate_paths(va, k, req.a.path_mode)
        pb, _, _ = enumerate_paths(vb, k, req.a.path_mode)
        rws = []
        for p in set(pa) | set(pb):
            ca, cb = len(pa.get(p, ())), len(pb.get(p, ()))
            ra, rb = rate(ca, na), rate(cb, nb)
            rws.append({"path": list(p), "count_a": ca, "count_b": cb, "rate_a": ra, "rate_b": rb,
                        "diff_pt": None if (ra is None or rb is None) else (ra - rb) * 100, "ratio": ratio(ra, rb), "small_cell": small_cell(ca, cb)})
        rws.sort(key=lambda r: -abs(r["diff_pt"] or 0))
        path_rows[str(k)] = {"note": note, "rows": rws[:30]}

    pa_df = ds.person_frame(va.person_ids) if va.n else None
    pb_df = ds.person_frame(vb.person_ids) if vb.n else None
    summary = {
        "n_a": na, "n_b": nb,
        "avg_action_count_a": None if pa_df is None else float(pa_df["recorded_action_count"].mean()),
        "avg_action_count_b": None if pb_df is None else float(pb_df["recorded_action_count"].mean()),
        "avg_duration_a": None if pa_df is None else float(pa_df["duration_days"].mean()),
        "avg_duration_b": None if pb_df is None else float(pb_df["duration_days"].mean()),
    }
    return {
        "label_a": req.label_a, "label_b": req.label_b,
        "graph_a": ga, "graph_b": gb,
        "node_order": {str(k): v for k, v in order.items()},
        "scale": {"max_count": max_count, "max_rate": max_rate},
        "summary": summary,
        "experience_rows": rows,
        "edge_rows": edge_rows[:40],
        "path_rows": path_rows,
        "filters_a": req.a.describe(), "filters_b": fb.describe(),
        "caveats": [
            "倍率は B の率が 0 の場合「算出不可」。",
            f"人数 {config.SMALL_CELL_THRESHOLD} 人未満のセルは注意表示。",
            "購入者に多い行動・パスは購入者サンプル内での出現率差であり、購買の因果効果を意味しません。",
        ],
    }
