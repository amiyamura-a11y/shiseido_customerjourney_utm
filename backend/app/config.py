from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = Path(os.environ.get("UTM_DATA_DIR", PROJECT_DIR / "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
UPLOAD_DIR = DATA_DIR / "uploads"

# Expected input files (actual names are discovered by pattern; see loader.discover_inputs)
CSV_PATTERNS = ["*パス分析*.csv", "*.csv"]
MAIN_XLSX_PATTERNS = ["*パス分析結果*.xlsx"]
ADDITIONAL_XLSX_PATTERNS = ["*追加集計*.xlsx"]
PROCESSING_XLSX_PATTERNS = ["*行動変数加工*.xlsx"]

AGE_LABELS = {"18-29": "18～29歳", "30-49": "30～49歳"}
RESULT_LABELS = {"buyer": "購買", "nonbuyer": "非購買"}
BUYER_LABEL = "購買"
NONBUYER_LABEL = "非購買"

# Expected check values from the specification (used only for validation reporting)
EXPECTED = {
    "total": 12430,
    "buyers": 2430,
    "nonbuyers": 10000,
    "age_18_29_buyers": 230,
    "age_18_29_nonbuyers": 5000,
    "age_30_49_buyers": 2200,
    "age_30_49_nonbuyers": 5000,
    "mean_action_count": 16.31,
    "mean_duration_days": 23.38,
}

SMALL_CELL_THRESHOLD = 5
MAX_STEPS = 25
