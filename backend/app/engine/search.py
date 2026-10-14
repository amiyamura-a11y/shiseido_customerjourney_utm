"""Path search (パス詳細探索) and path detail."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from .. import config
from ..filters import Filters
from .base import Dataset, mean_or_none, rate, ratio, small_cell
from .paths import complete_path_persons, enumerate_paths


class SearchRequest(BaseModel):
    filters: Filters = Field(default_factory=Filters)
    start: str | None = None
    end: str | None = None
    via: list[str] = Field(default_factory=list)
    min_steps: int = Field(default=2, ge=2, le=10)
    max_steps: int = Field(default=3, ge=2, le=10)
    min_count: int = Field(default=5, ge=0)
    limit: int = Field(default=100, ge=1, le=500)
    sort: str = "count"


class PathDetailRequest(BaseModel):
    filters: Filters = Field(default_factory=Filters)
    path: list[str]
    examples: int = Field(default=5, ge=0, le=20)


def _segment_counts(ds: Dataset, f: Filters, paths: list[tuple[str, ...]], mode: str) -> tuple[dict, int, dict, int]:
    fb = f.model_copy(update={"result": "buyer"})
    fn = f.model_copy(update={"result": "nonbuyer"})
    vb, vn = ds.view(fb), ds.view(fn)
    cb: dict[tuple[str, ...], int] = {}
    cn: dict[tuple[str, ...], int] = {}
    by_len: dict[int, list[tuple[str, ...]]] = defaultdict(list)
    for p in paths:
        by_len[len(p)].append(p)
    for k, ps in by_len.items():
        pb, _, _ = enumerate_paths(vb, k, mode)
        pn, _, _ = enumerate_paths(vn, k, mode)
        if mode == "ordered" and not pb and not pn and k > 3:
            for p in ps:
                cb[p] = len(complete_path_persons(vb, p, mode))
                cn[p] = len(complete_path_persons(vn, p, mode))
            continue
        for p in ps:
            cb[p] = len(pb.get(p, ()))
            cn[p] = len(pn.get(p, ()))
    return cb, vb.n, cn, vn.n


def search(ds: Dataset, req: SearchRequest) -> dict[str, Any]:
    f = req.filters
    view = ds.view(f)
    N = view.n
    mode = f.path_mode
    candidates: dict[tuple[str, ...], set[int]] = {}
    occurrences: dict[tuple[str, ...], int] = {}
    notes: list[str] = list(view.note)
    lo, hi = req.min_steps, max(req.min_steps, req.max_steps)
    for k in range(lo, hi + 1):
        if mode == "ordered" and k > 3:
            # ordered mode beyond 3 steps: only fully specified paths can be counted
            if req.start and req.end and len(req.via) == k - 2:
                p = (req.start, *req.via, req.end)
                s = complete_path_persons(view, p, mode)
                if s:
                    candidates[p] = s
                    occurrences[p] = len(s)
            else:
                notes.append(f"順序保持モードでは{k}ステップの全列挙は行いません（起点・経由・終点を完全指定すると算出できます）。")
            continue
        persons, occ, note = enumerate_paths(view, k, mode)
        if note and note not in notes:
            notes.append(note)
        for p, s in persons.items():
            if req.start and p[0] != req.start:
                continue
            if req.end and p[-1] != req.end:
                continue
            if req.via and not all(v in p[1:-1] for v in req.via):
                continue
            if len(s) < req.min_count:
                continue
            candidates[p] = s
            occurrences[p] = occ[p]
    paths = list(candidates)
    cb, nb, cn, nn = _segment_counts(ds, f, paths, mode)
    pidx = ds.person_index
    rows = []
    for p in paths:
        s = candidates[p]
        b, n_ = cb.get(p, 0), cn.get(p, 0)
        rb, rn = rate(b, nb), rate(n_, nn)
        sub = pidx.loc[list(s)]
        rows.append({
            "path": list(p),
            "path_str": " → ".join(p),
            "steps": len(p),
            "count": len(s),
            "rate": rate(len(s), N),
            "occurrences": occurrences[p],
            "buyer_count": b, "buyer_rate": rb, "nonbuyer_count": n_, "nonbuyer_rate": rn,
            "diff_pt": None if (rb is None or rn is None) else (rb - rn) * 100,
            "ratio": ratio(rb, rn),
            "avg_duration": float(sub["duration_days"].mean()) if len(sub) else None,
            "avg_action_count": float(sub["recorded_action_count"].mean()) if len(sub) else None,
            "small_cell": small_cell(b, n_),
        })
    key = {
        "count": lambda r: -r["count"], "rate": lambda r: -(r["rate"] or 0), "diff_pt": lambda r: -(r["diff_pt"] if r["diff_pt"] is not None else -1e9),
        "ratio": lambda r: -(r["ratio"] if r["ratio"] is not None else -1e9), "buyer_rate": lambda r: -(r["buyer_rate"] or 0),
    }.get(req.sort, lambda r: -r["count"])
    rows.sort(key=key)
    return {
        "n": N, "buyer_n": nb, "nonbuyer_n": nn, "total_matches": len(rows), "rows": rows[: req.limit],
        "filters": f.describe(), "notes": notes,
        "denominators": {"rate": "フィルタ対象者数 n", "buyer_rate": "同条件（年代・期間）の購入者数", "nonbuyer_rate": "同条件の非購入者数"},
    }


def path_detail(ds: Dataset, req: PathDetailRequest) -> dict[str, Any]:
    f = req.filters
    view = ds.view(f)
    N = view.n
    p = tuple(req.path)
    mode = f.path_mode
    s = complete_path_persons(view, p, mode)
    pidx = ds.person_index
    # per-step timing (first match position in each person's sequence)
    step_dn: list[list[int]] = [[] for _ in p]
    examples = []
    for pid in sorted(s):
        seq = view.sequences[pid]
        labs = [it[0] for it in seq]
        pos = _match_positions(labs, p, mode)
        if pos:
            for i, j in enumerate(pos):
                if seq[j][1] >= 0:
                    step_dn[i].append(seq[j][1])
        if len(examples) < req.examples:
            raw = ds.raw_sequences[pid]
            examples.append({
                "person": f"匿名 #{pid}",
                "age_group": pidx.at[pid, "age_group"],
                "purchase_status": pidx.at[pid, "purchase_status"],
                "duration_days": int(pidx.at[pid, "duration_days"]),
                "action_count": int(pidx.at[pid, "recorded_action_count"]),
                "matched_positions": pos,
                "sequence": [{"step": st, "dn": dn, "variable": v, "category": ds.dictionary.variable_to_category.get(v, "未分類"), "label": view.label_of(v), "repeat": rp} for v, dn, st, rp in raw],
            })
    # segment comparison
    segs = []
    for name, upd in [("購入者", {"result": "buyer"}), ("非購入者", {"result": "nonbuyer"}), ("18–29歳", {"age": "18-29"}), ("30–49歳", {"age": "30-49"})]:
        vf = f.model_copy(update=upd)
        vv = ds.view(vf)
        c = len(complete_path_persons(vv, p, mode))
        segs.append({"segment": name, "count": c, "n": vv.n, "rate": rate(c, vv.n)})
    sub = pidx.loc[list(s)] if s else None
    return {
        "path": list(p), "mode": mode, "n": N, "count": len(s), "rate": rate(len(s), N),
        "avg_duration": None if sub is None else float(sub["duration_days"].mean()),
        "avg_action_count": None if sub is None else float(sub["recorded_action_count"].mean()),
        "step_timing": [{"step": i + 1, "label": lab, "avg_dn": mean_or_none(step_dn[i]), "n": len(step_dn[i])} for i, lab in enumerate(p)],
        "segments": segs,
        "examples": examples,
        "filters": f.describe(), "notes": list(view.note),
    }


def _match_positions(labels: list[str], path: tuple[str, ...], mode: str) -> list[int] | None:
    k = len(path)
    if mode == "consecutive":
        for i in range(len(labels) - k + 1):
            if tuple(labels[i:i + k]) == path:
                return list(range(i, i + k))
        return None
    pos = []
    j = 0
    for i, lab in enumerate(labels):
        if j < k and lab == path[j]:
            pos.append(i)
            j += 1
    return pos if j == k else None
