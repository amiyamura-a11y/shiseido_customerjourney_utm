"""Variable dictionary: individual variable -> analysis category -> broad category.

* analysis category comes from the ``マスタ`` sheet of the main Excel
  (columns 変数 / 分析用カテゴリ).
* broad category is the first ``_`` token of the variable name
  (検索／外部サイト／自社サイト／競合検索／LISA) as decided with the user.
* the processing-definition Excel (06) is read to list mismatches only; it never
  overrides the master.
"""
from __future__ import annotations

import hashlib
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

BROAD_LABELS = {
    "検索": "検索",
    "外部サイト": "外部サイト",
    "自社サイト": "自社サイト",
    "競合検索": "競合検索",
    "LISA": "LISAタイアップ記事",
}


def broad_of(variable: str) -> str:
    head = str(variable).split("_", 1)[0]
    return BROAD_LABELS.get(head, "その他")


@dataclass
class Dictionary:
    variable_to_category: dict[str, str] = field(default_factory=dict)
    variable_to_broad: dict[str, str] = field(default_factory=dict)
    source: dict[str, Any] = field(default_factory=dict)
    mismatches: list[dict[str, Any]] = field(default_factory=list)
    processing_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        h = hashlib.sha1()
        for k in sorted(self.variable_to_category):
            h.update(f"{k}={self.variable_to_category[k]};".encode())
        return h.hexdigest()[:10]

    @property
    def categories(self) -> list[str]:
        return sorted(set(self.variable_to_category.values()))

    def table(self) -> list[dict[str, Any]]:
        return [
            {"individual_variable": v, "analysis_category": c, "broad_category": self.variable_to_broad.get(v, broad_of(v))}
            for v, c in sorted(self.variable_to_category.items(), key=lambda x: (x[1], x[0]))
        ]

    def extend_with_observed(self, observed: list[str]) -> list[str]:
        """Add variables observed in the CSV but absent from the master as 未分類."""
        added = []
        for v in observed:
            if v and v not in self.variable_to_category:
                self.variable_to_category[v] = "未分類"
                self.variable_to_broad[v] = broad_of(v)
                added.append(v)
        return added


def _read_sheet(path: Path, name: str, **kw) -> pd.DataFrame:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.read_excel(path, sheet_name=name, **kw)


def load_master(main_xlsx: Path | None) -> Dictionary:
    d = Dictionary()
    if main_xlsx is None or not main_xlsx.exists():
        d.source = {"master_sheet": None, "note": "マスタExcel未検出。変数は未分類扱い。"}
        return d
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        xl = pd.ExcelFile(main_xlsx)
    sheet = next((s for s in xl.sheet_names if "マスタ" in s), None)
    if sheet is None:
        d.source = {"master_sheet": None, "note": "マスタシート未検出"}
        return d
    m = _read_sheet(main_xlsx, sheet, dtype=str).fillna("")
    cols = [str(c).strip() for c in m.columns]
    m.columns = cols
    var_col = next((c for c in cols if c in ("変数", "個別変数")), cols[0])
    cat_col = next((c for c in cols if "カテゴリ" in c), cols[1] if len(cols) > 1 else cols[0])
    for _, r in m.iterrows():
        v = str(r[var_col]).strip()
        c = str(r[cat_col]).strip()
        if v:
            d.variable_to_category[v] = c or "未分類"
            d.variable_to_broad[v] = broad_of(v)
    d.source = {
        "master_sheet": sheet,
        "file": main_xlsx.name,
        "variable_column": var_col,
        "category_column": cat_col,
        "n_variables": len(d.variable_to_category),
        "broad_rule": "変数名の先頭語（検索／外部サイト／自社サイト／競合検索／LISA）",
    }
    return d


def _norm(s: str) -> str:
    """Loose normalisation used only to detect notation differences (never for mapping)."""
    s = str(s).strip()
    s = s.replace("＠", "@").replace("！", "!").replace("　", " ")
    s = re.sub(r"\s+", " ", s)
    s = s.replace("Ⅱ", "II").replace("ＳＫ", "SK")
    return s.lower()


def compare_with_processing_definitions(d: Dictionary, processing_xlsx: Path | None) -> None:
    """Populate d.mismatches with differences between master and the 06 definition workbook."""
    d.mismatches = []
    if processing_xlsx is None or not processing_xlsx.exists():
        d.processing_summary = {"file": None, "note": "加工定義Excel未検出"}
        return
    master = set(d.variable_to_category)
    master_norm = {_norm(v): v for v in master}
    summary: dict[str, Any] = {"file": processing_xlsx.name, "sheets": {}}

    def add(kind: str, defined: str, sheet: str, reason: str, master_hit: str | None = None):
        d.mismatches.append({"kind": kind, "defined_name": defined, "sheet": sheet, "reason": reason, "master_variable": master_hit})

    # 01 search keywords -> 検索_<大区分>_<中区分>
    try:
        kw = _read_sheet(processing_xlsx, "01_検索KW", header=4, dtype=str).fillna("")
        kw.columns = [str(c).strip() for c in kw.columns]
        big = next(c for c in kw.columns if c.startswith("KW分類_大区分"))
        mid = next(c for c in kw.columns if c.startswith("KW分類_中区分"))
        derived = {f"検索_{a.strip()}_{b.strip()}" for a, b in zip(kw[big], kw[mid]) if a.strip()}
        summary["sheets"]["01_検索KW"] = {"rows": int(len(kw)), "derived_variables": len(derived)}
        for name in sorted(derived - master):
            hit = master_norm.get(_norm(name))
            add("定義のみ（CSV/マスタ未出現）" if not hit else "表記揺れ", name, "01_検索KW",
                "加工定義から導かれる変数名がマスタに存在しない" if not hit else "全角/半角・空白等の表記差", hit)
        for v in sorted(v for v in master if v.startswith("検索_") and v not in derived):
            if _norm(v) not in {_norm(x) for x in derived}:
                add("マスタのみ（定義未記載）", v, "01_検索KW", "マスタ変数が加工定義シートから導出できない")
    except Exception as e:  # pragma: no cover
        summary["sheets"]["01_検索KW"] = {"error": str(e)}
    # 02 external sites -> 外部サイト_<サイト分類>_<サイト名>
    try:
        ex = _read_sheet(processing_xlsx, "02_外部サイト", header=4, dtype=str).fillna("")
        ex.columns = [str(c).strip() for c in ex.columns]
        derived = {f"外部サイト_{a.strip()}_{b.strip()}" for a, b in zip(ex["サイト分類"], ex["サイト名"]) if a.strip()}
        summary["sheets"]["02_外部サイト"] = {"rows": int(len(ex)), "derived_variables": len(derived)}
        dn = {_norm(x) for x in derived}
        for name in sorted(derived - master):
            hit = master_norm.get(_norm(name))
            add("表記揺れ" if hit else "定義のみ（CSV/マスタ未出現）", name, "02_外部サイト",
                "全角/半角・空白等の表記差" if hit else "加工定義のサイトがマスタに存在しない", hit)
        for v in sorted(v for v in master if v.startswith("外部サイト_") and v not in derived and _norm(v) not in dn):
            add("マスタのみ（定義未記載）", v, "02_外部サイト", "マスタ変数が加工定義シートに無い")
    except Exception as e:  # pragma: no cover
        summary["sheets"]["02_外部サイト"] = {"error": str(e)}
    # 06 competitor: brand-level definitions vs price-tier variables in CSV
    try:
        comp = _read_sheet(processing_xlsx, "06_競合検索_サイト来訪", header=4, dtype=str).fillna("")
        comp.columns = [str(c).strip() for c in comp.columns]
        names = sorted({x.strip() for x in comp.get("分析用変数名", pd.Series(dtype=str)) if x.strip()})
        tiers = sorted({x.strip() for x in comp.get("カテゴリ（3ブランド以上）", pd.Series(dtype=str)) if x.strip()})
        summary["sheets"]["06_競合検索_サイト来訪"] = {"brand_level_variables": len(names), "price_tiers": tiers}
        add("粒度差", "ブランド別（例: " + ", ".join(names[:3]) + " …）", "06_競合検索_サイト来訪",
            "加工定義はブランド別だが、CSVは価格帯別（競合検索_高価格帯デパコス美容液 等）に集約済み")
    except Exception as e:  # pragma: no cover
        summary["sheets"]["06_競合検索_サイト来訪"] = {"error": str(e)}
    # 05 talent articles
    try:
        other = _read_sheet(processing_xlsx, "05_26SSタレント_RP記事_その他", header=4, dtype=str).fillna("")
        summary["sheets"]["05_26SSタレント_RP記事"] = {"other_talent_rows": int(len(other))}
        add("定義のみ（CSV/マスタ未出現）", "その他タレント記事（Deep/Light）", "05_26SSタレント_RP記事_その他",
            "CSVには LISA_Deep / LISA_Light のみ出現")
    except Exception as e:  # pragma: no cover
        summary["sheets"]["05_26SSタレント_RP記事"] = {"error": str(e)}
    # 変数加工 sheet items not in CSV
    try:
        vp = _read_sheet(processing_xlsx, "変数加工", header=1, dtype=str).fillna("")
        vp.columns = [str(c).strip() for c in vp.columns]
        items = [x.strip() for x in vp.get("大区分", pd.Series(dtype=str)) if x.strip()]
        missing = [i for i in items if not any(i in v for v in master)]
        summary["sheets"]["変数加工"] = {"items": len(items), "not_in_master": missing}
        for i in missing:
            add("定義のみ（CSV/マスタ未出現）", i, "変数加工", "変数加工シートの項目がマスタ変数名に含まれない")
    except Exception as e:  # pragma: no cover
        summary["sheets"]["変数加工"] = {"error": str(e)}
    d.processing_summary = summary
