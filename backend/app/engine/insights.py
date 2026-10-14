"""Auto-generated 考察 (insight) text per page.

Every sentence is built only from counts recomputed from the individual records
under the current common filters (granularity, grouping, exclusions, duration and
timing windows). The age / result filters are overridden so that each section
describes the buyers of one age group against the non-buyers of the same age.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from .. import config
from ..filters import Filters
from .base import Dataset, mean_or_none, rate
from .entry import EntryRequest, entry_analysis
from .graph import GraphRequest, OTHER, OUTCOME_BUY, build_graph
from .paths import enumerate_paths
from .timeline import WINDOWS

AGES = [("18-29", "18–29歳"), ("30-49", "30–49歳")]
CAVEAT = "考察は個票の集計値から自動生成しています（粒度・変数統合・除外・期間などの共通フィルタを反映）。購入者に多い行動・パスは購入者サンプル内での出現率差であり、購買の因果効果を意味しません。5人未満のセルは参考値です。"


class InsightRequest(BaseModel):
    page: str
    filters: Filters = Field(default_factory=Filters)
    steps: int = Field(default=5, ge=2, le=config.MAX_STEPS)
    mode: str = "head"
    anchor: str | None = None
    top_n: int = Field(default=8, ge=3, le=15)
    other_mode: str = "show"
    entry_anchor: str | None = None
    compare_a: Filters | None = None
    compare_b: Filters | None = None
    label_a: str = "A"
    label_b: str = "B"


def _p(v: float | None, d: int = 1) -> str:
    return "算出不可" if v is None else f"{v * 100:.{d}f}%"


def _pt(v: float) -> str:
    return f"{'+' if v > 0 else ''}{v * 100:.1f}pt"


def _n(v: float | None, d: int = 1) -> str:
    return "–" if v is None else f"{v:,.{d}f}"


def _exp(ds: Dataset, f: Filters) -> tuple[dict[str, set[int]], int, dict[str, list[int]]]:
    v = ds.view(f)
    exp: dict[str, set[int]] = defaultdict(set)
    dn: dict[str, list[int]] = defaultdict(list)
    for pid, seq in v.sequences.items():
        for lab, d, _ in seq:
            exp[lab].add(pid)
            if d >= 0:
                dn[lab].append(d)
    return exp, v.n, dn


def _diffs(ds: Dataset, fb: Filters, fn: Filters) -> list[dict[str, Any]]:
    eb, nb, _ = _exp(ds, fb)
    en, nn, _ = _exp(ds, fn)
    rows = []
    for lab in set(eb) | set(en):
        cb, cn = len(eb.get(lab, ())), len(en.get(lab, ()))
        if max(cb, cn) < config.SMALL_CELL_THRESHOLD:
            continue
        rb, rn = rate(cb, nb), rate(cn, nn)
        if rb is None or rn is None:
            continue
        rows.append({"label": lab, "rb": rb, "rn": rn, "diff": rb - rn, "cb": cb, "cn": cn})
    rows.sort(key=lambda r: -r["diff"])
    return rows


def _seg_filters(f: Filters, age: str) -> tuple[Filters, Filters]:
    return f.model_copy(update={"age": age, "result": "buyer"}), f.model_copy(update={"age": age, "result": "nonbuyer"})


def _fmt_diff(r: dict[str, Any]) -> str:
    return f"「{r['label']}」（{_p(r['rb'])} vs {_p(r['rn'])}、{_pt(r['diff'])}）"


def _overview(ds: Dataset, f: Filters, age: str) -> list[str]:
    fb, fn = _seg_filters(f, age)
    vb, vn = ds.view(fb), ds.view(fn)
    if vb.n == 0:
        return ["対象なし（条件に該当する購入者がいません）。"]
    pb, pn = ds.person_frame(vb.person_ids), (ds.person_frame(vn.person_ids) if vn.n else None)
    out = [f"購入者 n={vb.n:,}（同年代の非購入者 n={vn.n:,}）。平均行動数は {_n(float(pb['recorded_action_count'].mean()))}" + (f"（非購入者 {_n(float(pn['recorded_action_count'].mean()))}）" if pn is not None else "") + f"、平均観測期間は {_n(float(pb['duration_days'].mean()))}日" + (f"（非購入者 {_n(float(pn['duration_days'].mean()))}日）。" if pn is not None else "。")]
    rows = _diffs(ds, fb, fn)
    pos = [r for r in rows if r["diff"] > 0][:3]
    neg = [r for r in rows if r["diff"] < 0][-2:]
    if pos:
        out.append("非購入者より経験率が高い行動は " + "、".join(_fmt_diff(r) for r in pos) + "。")
    if neg:
        out.append("逆に非購入者の方が高いのは " + "、".join(_fmt_diff(r) for r in reversed(neg)) + "。")
    return out


def _golden(ds: Dataset, req: InsightRequest, age: str) -> list[str]:
    fb, fn = _seg_filters(req.filters, age)
    g = build_graph(ds, GraphRequest(filters=fb, steps=req.steps, mode=req.mode if req.mode != "anchor" or req.anchor else "head", anchor=req.anchor, top_n=req.top_n, other_mode=req.other_mode, include_rankings=True))
    if g["n"] == 0:
        return ["対象なし。"]
    out = []
    first = [n for n in g["nodes"] if n["step"] == 1 and n["kind"] == "action"][:2]
    if first:
        out.append(f"購入者 n={g['n']:,}。{g['columns'][0]['label']} で多いのは " + "、".join(f"「{n['label']}」{_p(n['rate'])}" for n in first) + "。")
    buy, more = g["censoring"]["buy"], g["censoring"]["more_actions"]
    out.append(f"表示範囲（{g['steps']}ステップ）内で観測が終わり購入に至る人は {buy:,}人（{_p(rate(buy, g['n']))}）、{more:,}人（{_p(rate(more, g['n']))}）は表示範囲の後にも行動があります。")
    tp = g["rankings"]["top_paths"]["2"]["rows"][:2]
    if tp:
        out.append("最も多い2ステップの連続パスは " + "、".join(f"「{' → '.join(r['path'])}」{r['count']:,}人（{_p(r['rate'])}）" for r in tp) + "。")
    bc = [r for r in g["rankings"]["buyer_characteristic"]["2"]["rows"] if not r["small_cell"]][:2]
    if bc:
        out.append("同年代の非購入者と比べて購入者に特徴的なパスは " + "、".join(f"「{' → '.join(r['path'])}」（{_p(r['buyer_rate'])} vs {_p(r['nonbuyer_rate'])}）" for r in bc) + "。")
    return out


def _compare_age(ds: Dataset, f: Filters, age: str) -> list[str]:
    fb, fn = _seg_filters(f, age)
    rows = _diffs(ds, fb, fn)
    if not rows:
        return ["対象なし。"]
    out = ["非購入者との経験率差（pt）が大きい行動: " + "、".join(_fmt_diff(r) for r in rows[:3]) + "。"]
    vb, vn = ds.view(fb), ds.view(fn)
    pb, _, _ = enumerate_paths(vb, 2, f.path_mode)
    pn, _, _ = enumerate_paths(vn, 2, f.path_mode)
    prow = []
    for p, s in pb.items():
        cb, cn = len(s), len(pn.get(p, ()))
        if cb < config.SMALL_CELL_THRESHOLD:
            continue
        rb, rn = rate(cb, vb.n), rate(cn, vn.n)
        prow.append((p, rb, rn, (rb or 0) - (rn or 0)))
    prow.sort(key=lambda x: -x[3])
    if prow:
        out.append("2ステップパスの差が大きいのは " + "、".join(f"「{' → '.join(p)}」（{_p(rb)} vs {_p(rn)}）" for p, rb, rn, _ in prow[:2]) + "。")
    return out


def _compare_ab(ds: Dataset, req: InsightRequest) -> list[str]:
    if req.compare_a is None or req.compare_b is None:
        return []
    ea, na, _ = _exp(ds, req.compare_a)
    eb, nb, _ = _exp(ds, req.compare_b)
    rows = []
    for lab in set(ea) | set(eb):
        ca, cb = len(ea.get(lab, ())), len(eb.get(lab, ()))
        if max(ca, cb) < config.SMALL_CELL_THRESHOLD:
            continue
        ra, rb = rate(ca, na), rate(cb, nb)
        if ra is None or rb is None:
            continue
        rows.append({"label": lab, "rb": ra, "rn": rb, "diff": ra - rb})
    rows.sort(key=lambda r: -r["diff"])
    out = [f"{req.label_a}（n={na:,}）と {req.label_b}（n={nb:,}）の比較。"]
    if rows:
        out.append(f"{req.label_a} の方が高い行動: " + "、".join(_fmt_diff(r) for r in rows[:3] if r["diff"] > 0) + "。")
        neg = [r for r in rows if r["diff"] < 0][-2:]
        if neg:
            out.append(f"{req.label_b} の方が高い行動: " + "、".join(_fmt_diff(r) for r in reversed(neg)) + "。")
    return out


def _timeline(ds: Dataset, f: Filters, age: str) -> list[str]:
    fb, fn = _seg_filters(f.model_copy(update={"timing_preset": "all", "timing_min": None, "timing_max": None}), age)
    vb, vn = ds.view(fb), ds.view(fn)
    if vb.n == 0:
        return ["対象なし。"]

    def win(v):
        w: dict[tuple[str, str], set[int]] = defaultdict(set)
        for pid, seq in v.sequences.items():
            for lab, dn, _ in seq:
                for wname, lo, hi in WINDOWS:
                    if lo <= dn <= hi:
                        w[(wname, lab)].add(pid)
        return w

    wb, wn = win(vb), win(vn)
    out = [f"購入者 n={vb.n:,}。"]
    parts = []
    for wname, _lo, _hi in WINDOWS:
        rows = sorted(((lab, len(s)) for (w, lab), s in wb.items() if w == wname), key=lambda x: -x[1])[:2]
        if rows:
            parts.append(f"{wname}: " + "、".join(f"「{lab}」{_p(rate(c, vb.n))}" for lab, c in rows))
    if parts:
        out.append("時期別に経験率が高い行動は " + "／".join(parts) + "。")
    last = []
    for (w, lab), s in wb.items():
        if w != "D−7〜0" or len(s) < config.SMALL_CELL_THRESHOLD:
            continue
        rb, rn = rate(len(s), vb.n), rate(len(wn.get((w, lab), ())), vn.n)
        if rb is not None and rn is not None:
            last.append((lab, rb, rn, rb - rn))
    last.sort(key=lambda x: -x[3])
    if last:
        out.append("基準日直前（D−7〜0）に非購入者より多い行動は " + "、".join(f"「{lab}」（{_p(rb)} vs {_p(rn)}、{_pt(d)}）" for lab, rb, rn, d in last[:3]) + "。")
    return out


def _entry(ds: Dataset, req: InsightRequest, age: str) -> list[str]:
    if not req.entry_anchor:
        return ["起点が未選択です。"]
    fb, fn = _seg_filters(req.filters, age)
    rb = entry_analysis(ds, EntryRequest(filters=fb, anchor=req.entry_anchor, steps=2, top_n=5))
    rn = entry_analysis(ds, EntryRequest(filters=fn, anchor=req.entry_anchor, steps=2, top_n=5))
    if rb["n"] == 0:
        return ["対象なし。"]
    out = [f"起点「{req.entry_anchor}」の経験率は購入者 {_p(rb['anchor_rate'])}（{rb['anchor_count']:,}/{rb['n']:,}）、非購入者 {_p(rn['anchor_rate'])}（{rn['anchor_count']:,}/{rn['n']:,}）。"]
    nb = [r for r in rb["levels"][0]["rows"] if r["path"][-1] != "後続記録なし"][:2] if rb["levels"] else []
    nn = [r for r in rn["levels"][0]["rows"] if r["path"][-1] != "後続記録なし"][:1] if rn["levels"] else []
    if nb:
        out.append("起点の直後に多い行動（購入者、分母＝起点経験者）は " + "、".join(f"「{r['path'][-1]}」{_p(r['rate_of_parent'])}" for r in nb) + ("、非購入者では " + "、".join(f"「{r['path'][-1]}」{_p(r['rate_of_parent'])}" for r in nn) if nn else "") + "。")
    return out


def _search(ds: Dataset, f: Filters, age: str) -> list[str]:
    fb, fn = _seg_filters(f, age)
    vb, vn = ds.view(fb), ds.view(fn)
    if vb.n == 0:
        return ["対象なし。"]
    out = []
    for k in (2, 3):
        pb, _, _ = enumerate_paths(vb, k, f.path_mode)
        pn, _, _ = enumerate_paths(vn, k, f.path_mode)
        rows = []
        for p, s in pb.items():
            cb, cn = len(s), len(pn.get(p, ()))
            if cb < config.SMALL_CELL_THRESHOLD:
                continue
            rb, rn = rate(cb, vb.n), rate(cn, vn.n)
            rows.append((p, cb, rb, rn, (rb or 0) - (rn or 0)))
        if not rows:
            continue
        top = max(rows, key=lambda x: x[1])
        diff = max(rows, key=lambda x: x[4])
        out.append(f"{k}ステップ: 最も多いのは「{' → '.join(top[0])}」{top[1]:,}人（{_p(top[2])}）、非購入者との差が最大なのは「{' → '.join(diff[0])}」（{_p(diff[2])} vs {_p(diff[3])}）。")
    return out


def _dictionary(ds: Dataset) -> list[str]:
    s = ds.summary()
    q = ds.quality
    p = ds.persons
    parts = []
    for key, label in AGES:
        a = config.AGE_LABELS[key]
        b = int(((p.age_group == a) & (p.purchase_status == config.BUYER_LABEL)).sum())
        n = int(((p.age_group == a) & (p.purchase_status == config.NONBUYER_LABEL)).sum())
        parts.append(f"{label}: 購入者 {b:,}／非購入者 {n:,}")
    return [
        f"個票 {s['persons']:,}人・{s['events']:,}行動を読み込み、{s['variables']}個別変数を{s['categories']}分析カテゴリに分類（" + "、".join(parts) + "）。",
        f"品質検査: 行動数と非欠損列数の不一致 {q.get('action_count_mismatch_rows', 0)}行、D−n解析エラー {q.get('parse_error_events', 0)}件、マスタ未対応変数 {len(q.get('unmapped_variables', []))}種、25列上限到達 {q.get('reached_25_rows', 0)}人。",
    ]


def insights(ds: Dataset, req: InsightRequest) -> dict[str, Any]:
    f = req.filters
    sections: list[dict[str, Any]] = []
    if req.page == "dictionary":
        sections.append({"title": "データの要約", "paragraphs": _dictionary(ds)})
        return {"sections": sections, "caveat": "数値は読み込み時の検査結果です。", "basis": f.describe()}
    if req.page == "compare":
        ab = _compare_ab(ds, req)
        if ab:
            sections.append({"title": f"{req.label_a} vs {req.label_b}", "paragraphs": ab})
    for key, label in AGES:
        fb, _ = _seg_filters(f, key)
        nb = ds.view(fb).n
        title = f"{label} 購入者（n={nb:,}）"
        if req.page == "overview":
            paras = _overview(ds, f, key)
        elif req.page == "golden-path":
            paras = _golden(ds, req, key)
        elif req.page == "compare":
            paras = _compare_age(ds, f, key)
        elif req.page == "timeline":
            paras = _timeline(ds, f, key)
        elif req.page == "entry":
            paras = _entry(ds, req, key)
        elif req.page == "search":
            paras = _search(ds, f, key)
        else:
            paras = []
        sections.append({"title": title, "paragraphs": paras})
    return {"sections": sections, "caveat": CAVEAT, "basis": f.describe()}
