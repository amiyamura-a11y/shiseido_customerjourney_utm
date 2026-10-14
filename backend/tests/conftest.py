import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.dictionary import Dictionary, broad_of  # noqa: E402
from app.engine.base import Dataset  # noqa: E402
from app.loader import normalise_csv  # noqa: E402

SYNTH_ROWS = [
    # age, result, type, start, days, count, actions...
    ("18～29歳", "購買", "T", "22～30日前", 24, 4, ["D−24｜外部サイト_大衆向けEC_Yahoo！ショッピング_1回目", "D−20｜外部サイト_直営EC_資生堂オンライン_1回目", "D−19｜検索_ブランド名_アルティミューン_1回目", "D−1｜検索_ブランド名_アルティミューン_2回目"]),
    ("18～29歳", "購買", "T", "0～7日前", 3, 3, ["D−3｜検索_効能/肌悩み系_乾燥_1回目", "D−2｜外部サイト_直営EC_資生堂オンライン_1回目", "D−0｜外部サイト_直営EC_資生堂オンライン_2回目"]),
    ("18～29歳", "非購買", "T", "8～14日前", 10, 2, ["D−10｜検索_効能/肌悩み系_乾燥_1回目", "D−9｜外部サイト_大衆向けEC_Amazon_1回目"]),
    ("30～49歳", "非購買", "T", "15～21日前", 16, 3, ["D−16｜外部サイト_大衆向けEC_Yahoo！ショッピング_1回目", "D−8｜外部サイト_直営EC_資生堂オンライン_1回目", "D−8｜検索_ブランド名_アルティミューン_1回目"]),
    ("30～49歳", "購買", "T", "22～30日前", 30, 6, ["D−30｜検索_効能/肌悩み系_乾燥_1回目", "D−25｜外部サイト_大衆向けEC_Amazon_1回目", "D−20｜外部サイト_大衆向けEC_Amazon_2回目", "D−10｜外部サイト_直営EC_資生堂オンライン_1回目", "D−5｜検索_ブランド名_アルティミューン_1回目", "D−0｜外部サイト_直営EC_資生堂オンライン_2回目"]),
    ("30～49歳", "非購買", "T", "22～30日前", 22, 1, ["D−22｜検索_効能/肌悩み系_乾燥_1回目"]),
]
MASTER = {
    "外部サイト_大衆向けEC_Yahoo！ショッピング": "大手EC_その他",
    "外部サイト_大衆向けEC_Amazon": "大手EC_Amazon",
    "外部サイト_直営EC_資生堂オンライン": "資生堂_公式EC",
    "検索_ブランド名_アルティミューン": "UTM指名検索",
    "検索_効能/肌悩み系_乾燥": "悩み・成分・カテゴリ検索",
}


@pytest.fixture(scope="session")
def synth_csv(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("data") / "synthetic.csv"
    cols = ["年代", "結果", "タイプ分類", "開始期", "日数", "行動数"] + [f"行動{i:02d}" for i in range(1, 26)]
    rows = []
    for age, res, typ, st, days, cnt, acts in SYNTH_ROWS:
        rows.append([age, res, typ, st, days, cnt] + acts + [""] * (25 - len(acts)))
    pd.DataFrame(rows, columns=cols).to_csv(p, index=False, encoding="utf-8-sig")
    return p


@pytest.fixture(scope="session")
def dictionary() -> Dictionary:
    d = Dictionary()
    for v, c in MASTER.items():
        d.variable_to_category[v] = c
        d.variable_to_broad[v] = broad_of(v)
    return d


@pytest.fixture(scope="session")
def synth_ds(synth_csv, dictionary) -> Dataset:
    data = normalise_csv(synth_csv, dictionary)
    return Dataset(data.persons, data.events, dictionary, data.quality)


@pytest.fixture(scope="session")
def real_ds():
    """Real dataset (skipped when data/raw is absent)."""
    from app.loader import discover_inputs, load_or_build
    from app.dictionary import load_master
    inputs = discover_inputs()
    if not inputs["csv"].exists or not inputs["main_xlsx"].exists:
        pytest.skip("real data not available")
    d = load_master(inputs["main_xlsx"].path)
    data = load_or_build(inputs["csv"].path, d)
    return Dataset(data.persons, data.events, d, data.quality), inputs
