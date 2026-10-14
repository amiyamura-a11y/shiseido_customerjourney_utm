"""Application state: discovered inputs, dictionary, dataset, validation cache."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from . import config
from .dictionary import Dictionary, compare_with_processing_definitions, load_master
from .engine.base import Dataset
from .loader import InputFile, discover_inputs, load_or_build


class AppState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.inputs: dict[str, InputFile] = {}
        self.dictionary: Dictionary | None = None
        self.dataset: Dataset | None = None
        self.loaded_at: str | None = None
        self.error: str | None = None
        self.validation: dict[str, Any] | None = None
        self.csv_override: Path | None = None

    def load(self, force: bool = False) -> None:
        with self.lock:
            try:
                self.inputs = discover_inputs(csv_override=self.csv_override)
                main_x = self.inputs["main_xlsx"]
                d = load_master(main_x.path if main_x.exists else None)
                proc = self.inputs["processing_xlsx"]
                compare_with_processing_definitions(d, proc.path if proc.exists else None)
                csv = self.inputs["csv"]
                if not csv.exists:
                    raise FileNotFoundError("個票CSVが data/raw に見つかりません")
                data = load_or_build(csv.path, d, force=force)
                added = d.extend_with_observed(sorted(set(data.events["individual_variable"])))
                if added:
                    data.quality["unmapped_variables"] = added
                self.dictionary = d
                self.dataset = Dataset(data.persons, data.events, d, data.quality, data.source)
                self.loaded_at = time.strftime("%Y-%m-%d %H:%M:%S")
                self.validation = None
                self.error = None
            except Exception as e:  # keep the API alive and surface the error
                self.error = f"{type(e).__name__}: {e}"
                self.dataset = None

    def require(self) -> Dataset:
        if self.dataset is None:
            raise RuntimeError(self.error or "データ未読み込み")
        return self.dataset

    def meta(self) -> dict[str, Any]:
        return {
            "app": "ULTIMUNE | Journey Analytics",
            "loaded_at": self.loaded_at,
            "error": self.error,
            "inputs": {k: v.as_dict() for k, v in self.inputs.items()},
            "summary": self.dataset.summary() if self.dataset else None,
            "quality": self.dataset.quality if self.dataset else None,
            "data_dir": str(config.DATA_DIR),
        }


state = AppState()
