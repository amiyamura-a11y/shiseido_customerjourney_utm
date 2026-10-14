"""Export a self-contained single-file HTML version of ULTIMUNE | Journey Analytics.

The file embeds the normalised individual records (compact arrays) and recomputes
every figure in the browser, so it can be hosted as a static page (e.g. GitHub Pages)
without the Python backend.

Usage:  python scripts/export_static_html.py [--out ../site/index.html]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app import config  # noqa: E402
from app.dictionary import compare_with_processing_definitions, load_master  # noqa: E402
from app.engine.base import Dataset  # noqa: E402
from app.loader import discover_inputs, load_or_build  # noqa: E402
from app.validation import run_validation  # noqa: E402


def build_payload(include_validation: bool = True) -> dict:
    inputs = discover_inputs()
    d = load_master(inputs["main_xlsx"].path if inputs["main_xlsx"].exists else None)
    compare_with_processing_definitions(d, inputs["processing_xlsx"].path if inputs["processing_xlsx"].exists else None)
    data = load_or_build(inputs["csv"].path, d)
    d.extend_with_observed(sorted(set(data.events["individual_variable"])))
    ds = Dataset(data.persons, data.events, d, data.quality, data.source)

    vars_ = ds.variables
    vidx = {v: i for i, v in enumerate(vars_)}
    cats = sorted(set(d.variable_to_category.get(v, "未分類") for v in vars_))
    cidx = {c: i for i, c in enumerate(cats)}
    broads = sorted(set(d.variable_to_broad.get(v, "その他") for v in vars_))
    bidx = {b: i for i, b in enumerate(broads)}
    types = sorted(set(ds.persons["journey_type"]))
    starts = sorted(set(ds.persons["start_period"]))
    ages = [config.AGE_LABELS["18-29"], config.AGE_LABELS["30-49"]]

    persons = []
    seq = []
    for _, r in ds.persons.iterrows():
        pid = int(r["person_id"])
        age = ages.index(r["age_group"]) if r["age_group"] in ages else 2
        persons.append([age, 1 if r["purchase_status"] == config.BUYER_LABEL else 0, int(r["duration_days"]), int(r["recorded_action_count"]), types.index(r["journey_type"]), starts.index(r["start_period"])])
        flat = []
        for v, dn, _st, rp in ds.raw_sequences[pid]:
            flat.append(vidx[v])
            flat.append(dn)
            flat.append(rp)
        seq.append(flat)

    payload = {
        "meta": {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": inputs["csv"].path.name,
            "inputs": {k: v.as_dict() for k, v in inputs.items()},
            "summary": ds.summary(),
            "quality": ds.quality,
            "expected": config.EXPECTED,
            "dictionary_source": d.source,
        },
        "ages": ages,
        "vars": vars_,
        "var_cat": [cidx[d.variable_to_category.get(v, "未分類")] for v in vars_],
        "cats": cats,
        "var_broad": [bidx[d.variable_to_broad.get(v, "その他")] for v in vars_],
        "broads": broads,
        "types": types,
        "starts": starts,
        "persons": persons,
        "seq": seq,
        "mismatches": d.mismatches,
    }
    if include_validation:
        v = run_validation(ds, inputs)
        payload["validation"] = {"summary": v["summary"], "implied_prior": v["implied_prior"], "rows": v["rows"]}
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(config.PROJECT_DIR / "site" / "index.html"))
    ap.add_argument("--no-validation", action="store_true")
    args = ap.parse_args()
    template = (HERE.parent / "app" / "static_template.html").read_text(encoding="utf-8")
    payload = build_payload(include_validation=not args.no_validation)
    js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    js = js.replace("</", "<\\/")
    html = template.replace("/*__DATA__*/null", js)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"written {out} ({out.stat().st_size / 1024 / 1024:.2f} MB; persons={len(payload['persons'])}, events={payload['meta']['summary']['events']})")


if __name__ == "__main__":
    main()
