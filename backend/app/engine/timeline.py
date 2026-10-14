"""Time-series analysis over D−n (days before the reference date)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from ..filters import Filters
from .base import Dataset, rate

WINDOWS = [("D−30〜15", 15, 30), ("D−14〜8", 8, 14), ("D−7〜0", 0, 7)]
DURATION_BUCKETS = [("0–7日", 0, 7), ("8–14日", 8, 14), ("15–21日", 15, 21), ("22–30日", 22, 30)]


class TimelineRequest(BaseModel):
    filters: Filters = Field(default_factory=Filters)
    top_n: int = Field(default=15, ge=3, le=40)


def timeline(ds: Dataset, req: TimelineRequest) -> dict[str, Any]:
    f = req.filters.model_copy(update={"timing_preset": "all", "timing_min": None, "timing_max": None, "dedupe": "keep_all"})
    view = ds.view(f)
    N = view.n
    max_day = 30
    day_people: dict[tuple[str, int], set[int]] = defaultdict(set)
    any_day: dict[int, set[int]] = defaultdict(set)
    label_people: dict[str, set[int]] = defaultdict(set)
    win_people: dict[tuple[str, str], set[int]] = defaultdict(set)
    for pid, seq in view.sequences.items():
        for lab, dn, _ in seq:
            if dn < 0:
                continue
            d = min(dn, max_day)
            day_people[(lab, d)].add(pid)
            any_day[d].add(pid)
            label_people[lab].add(pid)
            for wname, lo, hi in WINDOWS:
                if lo <= dn <= hi:
                    win_people[(wname, lab)].add(pid)
    labels = sorted(label_people, key=lambda l: -len(label_people[l]))[: req.top_n]
    heat = []
    for lab in labels:
        heat.append({"label": lab, "total": len(label_people[lab]), "cells": [{"day": d, "count": len(day_people.get((lab, d), ())), "rate": rate(len(day_people.get((lab, d), ())), N)} for d in range(max_day, -1, -1)]})
    daily = [{"day": d, "count": len(any_day.get(d, ())), "rate": rate(len(any_day.get(d, ())), N)} for d in range(max_day, -1, -1)]
    daily_by_label = {lab: [{"day": d, "count": len(day_people.get((lab, d), ())), "rate": rate(len(day_people.get((lab, d), ())), N)} for d in range(max_day, -1, -1)] for lab in labels[:8]}
    rankings = []
    for wname, lo, hi in WINDOWS:
        rows = sorted(((lab, len(s)) for (w, lab), s in win_people.items() if w == wname), key=lambda x: -x[1])[: req.top_n]
        rankings.append({"window": wname, "rows": [{"label": lab, "count": c, "rate": rate(c, N)} for lab, c in rows]})
    # comparison by person observation-duration bucket
    pidx = ds.person_index
    bucket_rows = []
    for bname, lo, hi in DURATION_BUCKETS:
        pids = [pid for pid in view.sequences if lo <= pidx.at[pid, "duration_days"] <= hi]
        n = len(pids)
        lab_c: dict[str, set[int]] = defaultdict(set)
        for pid in pids:
            for lab, dn, _ in view.sequences[pid]:
                lab_c[lab].add(pid)
        bucket_rows.append({"bucket": bname, "n": n, "rows": [{"label": lab, "count": len(lab_c.get(lab, ())), "rate": rate(len(lab_c.get(lab, ())), n)} for lab in labels]})
    return {
        "n": N, "labels": labels, "heatmap": heat, "daily": daily, "daily_by_label": daily_by_label,
        "window_rankings": rankings, "duration_buckets": bucket_rows,
        "filters": req.filters.describe(),
        "notes": [
            "D−n は基準日からの日数（非購入者の基準日は購入日ではありません）。",
            "行動発生時期フィルタで隣接させたパスは「期間内抽出後の隣接」であり、元ログの真の連続パスとは異なります。",
        ],
    }
