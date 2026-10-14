"""Common filter model shared by all analysis endpoints."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Age = Literal["all", "18-29", "30-49"]
Result = Literal["all", "buyer", "nonbuyer"]
DurationPreset = Literal["all", "0-7", "8-14", "15-21", "22-30", "custom"]
TimingPreset = Literal["all", "30-15", "14-8", "7-0", "custom"]
Granularity = Literal["variable", "category", "broad"]
Dedupe = Literal["keep_all", "collapse_consecutive", "first_only"]
PathMode = Literal["consecutive", "ordered"]

DURATION_PRESETS: dict[str, tuple[int | None, int | None]] = {
    "all": (None, None),
    "0-7": (0, 7),
    "8-14": (8, 14),
    "15-21": (15, 21),
    "22-30": (22, 30),
}
TIMING_PRESETS: dict[str, tuple[int | None, int | None]] = {
    "all": (None, None),
    "30-15": (15, 30),
    "14-8": (8, 14),
    "7-0": (0, 7),
}


MatchType = Literal["select", "prefix", "contains", "regex"]


class GroupRule(BaseModel):
    """A user-defined group that merges arbitrary variables/categories under one label.

    * members: exact names (individual variables, analysis categories or broad categories)
    * pattern: optional name pattern applied to the individual variable name
    * dn_min/dn_max: optional D−n window (only actions in this window join the group)
    """

    name: str = Field(min_length=1, max_length=60)
    enabled: bool = True
    members: list[str] = Field(default_factory=list)
    match_type: MatchType = "select"
    pattern: str = ""
    dn_min: int | None = Field(default=None, ge=0, le=365)
    dn_max: int | None = Field(default=None, ge=0, le=365)


class Filters(BaseModel):
    age: Age = "all"
    result: Result = "all"
    duration_preset: DurationPreset = "all"
    duration_min: int | None = Field(default=None, ge=0, le=365)
    duration_max: int | None = Field(default=None, ge=0, le=365)
    timing_preset: TimingPreset = "all"
    timing_min: int | None = Field(default=None, ge=0, le=365, description="D−n の下限（基準日に近い側）")
    timing_max: int | None = Field(default=None, ge=0, le=365, description="D−n の上限（基準日から遠い側）")
    granularity: Granularity = "category"
    dedupe: Dedupe = "keep_all"
    path_mode: PathMode = "consecutive"
    groups: list[GroupRule] = Field(default_factory=list)
    grouping_enabled: bool = True
    collapse_groups: bool = Field(default=False, description="連続する同一グループを1つに集約")
    show_repeat: bool = Field(default=False, description="表示名に n回目 を付ける")
    exclude_labels: list[str] = Field(default_factory=list, description="パスから除外する行動（統合後ラベル。n回目付き／なしのどちらでも指定可）")

    def active_groups(self) -> list["GroupRule"]:
        return [g for g in self.groups if g.enabled and g.name.strip()] if self.grouping_enabled else []

    def duration_range(self) -> tuple[int | None, int | None]:
        if self.duration_preset == "custom":
            return self.duration_min, self.duration_max
        return DURATION_PRESETS[self.duration_preset]

    def timing_range(self) -> tuple[int | None, int | None]:
        if self.timing_preset == "custom":
            return self.timing_min, self.timing_max
        return TIMING_PRESETS[self.timing_preset]

    def person_key(self) -> tuple:
        return (self.age, self.result, self.duration_range())

    def sequence_key(self) -> tuple:
        groups = tuple((g.name, tuple(sorted(g.members)), g.match_type, g.pattern, g.dn_min, g.dn_max) for g in self.active_groups())
        return (self.timing_range(), self.granularity, self.dedupe, groups, self.collapse_groups, self.show_repeat, tuple(sorted(self.exclude_labels)))

    def describe(self) -> dict:
        d_lo, d_hi = self.duration_range()
        t_lo, t_hi = self.timing_range()
        return {
            "age": self.age,
            "result": self.result,
            "duration_days": "全期間" if d_lo is None and d_hi is None else f"{d_lo if d_lo is not None else 0}〜{d_hi if d_hi is not None else '∞'}日",
            "timing": "全期間" if t_lo is None and t_hi is None else f"D−{t_hi if t_hi is not None else '∞'}〜D−{t_lo if t_lo is not None else 0}",
            "timing_applied": not (t_lo is None and t_hi is None),
            "granularity": self.granularity,
            "dedupe": self.dedupe,
            "path_mode": self.path_mode,
            "groups": [g.name for g in self.active_groups()],
            "collapse_groups": self.collapse_groups,
            "show_repeat": self.show_repeat,
            "exclude_labels": list(self.exclude_labels),
        }
