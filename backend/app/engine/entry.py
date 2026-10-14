"""Entry-action (起点行動) analysis: anchor -> 2nd -> 3rd ... with explicit denominators."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, Field

from .. import config
from ..filters import Filters
from .base import Dataset, mean_or_none, rate

NO_FOLLOW = "後続記録なし"
WORRY_GROUP = "肌悩み検索ALL（5変数統合）"


class EntryRequest(BaseModel):
    filters: Filters = Field(default_factory=Filters)
    anchor: str
    steps: int = Field(default=3, ge=2, le=10)
    occurrence: Literal["first", "last", "all"] = "first"
    follow: Literal["next", "next_in_category", "within_days"] = "next"
    target_category: str | None = None
    within_days: int = Field(default=7, ge=0, le=30)
    top_n: int = Field(default=10, ge=1, le=50)


def anchor_options(ds: Dataset, granularity: str) -> list[dict[str, Any]]:
    labels = ds.labels_for(granularity)
    out = [{"value": l, "label": l, "group": "個別変数" if granularity == "variable" else ("分析カテゴリ" if granularity == "category" else "大分類")} for l in labels]
    if granularity == "variable":
        out.insert(0, {"value": WORRY_GROUP, "label": WORRY_GROUP, "group": "統合"})
    return out


def _is_anchor(lab: str, raw_var: str, anchor: str) -> bool:
    if anchor == WORRY_GROUP:
        return raw_var.startswith("検索_効能/肌悩み系_") and ds_worry_ok(raw_var)
    return lab == anchor


def ds_worry_ok(raw_var: str) -> bool:
    # 5 skin-worry search variables (エイジング・乾燥・肌荒れ・肌トーン・○○肌); the ULTIMUNE-branded one belongs to UTM指名検索
    return not raw_var.endswith("_アルティミューン")


def entry_analysis(ds: Dataset, req: EntryRequest) -> dict[str, Any]:
    f = req.filters
    view = ds.view(f)
    N = view.n
    # we need the raw variable for the worry-group anchor; rebuild sequences with raw vars alongside labels
    lo, hi = f.timing_range()
    cat_of = ds.dictionary.variable_to_category
    label_of = view.label_of

    tree_people: dict[tuple[str, ...], set[int]] = defaultdict(set)
    tree_events: dict[tuple[str, ...], int] = defaultdict(int)
    anchor_people: set[int] = set()
    anchor_events = 0
    step_dn: dict[tuple[str, ...], list[int]] = defaultdict(list)

    for pid, seq in view.sequences.items():
        # pair labels with raw variables (same filtering/dedupe as the view)
        raws = _raw_aligned(ds, pid, f, label_of)
        idxs = [i for i, (lab, _dn, _st) in enumerate(seq) if _is_anchor(lab, raws[i], req.anchor)]
        if not idxs:
            continue
        anchor_people.add(pid)
        if req.occurrence == "first":
            idxs = idxs[:1]
        elif req.occurrence == "last":
            idxs = idxs[-1:]
        anchor_events += len(idxs)
        person_paths: set[tuple[str, ...]] = set()
        for i in idxs:
            path = [req.anchor]
            dns = [seq[i][1]]
            cur = i
            for _s in range(req.steps - 1):
                nxt = _follow(seq, cur, req, cat_of, raws)
                if nxt is None:
                    path.append(NO_FOLLOW)
                    dns.append(-1)
                    break
                path.append(seq[nxt][0])
                dns.append(seq[nxt][1])
                cur = nxt
            for depth in range(2, len(path) + 1):
                key = tuple(path[:depth])
                tree_events[key] += 1
                person_paths.add(key)
                if dns[depth - 1] >= 0:
                    step_dn[key].append(dns[depth - 1])
        for key in person_paths:
            tree_people[key].add(pid)

    A = len(anchor_people)
    # level tables
    levels: list[dict[str, Any]] = []
    for depth in range(2, req.steps + 1):
        rows = []
        keys = [k for k in tree_people if len(k) == depth]
        for k in sorted(keys, key=lambda x: -len(tree_people[x])):
            parent = k[:-1]
            parent_n = A if depth == 2 else len(tree_people.get(parent, ()))
            rows.append({
                "path": list(k),
                "count": len(tree_people[k]),
                "events": tree_events[k],
                "rate_of_parent": rate(len(tree_people[k]), parent_n),
                "parent_count": parent_n,
                "rate_of_anchor": rate(len(tree_people[k]), A),
                "rate_of_all": rate(len(tree_people[k]), N),
                "avg_dn": mean_or_none(step_dn[k]),
            })
        levels.append({"depth": depth, "rows": rows[: req.top_n * (3 ** (depth - 2))]})
    return {
        "anchor": req.anchor,
        "n": N,
        "anchor_count": A,
        "anchor_rate": rate(A, N),
        "anchor_events": anchor_events,
        "occurrence": req.occurrence,
        "follow": req.follow,
        "target_category": req.target_category,
        "within_days": req.within_days,
        "levels": levels,
        "filters": f.describe(),
        "notes": list(view.note) + _entry_notes(req),
        "denominators": {
            "anchor_rate": "フィルタ対象者数 n",
            "rate_of_parent": "直前ステップまでのパスを経験した人数（条件付き率）",
            "rate_of_anchor": "起点経験者数",
            "rate_of_all": "フィルタ対象者数 n（完全パス経験率）",
        },
    }


def _raw_aligned(ds: Dataset, pid: int, f: Filters, label_of) -> list[str]:
    lo, hi = f.timing_range()
    out: list[str] = []
    last = None
    seen: set[str] = set()
    for v, dn, st, _rp in ds.raw_sequences.get(pid, []):
        if lo is not None and dn < lo:
            continue
        if hi is not None and dn > hi:
            continue
        lab = label_of(v)
        if f.dedupe == "collapse_consecutive" and lab == last:
            continue
        if f.dedupe == "first_only":
            if lab in seen:
                continue
            seen.add(lab)
        out.append(v)
        last = lab
    return out


def _follow(seq, cur: int, req: EntryRequest, cat_of: dict[str, str], raws: list[str]) -> int | None:
    if req.follow == "next":
        return cur + 1 if cur + 1 < len(seq) else None
    if req.follow == "next_in_category":
        if not req.target_category:
            return cur + 1 if cur + 1 < len(seq) else None
        for j in range(cur + 1, len(seq)):
            lab = seq[j][0]
            if lab == req.target_category or cat_of.get(raws[j]) == req.target_category or raws[j] == req.target_category:
                return j
        return None
    # within_days: the immediately following action, only if it occurs within N days
    if cur + 1 >= len(seq):
        return None
    cur_dn = seq[cur][1]
    nxt_dn = seq[cur + 1][1]
    if cur_dn < 0 or nxt_dn < 0:
        return None
    return cur + 1 if (cur_dn - nxt_dn) <= req.within_days else None


def _entry_notes(req: EntryRequest) -> list[str]:
    notes = []
    if req.occurrence == "all":
        notes.append("全出現モード：イベント件数（events）とユニーク人数（count）を区別して表示。")
    if req.follow == "next_in_category":
        notes.append(f"後続は「次に {req.target_category or '（未指定→直後の行動）'} が現れる行動」。")
    if req.follow == "within_days":
        notes.append(f"後続は「{req.within_days}日以内の直後行動」。超過時は後続記録なし。")
    if req.anchor == WORRY_GROUP:
        notes.append("肌悩み検索ALL＝検索_効能/肌悩み系_（エイジング・乾燥・肌荒れ・肌トーン・○○肌）の統合。")
    return notes
