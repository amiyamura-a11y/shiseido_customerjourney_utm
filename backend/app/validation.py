"""Cross-check of existing Excel aggregates against recalculation from the CSV.

Every row carries: Excel value / recalculated value / difference / denominator /
definition used / reason when the definitions differ.
"""
from __future__ import annotations

import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from . import config
from .engine.base import Dataset, mean_or_none, rate
from .engine.paths import enumerate_paths
from .filters import Filters

WORRY_PREFIX = "検索_効能/肌悩み系_"


def _sheet(path: Path, name: str, **kw) -> pd.DataFrame:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.read_excel(path, sheet_name=name, **kw)


def _row(section: str, segment: str, item: str, xl, re_, den, definition: str, reason: str = "", unit: str = "rate") -> dict[str, Any]:
    diff = None if (xl is None or re_ is None or pd.isna(xl) or pd.isna(re_)) else float(re_) - float(xl)
    ok = diff is not None and abs(diff) < (1e-6 if unit == "rate" else 1e-3)
    return {"section": section, "segment": segment, "item": item, "excel": None if xl is None or pd.isna(xl) else float(xl),
            "recalc": None if re_ is None or pd.isna(re_) else float(re_), "diff": diff, "denominator": den, "definition": definition,
            "match": ok, "reason": reason if not ok else ""}


def check_counts(ds: Dataset) -> list[dict[str, Any]]:
    p = ds.persons
    s = ds.summary()
    rows = [
        _row("基本件数", "全体", "総人数", config.EXPECTED["total"], s["persons"], None, "CSV行数", "", "count"),
        _row("基本件数", "全体", "購入者", config.EXPECTED["buyers"], s["buyers"], None, "結果=購買", "", "count"),
        _row("基本件数", "全体", "非購入者", config.EXPECTED["nonbuyers"], s["nonbuyers"], None, "結果=非購買", "", "count"),
    ]
    for age, key in [("18～29歳", "age_18_29"), ("30～49歳", "age_30_49")]:
        b = int(((p.age_group == age) & (p.purchase_status == config.BUYER_LABEL)).sum())
        n = int(((p.age_group == age) & (p.purchase_status == config.NONBUYER_LABEL)).sum())
        rows.append(_row("基本件数", age, "購入者", config.EXPECTED[f"{key}_buyers"], b, None, "年代×結果", "", "count"))
        rows.append(_row("基本件数", age, "非購入者", config.EXPECTED[f"{key}_nonbuyers"], n, None, "年代×結果", "", "count"))
    rows.append(_row("基本件数", "全体", "平均行動数", config.EXPECTED["mean_action_count"], round(float(p.recorded_action_count.mean()), 2), s["persons"], "行動数列の平均（小数2桁）", "指示書の目安値との比較", "count"))
    rows.append(_row("基本件数", "全体", "平均観測期間（日数）", config.EXPECTED["mean_duration_days"], round(float(p.duration_days.mean()), 2), s["persons"], "日数列の平均（小数2桁）", "指示書の目安値との比較", "count"))
    rows.append(_row("基本件数", "全体", "行動数と非欠損行動列数の不一致行", 0, ds.quality.get("action_count_mismatch_rows", 0), None, "行動数 ≠ 非空行動列数", "", "count"))
    return rows


def check_additional(ds: Dataset, add_xlsx: Path | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not add_xlsx or not add_xlsx.exists():
        return rows
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        xl = pd.ExcelFile(add_xlsx)
    for age_key, age_label in config.AGE_LABELS.items():
        sheet = next((s for s in xl.sheet_names if "個別変数の出現" in s and age_label[:2] in s), None)
        if not sheet:
            continue
        df = _sheet(add_xlsx, sheet)
        f = Filters(age=age_key, result="buyer", granularity="variable")
        view = ds.view(f)
        N = view.n
        exp: dict[str, set[int]] = defaultdict(set)
        dn_all: dict[str, list[int]] = defaultdict(list)
        dn_first: dict[str, list[int]] = defaultdict(list)
        dn_last: dict[str, list[int]] = defaultdict(list)
        for pid, seq in view.sequences.items():
            firsts: dict[str, int] = {}
            lasts: dict[str, int] = {}
            for lab, dn, _ in seq:
                keys = [lab]
                if lab.startswith(WORRY_PREFIX) and not lab.endswith("_アルティミューン"):
                    keys.append(WORRY_PREFIX + "ALL")
                for k in keys:
                    exp[k].add(pid)
                    dn_all[k].append(dn)
                    firsts.setdefault(k, dn)
                    lasts[k] = dn
            for k, v in firsts.items():
                dn_first[k].append(v)
            for k, v in lasts.items():
                dn_last[k].append(v)
        for _, r in df.head(60).iterrows():
            v = str(r.get("個別変数", "")).strip()
            if not v:
                continue
            c = len(exp.get(v, ()))
            rows.append(_row("追加集計：個別変数出現率", f"{age_label}購入者", v, r.get("出現率"), rate(c, N), N, "1回以上経験したユニーク人数÷購入者数", "Excelとの定義差（要確認）"))
            m_all, m_first, m_last = mean_or_none(dn_all.get(v, [])), mean_or_none(dn_first.get(v, [])), mean_or_none(dn_last.get(v, []))
            rows.append(_row("追加集計：平均発生時期", f"{age_label}購入者", v, r.get("平均購買何日前か"), m_all, c,
                             "全イベントのD−n平均（参考：初回出現平均=%s／最終出現平均=%s）" % (None if m_first is None else round(m_first, 2), None if m_last is None else round(m_last, 2)),
                             "Excelの『平均購買何日前か』の算出定義は資料に記載なし。全出現／初回／最終のいずれとも一致しないため定義未確認として差分表示", "count"))
        # worry-keyword start paths
        wsheet = next((s for s in xl.sheet_names if "悩み系KW" in s and age_label[:2].replace("～", "") in s.replace("~", "")), None)
        if wsheet:
            w = _sheet(add_xlsx, wsheet, header=None)
            nxt: dict[str, set[int]] = defaultdict(set)
            worry_people: set[int] = set()
            for pid, seq in view.sequences.items():
                idx = next((i for i, (lab, _, _) in enumerate(seq) if lab.startswith(WORRY_PREFIX) and not lab.endswith("_アルティミューン")), None)
                if idx is None:
                    continue
                worry_people.add(pid)
                nxt[seq[idx + 1][0] if idx + 1 < len(seq) else "後続記録なし"].add(pid)
            A = len(worry_people)
            for i in range(4, len(w)):
                second = w.iat[i, 2] if w.shape[1] > 2 else None
                val = w.iat[i, 3] if w.shape[1] > 3 else None
                if isinstance(second, str) and second.strip() and pd.notna(val) and isinstance(val, (int, float)):
                    key = "後続記録なし" if "後続" in second else second.strip()
                    rows.append(_row("追加集計：悩み検索起点2接点", f"{age_label}購入者", f"肌悩み検索ALL → {key}", val, rate(len(nxt.get(key, ())), A), A,
                                     "悩み検索の初回出現の直後行動／分母＝悩み検索経験者", "Excelは『後続記録なし』を即購買と表記しているが本アプリでは観測終了として扱う"))
            # 3-step section (columns 5..9): 1番目,2番目,3番目, 悩み検索者の中で見られた割合, 2番目経験者の中で
            third: dict[tuple[str, str], set[int]] = defaultdict(set)
            second_people: dict[str, set[int]] = defaultdict(set)
            for pid, seq in view.sequences.items():
                idx = next((i for i, (lab, _, _) in enumerate(seq) if lab.startswith(WORRY_PREFIX) and not lab.endswith("_アルティミューン")), None)
                if idx is None or idx + 1 >= len(seq):
                    continue
                s2 = seq[idx + 1][0]
                second_people[s2].add(pid)
                s3 = seq[idx + 2][0] if idx + 2 < len(seq) else "後続記録なし"
                third[(s2, s3)].add(pid)
            for i in range(4, len(w)):
                if w.shape[1] < 10:
                    break
                s2, s3, v_all, v_cond = w.iat[i, 6], w.iat[i, 7], w.iat[i, 8], w.iat[i, 9]
                if isinstance(s2, str) and isinstance(s3, str) and pd.notna(v_all):
                    s3k = "後続記録なし" if "後続" in s3 else s3.strip()
                    c3 = len(third.get((s2.strip(), s3k), ()))
                    rows.append(_row("追加集計：悩み検索起点3接点", f"{age_label}購入者", f"肌悩み検索ALL → {s2.strip()} → {s3k}", v_all, rate(c3, A), A,
                                     "初回悩み検索→直後→その直後の完全パス人数÷悩み検索経験者（個票から直接計算）",
                                     "Excelの3接点率は率の積で算出された形跡があり（人数が整数にならない）、個票直接計算とは定義が異なる"))
                    if pd.notna(v_cond):
                        rows.append(_row("追加集計：悩み検索起点3接点（条件付き）", f"{age_label}購入者", f"{s2.strip()} → {s3k}｜分母=悩み→{s2.strip()}経験者", v_cond, rate(c3, len(second_people.get(s2.strip(), ()))), len(second_people.get(s2.strip(), ())),
                                         "2番目まで一致した人の中で3番目が一致した割合", "Excel側の分母定義が異なる可能性"))
    return rows


def check_path_priority(ds: Dataset, main_xlsx: Path | None, per_segment: int = 8) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not main_xlsx or not main_xlsx.exists():
        return rows
    for sheet, gran in [("❷パスの優先度_個別項目（検討期間毎）", "variable"), ("❷パスの優先度_カテゴライズ（検討期間毎）", "category"),
                        ("❷パスの優先度_個別項目（行動発生時期）", "variable"), ("❷パスの優先度_カテゴライズ（行動発生時期）", "category")]:
        try:
            df = _sheet(main_xlsx, sheet, header=1)
        except Exception:
            continue
        for (age, narrow, period), g in df.groupby(["年代", "絞り方", "対象期間"]):
            age_key = "18-29" if "18" in str(age) else "30-49"
            lo, hi = _period_range(str(period))
            if narrow == "人の検討日数":
                fb = Filters(age=age_key, result="buyer", granularity=gran, duration_preset="custom", duration_min=lo, duration_max=hi)
                definition = f"人の観測期間 {lo}〜{hi}日の人に限定した隣接2接点パス（ユニーク人数）"
            else:
                fb = Filters(age=age_key, result="buyer", granularity=gran, timing_preset="custom", timing_min=lo, timing_max=hi)
                definition = f"行動発生時期 D−{hi}〜D−{lo} に抽出後の隣接2接点パス（期間内抽出後の隣接）"
            fn = fb.model_copy(update={"result": "nonbuyer"})
            vb, vn = ds.view(fb), ds.view(fn)
            pb, _, _ = enumerate_paths(vb, 2, "consecutive")
            pn, _, _ = enumerate_paths(vn, 2, "consecutive")
            for _, r in g.head(per_segment).iterrows():
                parts = [x.strip() for x in str(r["パス"]).split("→")]
                if len(parts) != 2:
                    continue
                key = tuple(parts)
                cb, cn = len(pb.get(key, ())), len(pn.get(key, ()))
                seg = f"{age}｜{narrow}｜{period}｜{'個別変数' if gran == 'variable' else 'カテゴリ'}"
                rows.append(_row(f"パス優先度：{sheet}", seg, f"{parts[0]} → {parts[1]}（購入者内出現率）", r["購買者内出現率"], rate(cb, vb.n), vb.n, definition, "期間の境界定義または隣接定義の差"))
                rows.append(_row(f"パス優先度：{sheet}", seg, f"{parts[0]} → {parts[1]}（非購入者内出現率）", r["非購買者内出現率"], rate(cn, vn.n), vn.n, definition, "期間の境界定義または隣接定義の差"))
    return rows


def _period_range(period: str) -> tuple[int, int]:
    s = period.split("：")[-1].replace("日", "")
    a, b = s.split("～")
    return int(a), int(b)


def implied_prior(main_xlsx: Path | None) -> dict[str, Any]:
    """Reverse-engineer the prior purchase rate assumed by 推計UTM購買率 = p·r_b / (p·r_b + (1−p)·r_n)."""
    if not main_xlsx or not main_xlsx.exists():
        return {}
    try:
        df = _sheet(main_xlsx, "❷パスの優先度_個別項目（検討期間毎）", header=1)
    except Exception:
        return {}
    df = df[df["推計UTM購買率"].notna() & (df["非購買者内出現率"] > 0) & (df["購買者内出現率"] > 0)]
    rp, rn, post = df["購買者内出現率"], df["非購買者内出現率"], df["推計UTM購買率"]
    p = (post * rn) / (rp - post * rp + post * rn)
    out = {}
    for age, g in p.groupby(df["年代"]):
        out[str(age)] = {"prior": float(g.median()), "min": float(g.min()), "max": float(g.max()), "rows": int(len(g))}
    return {"formula": "推計UTM購買率 = p·購買者内出現率 ÷ (p·購買者内出現率 + (1−p)·非購買者内出現率)", "implied_prior_by_age": out,
            "note": "p（事前購買率）は資料に明記がなく、既存Excelの値から逆算した推計前提。本アプリでは別指標として注記付きで表示する。"}


def run_validation(ds: Dataset, inputs: dict) -> dict[str, Any]:
    main_x = inputs.get("main_xlsx")
    add_x = inputs.get("additional_xlsx")
    rows = check_counts(ds)
    rows += check_additional(ds, add_x.path if add_x else None)
    rows += check_path_priority(ds, main_x.path if main_x else None)
    n_match = sum(1 for r in rows if r["match"])
    return {
        "rows": rows,
        "summary": {"total": len(rows), "match": n_match, "mismatch": len(rows) - n_match},
        "implied_prior": implied_prior(main_x.path if main_x else None),
    }
