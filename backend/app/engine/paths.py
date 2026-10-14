"""Path enumeration and complete-path counting (unique persons, computed from
individual records; never from products of transition rates)."""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Iterable

from .base import SeqItem, View

Path = tuple[str, ...]

ORDERED_MAX_ENUMERATION = 3


def _labels(seq: list[SeqItem]) -> list[str]:
    return [it[0] for it in seq]


def is_consecutive_match(labels: list[str], path: Path) -> bool:
    k = len(path)
    if k == 0 or len(labels) < k:
        return False
    for i in range(len(labels) - k + 1):
        if tuple(labels[i:i + k]) == path:
            return True
    return False


def is_ordered_match(labels: list[str], path: Path) -> bool:
    """path appears as a (not necessarily adjacent) subsequence."""
    j = 0
    for lab in labels:
        if j < len(path) and lab == path[j]:
            j += 1
            if j == len(path):
                return True
    return len(path) == 0


def match(labels: list[str], path: Path, mode: str) -> bool:
    return is_consecutive_match(labels, path) if mode == "consecutive" else is_ordered_match(labels, path)


def complete_path_persons(view: View, path: Path, mode: str, person_ids: Iterable[int] | None = None) -> set[int]:
    pids = view.sequences.keys() if person_ids is None else person_ids
    out: set[int] = set()
    for pid in pids:
        if match(_labels(view.sequences[pid]), path, mode):
            out.add(pid)
    return out


def enumerate_paths(view: View, k: int, mode: str = "consecutive", person_ids: Iterable[int] | None = None) -> tuple[dict[Path, set[int]], dict[Path, int], str | None]:
    """Return {path: persons}, {path: event occurrences}, note.

    consecutive: all length-k sliding windows.
    ordered: all length-k combinations of distinct labels in order of first
    occurrence (k <= ORDERED_MAX_ENUMERATION; larger k is not enumerated).
    """
    persons: dict[Path, set[int]] = defaultdict(set)
    occurrences: dict[Path, int] = defaultdict(int)
    note = None
    pids = list(view.sequences.keys() if person_ids is None else person_ids)
    if mode == "consecutive":
        for pid in pids:
            labs = _labels(view.sequences[pid])
            for i in range(len(labs) - k + 1):
                p = tuple(labs[i:i + k])
                persons[p].add(pid)
                occurrences[p] += 1
    else:
        if k > ORDERED_MAX_ENUMERATION:
            return {}, {}, f"順序保持パスの全列挙は{ORDERED_MAX_ENUMERATION}ステップまでです（指定パスの人数は検索で算出できます）"
        note = "順序保持パス：同一行動は初回出現のみを用い、間に他の行動を挟んでもよい順序の組合せを列挙"
        for pid in pids:
            labs = _labels(view.sequences[pid])
            distinct: list[str] = []
            seen: set[str] = set()
            for lab in labs:
                if lab not in seen:
                    seen.add(lab)
                    distinct.append(lab)
            for comb in combinations(distinct, k):
                persons[comb].add(pid)
                occurrences[comb] += 1
    return persons, occurrences, note


def path_stats(view: View, pids: set[int], persons_df) -> dict:
    """Average duration / action count / per-step timing is computed by caller when needed."""
    return {"count": len(pids)}
