"""Checks against the real CSV and the existing Excel aggregates (skipped without data)."""
import pytest

from app.engine.entry import EntryRequest, WORRY_GROUP, entry_analysis
from app.engine.graph import GraphRequest, OUTCOME_BUY, build_graph
from app.engine.paths import enumerate_paths
from app.filters import Filters
from app.validation import check_additional, check_counts, check_path_priority


def test_counts(real_ds):
    ds, _ = real_ds
    s = ds.summary()
    assert s["persons"] == 12430 and s["buyers"] == 2430 and s["nonbuyers"] == 10000
    assert ds.quality["action_count_mismatch_rows"] == 0 and ds.quality["parse_error_events"] == 0
    assert ds.quality["unmapped_variables"] == []
    assert all(r["match"] for r in check_counts(ds))


def test_no_purchase_outcome_for_nonbuyers_real(real_ds):
    ds, _ = real_ds
    g = build_graph(ds, GraphRequest(filters=Filters(result="nonbuyer"), steps=5, include_rankings=False))
    assert not any(n["label"] == OUTCOME_BUY for n in g["nodes"])


def test_worry_entry_paths_match_excel(real_ds):
    # test 10: 18–29 buyers, worry-keyword start, 2-step paths (first occurrence, immediate next)
    ds, inputs = real_ds
    r = entry_analysis(ds, EntryRequest(filters=Filters(age="18-29", result="buyer", granularity="variable"), anchor=WORRY_GROUP, steps=3))
    assert r["anchor_count"] == 81
    lvl2 = {tuple(x["path"])[1]: x for x in r["levels"][0]["rows"]}
    assert lvl2["外部サイト_直営EC_資生堂オンライン"]["count"] == 12
    assert lvl2["検索_効能/肌悩み系_エイジング"]["count"] == 11
    assert lvl2["後続記録なし"]["count"] == 6
    rows = [x for x in check_additional(ds, inputs["additional_xlsx"].path) if x["section"] == "追加集計：悩み検索起点2接点"]
    assert rows and all(x["match"] for x in rows)


def test_path_priority_matches_excel(real_ds):
    # test 11: existing 2-step path priority (definition identical) must match
    ds, inputs = real_ds
    rows = check_path_priority(ds, inputs["main_xlsx"].path, per_segment=3)
    assert rows and all(r["match"] for r in rows)


def test_variable_rates_match_excel(real_ds):
    ds, inputs = real_ds
    rows = [x for x in check_additional(ds, inputs["additional_xlsx"].path) if x["section"] == "追加集計：個別変数出現率"]
    assert rows and all(x["match"] for x in rows)


def test_other_node_selection_real(real_ds):
    from app.engine.graph import NodeRef, OTHER
    ds, _ = real_ds
    g = build_graph(ds, GraphRequest(filters=Filters(age="18-29", result="buyer"), steps=5, top_n=3, include_rankings=False))
    other = next(n for n in g["nodes"] if n["step"] == 1 and n["label"] == OTHER)
    g2 = build_graph(ds, GraphRequest(filters=Filters(age="18-29", result="buyer"), steps=5, top_n=3, include_rankings=False, selected_nodes=[NodeRef(step=1, label=OTHER)]))
    assert g2["selection"]["count"] == other["count"]
