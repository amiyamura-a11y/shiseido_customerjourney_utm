"""Input discovery, inspection and normalisation of the individual-level CSV.

The CSV (one row per person) is normalised into two tables:

* persons(person_id, age_group, purchase_status, journey_type, start_period,
          duration_days, recorded_action_count)
* events(person_id, step_index, days_before_reference, raw_action,
         individual_variable, analysis_category, broad_category, repeat_index)

Both are cached as Parquet under data/processed. The raw files are never modified.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from . import config
from .parsing import parse_action

ACTION_COL_RE = re.compile(r"^\s*行動\s*(\d{1,2})\s*$")

# column name normalisation: canonical -> accepted variants (after whitespace strip)
COLUMN_ALIASES: dict[str, list[str]] = {
    "年代": ["年代", "年齢", "年齢層", "age", "age_group"],
    "結果": ["結果", "購買結果", "購入有無", "result", "purchase_status"],
    "タイプ分類": ["タイプ分類", "タイプ", "journey_type"],
    "開始期": ["開始期", "開始時期", "start_period"],
    "日数": ["日数", "期間", "観測日数", "duration_days", "days"],
    "行動数": ["行動数", "行動回数", "action_count"],
}


@dataclass
class InputFile:
    role: str
    path: Path | None
    exists: bool
    size_bytes: int = 0
    modified: str | None = None
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "path": str(self.path) if self.path else None,
            "name": self.path.name if self.path else None,
            "exists": self.exists,
            "size_bytes": self.size_bytes,
            "modified": self.modified,
            "note": self.note,
        }


def _find(patterns: list[str], directory: Path, exclude: set[Path] | None = None) -> Path | None:
    exclude = exclude or set()
    for pat in patterns:
        hits = sorted(p for p in directory.glob(pat) if p.is_file() and p not in exclude and not p.name.startswith("~$"))
        if hits:
            return hits[0]
    return None


def discover_inputs(raw_dir: Path | None = None, csv_override: Path | None = None) -> dict[str, InputFile]:
    raw_dir = raw_dir or config.RAW_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    main_x = _find(config.MAIN_XLSX_PATTERNS, raw_dir)
    add_x = _find(config.ADDITIONAL_XLSX_PATTERNS, raw_dir)
    proc_x = _find(config.PROCESSING_XLSX_PATTERNS, raw_dir)
    csv = csv_override or _find(config.CSV_PATTERNS, raw_dir)
    out: dict[str, InputFile] = {}
    for role, p, note in [
        ("csv", csv, "個票CSV（正本）"),
        ("main_xlsx", main_x, "パス分析結果Excel（全パターン／マスタ／既存集計）"),
        ("additional_xlsx", add_x, "追加集計Excel（年代別出現率・悩み系KW起点パス）"),
        ("processing_xlsx", proc_x, "行動変数加工定義Excel"),
    ]:
        if p and p.exists():
            st = p.stat()
            out[role] = InputFile(role, p, True, st.st_size, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)), note)
        else:
            out[role] = InputFile(role, p, False, 0, None, note + "（未検出）")
    return out


def _normalise_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    """Return df with canonical column names, mapping used, and warnings."""
    mapping: dict[str, str] = {}
    warnings: list[str] = []
    stripped = {c: str(c).replace("﻿", "").strip() for c in df.columns}
    rename: dict[str, str] = {}
    for canonical, variants in COLUMN_ALIASES.items():
        found = None
        for orig, s in stripped.items():
            if s == canonical or s.lower() in [v.lower() for v in variants]:
                found = orig
                break
        if found is None:
            warnings.append(f"列 '{canonical}' が見つかりません")
        else:
            rename[found] = canonical
            mapping[canonical] = str(found)
    for orig, s in stripped.items():
        m = ACTION_COL_RE.match(s)
        if m:
            rename[orig] = f"行動{int(m.group(1)):02d}"
    df = df.rename(columns=rename)
    return df, mapping, warnings


def read_csv_any_encoding(path: Path) -> tuple[pd.DataFrame, str]:
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "cp932", "shift_jis", "euc_jp"):
        try:
            df = pd.read_csv(path, encoding=enc, dtype=str, keep_default_na=False)
            return df, enc
        except (UnicodeDecodeError, UnicodeError) as e:  # pragma: no cover - depends on file
            last_err = e
    raise ValueError(f"CSVの文字コードを判定できません: {last_err}")


@dataclass
class NormalisedData:
    persons: pd.DataFrame
    events: pd.DataFrame
    quality: dict[str, Any]
    source: dict[str, Any] = field(default_factory=dict)


def normalise_csv(path: Path, dictionary: "Dictionary") -> NormalisedData:  # noqa: F821
    from .dictionary import Dictionary  # local import to avoid cycle

    assert isinstance(dictionary, Dictionary)
    raw, encoding = read_csv_any_encoding(path)
    raw, col_map, col_warnings = _normalise_columns(raw)
    action_cols = sorted([c for c in raw.columns if re.match(r"^行動\d{2}$", c)])
    if not action_cols:
        raise ValueError("行動01〜行動25 の列が見つかりません")

    n = len(raw)
    persons = pd.DataFrame({
        "person_id": range(n),
        "age_group": raw.get("年代", pd.Series([""] * n)).astype(str).str.strip(),
        "purchase_status": raw.get("結果", pd.Series([""] * n)).astype(str).str.strip(),
        "journey_type": raw.get("タイプ分類", pd.Series([""] * n)).astype(str).str.strip(),
        "start_period": raw.get("開始期", pd.Series([""] * n)).astype(str).str.strip(),
    })
    persons["duration_days"] = pd.to_numeric(raw.get("日数", pd.Series([None] * n)), errors="coerce")
    persons["recorded_action_count"] = pd.to_numeric(raw.get("行動数", pd.Series([None] * n)), errors="coerce")

    # events
    pid_list: list[int] = []
    step_list: list[int] = []
    dn_list: list[int | None] = []
    raw_list: list[str] = []
    var_list: list[str] = []
    rep_list: list[int | None] = []
    err_list: list[str | None] = []
    gap_rows: list[int] = []
    values = raw[action_cols].values
    for pid in range(n):
        row = values[pid]
        seen_empty = False
        for s, cell in enumerate(row):
            text = str(cell).strip()
            if text == "":
                seen_empty = True
                continue
            if seen_empty and pid not in gap_rows:
                gap_rows.append(pid)
            p = parse_action(text)
            pid_list.append(pid)
            step_list.append(s + 1)
            dn_list.append(p.days_before_reference)
            raw_list.append(text)
            var_list.append(p.individual_variable)
            rep_list.append(p.repeat_index)
            err_list.append(p.error)
    events = pd.DataFrame({
        "person_id": pid_list,
        "step_index": step_list,
        "days_before_reference": dn_list,
        "raw_action": raw_list,
        "individual_variable": var_list,
        "repeat_index": rep_list,
        "parse_error": err_list,
    })
    events["days_before_reference"] = pd.to_numeric(events["days_before_reference"], errors="coerce")
    events["analysis_category"] = events["individual_variable"].map(dictionary.variable_to_category).fillna("未分類")
    events["broad_category"] = events["individual_variable"].map(dictionary.variable_to_broad).fillna("未分類")

    # quality
    nonempty_counts = events.groupby("person_id").size().reindex(range(n), fill_value=0)
    mismatch = int((nonempty_counts.values != persons["recorded_action_count"].fillna(-1).values).sum())
    unmapped = sorted(set(events.loc[events["analysis_category"] == "未分類", "individual_variable"]))
    dn_errors = int(events["parse_error"].notna().sum())
    nonmono = 0
    for _, g in events.groupby("person_id"):
        d = g.sort_values("step_index")["days_before_reference"].tolist()
        if any(pd.notna(d[i]) and pd.notna(d[i + 1]) and d[i] < d[i + 1] for i in range(len(d) - 1)):
            nonmono += 1
    quality = {
        "encoding": encoding,
        "column_mapping": col_map,
        "column_warnings": col_warnings,
        "action_columns": len(action_cols),
        "rows": n,
        "events": int(len(events)),
        "action_count_mismatch_rows": mismatch,
        "gap_rows": len(gap_rows),
        "parse_error_events": dn_errors,
        "parse_error_examples": events.loc[events["parse_error"].notna(), "raw_action"].head(10).tolist(),
        "unmapped_variables": unmapped,
        "unmapped_events": int((events["analysis_category"] == "未分類").sum()),
        "reached_25_rows": int((nonempty_counts.values >= len(action_cols)).sum()),
        "missing_age": int((persons["age_group"] == "").sum()),
        "missing_result": int((persons["purchase_status"] == "").sum()),
        "missing_duration": int(persons["duration_days"].isna().sum()),
        "missing_action_count": int(persons["recorded_action_count"].isna().sum()),
        "non_monotonic_dn_rows": nonmono,
        "unknown_age_values": sorted(set(persons["age_group"]) - set(config.AGE_LABELS.values())),
        "unknown_result_values": sorted(set(persons["purchase_status"]) - {config.BUYER_LABEL, config.NONBUYER_LABEL}),
        "first_dn_equals_duration_rows": int(
            (events[events.step_index == 1].set_index("person_id")["days_before_reference"].reindex(range(n)).values
             == persons["duration_days"].values).sum()
        ),
    }
    return NormalisedData(persons, events, quality, {"path": str(path), "encoding": encoding})


def file_fingerprint(path: Path) -> str:
    st = path.stat()
    h = hashlib.sha1(f"{path.resolve()}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest()
    return h[:12]


def load_or_build(path: Path, dictionary: "Dictionary", processed_dir: Path | None = None, force: bool = False) -> NormalisedData:  # noqa: F821
    processed_dir = processed_dir or config.PROCESSED_DIR
    processed_dir.mkdir(parents=True, exist_ok=True)
    fp = file_fingerprint(path) + "_" + dictionary.fingerprint
    p_persons = processed_dir / f"persons_{fp}.parquet"
    p_events = processed_dir / f"events_{fp}.parquet"
    p_quality = processed_dir / f"quality_{fp}.json"
    if not force and p_persons.exists() and p_events.exists() and p_quality.exists():
        persons = pd.read_parquet(p_persons)
        events = pd.read_parquet(p_events)
        quality = json.loads(p_quality.read_text(encoding="utf-8"))
        return NormalisedData(persons, events, quality, {"path": str(path), "encoding": quality.get("encoding"), "cache": fp})
    data = normalise_csv(path, dictionary)
    data.persons.to_parquet(p_persons, index=False)
    data.events.to_parquet(p_events, index=False)
    p_quality.write_text(json.dumps(data.quality, ensure_ascii=False, indent=1), encoding="utf-8")
    data.source["cache"] = fp
    return data
