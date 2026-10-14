"""Dataset container and filtered sequence views.

A *view* is the list of persons that pass the person-level filters together with
each person's ordered sequence of labels (after timing window, granularity
mapping and same-action handling). Rates are always computed against the number
of persons in the view (``n``) unless stated otherwise in the response.
"""
from __future__ import annotations

import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

import numpy as np
import pandas as pd

from .. import config
from ..dictionary import Dictionary
from ..filters import Filters

SeqItem = tuple[str, int, int]  # (label, days_before_reference, original_step_index)


class LRU:
    def __init__(self, capacity: int = 256):
        self.capacity = capacity
        self._d: OrderedDict[Any, Any] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Any) -> Any:
        with self._lock:
            if key in self._d:
                self._d.move_to_end(key)
                return self._d[key]
            return None

    def set(self, key: Any, value: Any) -> None:
        with self._lock:
            self._d[key] = value
            self._d.move_to_end(key)
            while len(self._d) > self.capacity:
                self._d.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._d.clear()


@dataclass
class View:
    filters: Filters
    person_ids: np.ndarray
    sequences: dict[int, list[SeqItem]]
    n: int
    label_of: Callable[[str], str]
    note: list[str] = field(default_factory=list)

    @property
    def labels(self) -> list[str]:
        s: set[str] = set()
        for seq in self.sequences.values():
            for it in seq:
                s.add(it[0])
        return sorted(s)


class Dataset:
    def __init__(self, persons: pd.DataFrame, events: pd.DataFrame, dictionary: Dictionary, quality: dict | None = None, source: dict | None = None):
        self.persons = persons.reset_index(drop=True)
        self.events = events
        self.dictionary = dictionary
        self.quality = quality or {}
        self.source = source or {}
        self.cache = LRU(512)
        self._build_index()

    # ---- indexing -----------------------------------------------------
    def _build_index(self) -> None:
        ev = self.events.sort_values(["person_id", "step_index"])
        self.raw_sequences: dict[int, list[tuple[str, int, int, int]]] = {}
        pids = ev["person_id"].to_numpy()
        vars_ = ev["individual_variable"].to_numpy()
        dns = ev["days_before_reference"].to_numpy()
        steps = ev["step_index"].to_numpy()
        reps = ev["repeat_index"].to_numpy()
        for pid in self.persons["person_id"].to_numpy():
            self.raw_sequences[int(pid)] = []
        for pid, v, dn, st, rp in zip(pids, vars_, dns, steps, reps):
            self.raw_sequences[int(pid)].append((str(v), int(dn) if pd.notna(dn) else -1, int(st), int(rp) if pd.notna(rp) else 0))
        self.person_index = self.persons.set_index("person_id")
        self.variables = sorted(set(map(str, vars_)))
        self.categories = sorted(set(self.events["analysis_category"].astype(str)))
        self.broads = sorted(set(self.events["broad_category"].astype(str)))

    def label_mapper(self, granularity: str) -> Callable[[str], str]:
        if granularity == "variable":
            return lambda v: v
        if granularity == "category":
            m = self.dictionary.variable_to_category
            return lambda v: m.get(v, "未分類")
        m2 = self.dictionary.variable_to_broad
        return lambda v: m2.get(v, "その他")

    def labels_for(self, granularity: str) -> list[str]:
        if granularity == "variable":
            return self.variables
        if granularity == "category":
            return self.categories
        return self.broads

    def observed_labels(self, f: Filters) -> list[str]:
        """Labels actually present in the filtered view (groups / n回目 included), sorted by frequency."""
        v = self.view(f)
        counts: dict[str, int] = {}
        for seq in v.sequences.values():
            for lab, _, _ in seq:
                counts[lab] = counts.get(lab, 0) + 1
        return [k for k, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]

    # ---- person-level filtering ----------------------------------------
    def select_persons(self, f: Filters) -> np.ndarray:
        p = self.persons
        mask = np.ones(len(p), dtype=bool)
        if f.age != "all":
            mask &= (p["age_group"] == config.AGE_LABELS[f.age]).to_numpy()
        if f.result != "all":
            mask &= (p["purchase_status"] == config.RESULT_LABELS[f.result]).to_numpy()
        lo, hi = f.duration_range()
        if lo is not None:
            mask &= (p["duration_days"] >= lo).to_numpy()
        if hi is not None:
            mask &= (p["duration_days"] <= hi).to_numpy()
        return p.loc[mask, "person_id"].to_numpy()

    # ---- grouping -------------------------------------------------------
    def group_matcher(self, f: Filters) -> Callable[[str, int], str | None]:
        """Return fn(variable, dn) -> group name or None for the active group rules."""
        rules = []
        for g in f.active_groups():
            members = set(g.members)
            rx = None
            if g.match_type == "regex" and g.pattern:
                try:
                    rx = re.compile(g.pattern)
                except re.error:
                    rx = None
            rules.append((g, members, rx))
        if not rules:
            return lambda v, dn: None
        cat = self.dictionary.variable_to_category
        broad = self.dictionary.variable_to_broad

        def match(v: str, dn: int) -> str | None:
            for g, members, rx in rules:
                if g.dn_min is not None and dn < g.dn_min:
                    continue
                if g.dn_max is not None and dn > g.dn_max:
                    continue
                hit = False
                if members and (v in members or cat.get(v) in members or broad.get(v) in members):
                    hit = True
                elif g.match_type == "prefix" and g.pattern and v.startswith(g.pattern):
                    hit = True
                elif g.match_type == "contains" and g.pattern and g.pattern in v:
                    hit = True
                elif g.match_type == "regex" and rx is not None and rx.search(v):
                    hit = True
                if hit:
                    return g.name
            return None

        return match

    def group_members_count(self, f: Filters) -> dict[str, dict[str, int]]:
        """How many variables / events / persons each active group captures (ignores timing filter)."""
        match = self.group_matcher(f)
        out: dict[str, dict[str, Any]] = {g.name: {"variables": set(), "events": 0, "persons": set()} for g in f.active_groups()}
        for pid, seq in self.raw_sequences.items():
            for v, dn, _st, _rp in seq:
                name = match(v, dn)
                if name is not None:
                    out[name]["variables"].add(v)
                    out[name]["events"] += 1
                    out[name]["persons"].add(pid)
        return {k: {"variables": len(d["variables"]), "events": d["events"], "persons": len(d["persons"])} for k, d in out.items()}

    # ---- sequence building ---------------------------------------------
    def build_sequence(self, pid: int, f: Filters, label_of: Callable[[str], str], group_of: Callable[[str, int], str | None] | None = None) -> list[SeqItem]:
        """Label every action of a person, then apply same-action handling, repeat numbering and the timing window.

        Occurrence numbers (n回目) are counted over the person's whole journey (before the
        timing window) so that "2回目" always means the second time in the journey.
        """
        lo, hi = f.timing_range()
        group_of = group_of or (lambda v, dn: None)
        group_names = {g.name for g in f.active_groups()}
        labelled: list[tuple[str, int, int]] = []
        last: str | None = None
        seen: set[str] = set()
        for v, dn, st, _rp in self.raw_sequences.get(pid, []):
            g = group_of(v, dn)
            lab = g if g is not None else label_of(v)
            if f.dedupe == "collapse_consecutive" and lab == last:
                continue
            if f.collapse_groups and lab in group_names and lab == last:
                continue
            if f.dedupe == "first_only":
                if lab in seen:
                    continue
                seen.add(lab)
            labelled.append((lab, dn, st))
            last = lab
        if f.show_repeat:
            counts: dict[str, int] = {}
            numbered: list[tuple[str, int, int]] = []
            for lab, dn, st in labelled:
                counts[lab] = counts.get(lab, 0) + 1
                numbered.append((f"{lab} {counts[lab]}回目", dn, st))
            labelled = numbered
        out: list[SeqItem] = []
        for lab, dn, st in labelled:
            if lo is not None and dn < lo:
                continue
            if hi is not None and dn > hi:
                continue
            out.append((lab, dn, st))
        return out

    def view(self, f: Filters, person_ids: Iterable[int] | None = None) -> View:
        key = ("view", f.person_key(), f.sequence_key(), None if person_ids is None else tuple(sorted(person_ids)))
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        pids = self.select_persons(f) if person_ids is None else np.array(sorted(person_ids), dtype=int)
        label_of = self.label_mapper(f.granularity)
        group_of = self.group_matcher(f)
        seqs = {int(pid): self.build_sequence(int(pid), f, label_of, group_of) for pid in pids}
        notes = []
        if f.active_groups():
            notes.append("変数統合: " + "、".join(g.name for g in f.active_groups()) + "（統合ルールに一致した行動はグループ名で表示）")
        if f.collapse_groups and f.active_groups():
            notes.append("連続する同一グループを1つに集約")
        if f.show_repeat:
            notes.append("表示名の「n回目」は本人のジャーニー全体における当該行動の出現回数（行動発生時期フィルタ適用前に採番）")
        t_lo, t_hi = f.timing_range()
        if not (t_lo is None and t_hi is None):
            notes.append("行動発生時期フィルタ適用後の隣接（期間内抽出後の隣接）。元ログでの真の連続パスとは異なります。")
        if f.dedupe != "keep_all":
            notes.append({"collapse_consecutive": "連続する同一行動を1つに統合", "first_only": "同一行動は初回のみ保持"}[f.dedupe])
        v = View(f, pids, seqs, int(len(pids)), label_of, notes)
        self.cache.set(key, v)
        return v

    # ---- helpers ---------------------------------------------------------
    def person_frame(self, pids: Iterable[int]) -> pd.DataFrame:
        return self.person_index.loc[list(pids)]

    def summary(self) -> dict[str, Any]:
        p = self.persons
        return {
            "persons": int(len(p)),
            "buyers": int((p["purchase_status"] == config.BUYER_LABEL).sum()),
            "nonbuyers": int((p["purchase_status"] == config.NONBUYER_LABEL).sum()),
            "events": int(len(self.events)),
            "variables": len(self.variables),
            "categories": len(self.categories),
        }


def rate(num: int, den: int) -> float | None:
    return None if den == 0 else num / den


def ratio(a: float | None, b: float | None) -> float | None:
    """A÷B; None (算出不可) when B is 0/None."""
    if a is None or b is None or b == 0:
        return None
    return a / b


def small_cell(*counts: int) -> bool:
    return any(c < config.SMALL_CELL_THRESHOLD for c in counts)


def mean_or_none(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None and v >= 0]
    return None if not vals else float(sum(vals) / len(vals))


def median_or_none(values: list[float]) -> float | None:
    vals = sorted(v for v in values if v is not None and v >= 0)
    if not vals:
        return None
    n = len(vals)
    mid = n // 2
    return float(vals[mid]) if n % 2 else float((vals[mid - 1] + vals[mid]) / 2)
