from app.engine.compare import CompareRequest, compare
from app.engine.entry import EntryRequest, entry_analysis
from app.engine.graph import EdgeRef, GraphRequest, NodeRef, OUTCOME_BUY, OUTCOME_MORE, OUTCOME_NONBUY, build_graph
from app.engine.paths import complete_path_persons, enumerate_paths
from app.engine.search import PathDetailRequest, SearchRequest, path_detail, search
from app.engine.timeline import TimelineRequest, timeline
from app.engine.overview import overview
from app.filters import Filters


def node(g, step, label):
    return next((n for n in g["nodes"] if n["step"] == step and n["label"] == label), None)


def edge(g, step, a, b):
    return next((e for e in g["edges"] if e["step"] == step and e["source_label"] == a and e["target_label"] == b), None)


def test_step_node_counts_and_rates(synth_ds):
    # test 3
    g = build_graph(synth_ds, GraphRequest(filters=Filters(granularity="category"), steps=3, top_n=10))
    assert g["n"] == 6
    n = node(g, 1, "悩み・成分・カテゴリ検索")
    assert n["count"] == 4 and abs(n["rate"] - 4 / 6) < 1e-9
    assert node(g, 1, "大手EC_その他")["count"] == 2
    # share of step uses reached count at that step
    assert abs(n["share_of_step"] - 4 / 6) < 1e-9


def test_edge_transition_counts_and_rates(synth_ds):
    # test 4
    g = build_graph(synth_ds, GraphRequest(filters=Filters(granularity="category"), steps=3, top_n=10))
    e = edge(g, 1, "大手EC_その他", "資生堂_公式EC")
    assert e["count"] == 2 and e["denominator"] == 2 and e["rate"] == 1.0
    e2 = edge(g, 1, "悩み・成分・カテゴリ検索", "資生堂_公式EC")
    assert e2["count"] == 1 and e2["denominator"] == 4 and abs(e2["rate"] - 1 / 4) < 1e-9


def test_complete_path_counts(synth_ds):
    # test 5: complete 3-step path persons counted directly, not as product of rates
    view = synth_ds.view(Filters(granularity="category"))
    p = ("大手EC_その他", "資生堂_公式EC", "UTM指名検索")
    assert complete_path_persons(view, p, "consecutive") == {0, 3}
    persons, occ, _ = enumerate_paths(view, 3, "consecutive")
    assert len(persons[p]) == 2
    # ordered (subsequence) match
    q = ("悩み・成分・カテゴリ検索", "資生堂_公式EC", "UTM指名検索")
    assert complete_path_persons(view, q, "consecutive") == set()
    assert complete_path_persons(view, q, "ordered") == {4}


def test_no_double_counting_of_same_person(synth_ds):
    # test 6: person 4 visits Amazon twice consecutively -> counted once in experience and once per path
    view = synth_ds.view(Filters(granularity="category"))
    persons, occ, _ = enumerate_paths(view, 2, "consecutive")
    key = ("大手EC_Amazon", "大手EC_Amazon")
    assert len(persons[key]) == 1 and occ[key] == 1
    ov = overview(synth_ds, Filters(granularity="category"))
    row = next(r for r in ov["category_table"] if r["label"] == "資生堂_公式EC")
    assert row["count"] == 4 and row["events"] == 6


def test_filter_denominators(synth_ds):
    # test 7
    assert synth_ds.view(Filters(age="18-29")).n == 3
    assert synth_ds.view(Filters(age="18-29", result="buyer")).n == 2
    assert synth_ds.view(Filters(duration_preset="22-30")).n == 3
    assert synth_ds.view(Filters(duration_preset="custom", duration_min=10, duration_max=16)).n == 2
    # timing window keeps only in-window events (period-restricted adjacency)
    v = synth_ds.view(Filters(timing_preset="7-0", granularity="category"))
    assert v.n == 6 and [x[0] for x in v.sequences[4]] == ["UTM指名検索", "資生堂_公式EC"]
    assert any("期間内抽出後" in n for n in v.note)


def test_nonbuyers_never_get_purchase_outcome(synth_ds):
    # test 8
    g = build_graph(synth_ds, GraphRequest(filters=Filters(granularity="category", result="nonbuyer"), steps=5, top_n=10))
    assert node(g, 6, OUTCOME_BUY) is None
    assert node(g, 6, OUTCOME_NONBUY)["count"] == 3
    gb = build_graph(synth_ds, GraphRequest(filters=Filters(granularity="category", result="buyer"), steps=5, top_n=10))
    assert node(gb, 6, OUTCOME_BUY)["count"] == 2  # persons 0,1 end within 5 steps
    assert node(gb, 6, OUTCOME_MORE)["count"] == 1  # person 4 has 6 actions -> censored


def test_head_vs_tail_windows_differ(synth_ds):
    # test 9
    f = Filters(granularity="category", result="buyer")
    head = build_graph(synth_ds, GraphRequest(filters=f, steps=2, top_n=10))
    tail = build_graph(synth_ds, GraphRequest(filters=f, steps=2, mode="tail", top_n=10))
    assert node(head, 1, "大手EC_その他")["count"] == 1
    assert node(tail, 2, "資生堂_公式EC")["count"] == 2 and node(tail, 2, "UTM指名検索")["count"] == 1
    assert head["censoring"]["more_actions"] == 3 and tail["censoring"]["more_actions"] == 0


def test_selection_recomputes_complete_path(synth_ds):
    f = Filters(granularity="category")
    g = build_graph(synth_ds, GraphRequest(filters=f, steps=3, top_n=10, selected_nodes=[NodeRef(step=1, label="大手EC_その他"), NodeRef(step=3, label="UTM指名検索")]))
    assert g["selection"]["count"] == 2 and abs(g["selection"]["rate_of_filtered"] - 2 / 6) < 1e-9
    g2 = build_graph(synth_ds, GraphRequest(filters=f, steps=3, top_n=10, selected_edges=[EdgeRef(step=1, source="悩み・成分・カテゴリ検索", target="大手EC_Amazon")]))
    assert g2["selection"]["count"] == 2


def test_entry_analysis_denominators(synth_ds):
    r = entry_analysis(synth_ds, EntryRequest(filters=Filters(granularity="variable"), anchor="検索_効能/肌悩み系_乾燥", steps=3))
    assert r["anchor_count"] == 4 and r["n"] == 6
    lvl2 = {tuple(x["path"]): x for x in r["levels"][0]["rows"]}
    assert lvl2[("検索_効能/肌悩み系_乾燥", "外部サイト_大衆向けEC_Amazon")]["count"] == 2
    assert lvl2[("検索_効能/肌悩み系_乾燥", "後続記録なし")]["count"] == 1
    lvl3 = {tuple(x["path"]): x for x in r["levels"][1]["rows"]}
    k = ("検索_効能/肌悩み系_乾燥", "外部サイト_大衆向けEC_Amazon", "後続記録なし")
    assert lvl3[k]["count"] == 1 and lvl3[k]["parent_count"] == 2 and lvl3[k]["rate_of_parent"] == 0.5
    # all-occurrence mode distinguishes events from persons
    r2 = entry_analysis(synth_ds, EntryRequest(filters=Filters(granularity="category"), anchor="資生堂_公式EC", steps=2, occurrence="all"))
    assert r2["anchor_events"] == 6 and r2["anchor_count"] == 4


def test_search_and_detail(synth_ds):
    r = search(synth_ds, SearchRequest(filters=Filters(granularity="category"), start="大手EC_その他", min_steps=2, max_steps=3, min_count=1))
    paths = {x["path_str"]: x for x in r["rows"]}
    assert paths["大手EC_その他 → 資生堂_公式EC"]["count"] == 2
    assert paths["大手EC_その他 → 資生堂_公式EC"]["buyer_count"] == 1 and paths["大手EC_その他 → 資生堂_公式EC"]["nonbuyer_count"] == 1
    d = path_detail(synth_ds, PathDetailRequest(filters=Filters(granularity="category"), path=["大手EC_その他", "資生堂_公式EC"], examples=5))
    assert d["count"] == 2 and len(d["examples"]) == 2 and d["examples"][0]["person"].startswith("匿名")


def test_compare_and_timeline(synth_ds):
    c = compare(synth_ds, CompareRequest(a=Filters(result="buyer", granularity="category"), b=Filters(result="nonbuyer", granularity="category"), steps=3))
    row = next(r for r in c["experience_rows"] if r["label"] == "UTM指名検索")
    assert row["count_a"] == 2 and row["count_b"] == 1
    zero = next((r for r in c["experience_rows"] if r["rate_b"] == 0), None)
    if zero:
        assert zero["ratio"] is None  # 算出不可
    t = timeline(synth_ds, TimelineRequest(filters=Filters(granularity="category")))
    day = next(x for x in t["daily"] if x["day"] == 0)
    assert day["count"] == 2


def test_show_repeat_and_groups(synth_ds):
    from app.filters import Filters, GroupRule
    f = Filters(granularity="category", show_repeat=True)
    v = synth_ds.view(f)
    assert [x[0] for x in v.sequences[4]] == ["悩み・成分・カテゴリ検索 1回目", "大手EC_Amazon 1回目", "大手EC_Amazon 2回目", "資生堂_公式EC 1回目", "UTM指名検索 1回目", "資生堂_公式EC 2回目"]
    # occurrence numbers are assigned before the timing window
    f2 = Filters(granularity="category", show_repeat=True, timing_preset="7-0")
    assert [x[0] for x in synth_ds.view(f2).sequences[4]] == ["UTM指名検索 1回目", "資生堂_公式EC 2回目"]
    # grouping by member selection (variable + category names) and collapse of consecutive group items
    g = GroupRule(name="EC行動", members=["外部サイト_大衆向けEC_Amazon", "資生堂_公式EC"])
    f3 = Filters(granularity="category", groups=[g], collapse_groups=True)
    assert [x[0] for x in synth_ds.view(f3).sequences[4]] == ["悩み・成分・カテゴリ検索", "EC行動", "UTM指名検索", "EC行動"]
    # prefix pattern + D-n window
    g2 = GroupRule(name="直前検索", match_type="prefix", pattern="検索_", dn_min=0, dn_max=7)
    f4 = Filters(granularity="variable", groups=[g2])
    labs = [x[0] for x in synth_ds.view(f4).sequences[4]]
    assert labs[0] == "検索_効能/肌悩み系_乾燥" and labs[4] == "直前検索"
    counts = synth_ds.group_members_count(f4)
    assert counts["直前検索"]["events"] >= 1
    assert "直前検索" in synth_ds.observed_labels(f4)
    # disabled grouping leaves labels untouched
    f5 = f3.model_copy(update={"grouping_enabled": False})
    assert "EC行動" not in synth_ds.observed_labels(f5)


def test_exclude_labels_and_other_exclude_mode(synth_ds):
    from app.filters import Filters
    f = Filters(granularity="category", exclude_labels=["大手EC_Amazon"])
    assert [x[0] for x in synth_ds.view(f).sequences[4]] == ["悩み・成分・カテゴリ検索", "資生堂_公式EC", "UTM指名検索", "資生堂_公式EC"]
    # base-label exclusion also removes n回目 variants
    f2 = Filters(granularity="category", show_repeat=True, exclude_labels=["大手EC_Amazon"])
    assert all("大手EC_Amazon" not in x[0] for x in synth_ds.view(f2).sequences[4])
    g = build_graph(synth_ds, GraphRequest(filters=Filters(granularity="category"), steps=3, top_n=3, other_mode="exclude"))
    assert not any(n["label"] == "その他" for n in g["nodes"])
    assert any("除外モード" in n for n in g["notes"])
    assert g["n"] == 6
