"""Overview KPIs, distributions and data quality."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from .. import config
from ..filters import Filters
from .base import Dataset, mean_or_none, median_or_none, rate, small_cell


def overview(ds: Dataset, f: Filters) -> dict[str, Any]:
    pids = ds.select_persons(f)
    p = ds.person_index.loc[pids]
    N = int(len(p))
    buyers = int((p["purchase_status"] == config.BUYER_LABEL).sum())
    counts = p["recorded_action_count"].dropna().astype(float).tolist()
    days = p["duration_days"].dropna().astype(float).tolist()
    by_age = {a: int((p["age_group"] == a).sum()) for a in sorted(set(p["age_group"]))}
    by_age_result = {
        a: {"buyers": int(((p["age_group"] == a) & (p["purchase_status"] == config.BUYER_LABEL)).sum()),
            "nonbuyers": int(((p["age_group"] == a) & (p["purchase_status"] == config.NONBUYER_LABEL)).sum())}
        for a in by_age
    }
    # histograms
    hist_actions = [{"bin": i, "count": int(sum(1 for c in counts if c == i))} for i in range(1, config.MAX_STEPS + 1)]
    hist_days = [{"bin": i, "count": int(sum(1 for d in days if d == i))} for i in range(0, 31)]
    type_share = [{"type": t, "count": int(c), "rate": rate(int(c), N)} for t, c in p["journey_type"].value_counts().items()]
    start_share = [{"period": t, "count": int(c), "rate": rate(int(c), N)} for t, c in p["start_period"].value_counts().items()]

    # category table (experience rate; buyers vs nonbuyers inside the same age/duration filter)
    view = ds.view(f)
    label_of = view.label_of
    exp: dict[str, set[int]] = defaultdict(set)
    dn: dict[str, list[int]] = defaultdict(list)
    events_n: dict[str, int] = defaultdict(int)
    for pid, seq in view.sequences.items():
        for lab, d, _ in seq:
            exp[lab].add(pid)
            events_n[lab] += 1
            if d >= 0:
                dn[lab].append(d)
    fb = f.model_copy(update={"result": "buyer"})
    fn = f.model_copy(update={"result": "nonbuyer"})
    vb, vn = ds.view(fb), ds.view(fn)
    expb: dict[str, set[int]] = defaultdict(set)
    expn: dict[str, set[int]] = defaultdict(set)
    for pid, seq in vb.sequences.items():
        for lab, _, _ in seq:
            expb[lab].add(pid)
    for pid, seq in vn.sequences.items():
        for lab, _, _ in seq:
            expn[lab].add(pid)
    rows = []
    for lab in sorted(exp, key=lambda l: -len(exp[l])):
        cb, cn = len(expb.get(lab, ())), len(expn.get(lab, ()))
        rb, rn = rate(cb, vb.n), rate(cn, vn.n)
        rows.append({
            "label": lab,
            "count": len(exp[lab]),
            "rate": rate(len(exp[lab]), N),
            "events": events_n[lab],
            "avg_dn": mean_or_none(dn[lab]),
            "buyer_count": cb, "buyer_rate": rb, "nonbuyer_count": cn, "nonbuyer_rate": rn,
            "diff_pt": None if (rb is None or rn is None) else (rb - rn) * 100,
            "ratio": None if (rb is None or rn is None or rn == 0) else rb / rn,
            "small_cell": small_cell(cb, cn),
        })
    uniq_vars = len({v for pid in pids for v, *_ in ds.raw_sequences[int(pid)]})
    uniq_cats = len({ds.dictionary.variable_to_category.get(v, "未分類") for pid in pids for v, *_ in ds.raw_sequences[int(pid)]})
    return {
        "n": N,
        "buyers": buyers,
        "nonbuyers": N - buyers,
        "by_age": by_age,
        "by_age_result": by_age_result,
        "action_count": {"mean": mean_or_none(counts), "median": median_or_none(counts)},
        "duration_days": {"mean": mean_or_none(days), "median": median_or_none(days), "label": "観測期間（基準日までの日数）"},
        "unique_variables": uniq_vars,
        "unique_categories": uniq_cats,
        "hist_action_count": hist_actions,
        "hist_duration": hist_days,
        "journey_type_share": type_share,
        "start_period_share": start_share,
        "category_table": rows,
        "category_table_denominators": {"all": N, "buyers": vb.n, "nonbuyers": vn.n},
        "filters": f.describe(),
        "notes": list(view.note),
        "quality": ds.quality,
        "expected": config.EXPECTED,
    }
