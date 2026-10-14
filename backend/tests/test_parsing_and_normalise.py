from app.parsing import parse_action


def test_parse_keeps_underscores_in_site_name():
    p = parse_action("D−24｜外部サイト_大衆向けEC_Yahoo！ショッピング_1回目")
    assert p.days_before_reference == 24
    assert p.individual_variable == "外部サイト_大衆向けEC_Yahoo！ショッピング"
    assert p.repeat_index == 1 and p.error is None


def test_parse_handles_minus_and_bar_variants():
    for s in ["D-3|検索_ブランド名_資生堂_2回目", "D－3｜検索_ブランド名_資生堂_2回目", "D–3｜検索_ブランド名_資生堂_2回目"]:
        p = parse_action(s)
        assert p.days_before_reference == 3 and p.individual_variable == "検索_ブランド名_資生堂" and p.repeat_index == 2


def test_parse_nested_underscore_variable():
    p = parse_action("D−5｜外部サイト_百貨店EC_美容カテゴリページ_高島屋オンライン_TBEAUT_3回目")
    assert p.individual_variable == "外部サイト_百貨店EC_美容カテゴリページ_高島屋オンライン_TBEAUT"
    assert p.repeat_index == 3


def test_parse_error_keeps_raw():
    p = parse_action("不明な文字列")
    assert p.error == "no_dn_prefix" and p.raw == "不明な文字列" and p.individual_variable == "不明な文字列"
    q = parse_action("D−5｜外部サイト_X")
    assert q.error == "no_repeat_suffix" and q.days_before_reference == 5


def test_order_missing_and_repeats_preserved(synth_ds):
    # test 1: order of 行動01..25, missing cells, repeat index kept
    seq = synth_ds.raw_sequences[0]
    assert [s[2] for s in seq] == [1, 2, 3, 4]
    assert [s[1] for s in seq] == [24, 20, 19, 1]
    assert seq[-1][0] == "検索_ブランド名_アルティミューン" and seq[-1][3] == 2
    assert synth_ds.quality["action_count_mismatch_rows"] == 0
    assert synth_ds.quality["gap_rows"] == 0


def test_dn_and_category_conversion(synth_ds):
    # test 2
    ev = synth_ds.events
    row = ev[(ev.person_id == 0) & (ev.step_index == 2)].iloc[0]
    assert row.days_before_reference == 20
    assert row.analysis_category == "資生堂_公式EC"
    assert row.broad_category == "外部サイト"
