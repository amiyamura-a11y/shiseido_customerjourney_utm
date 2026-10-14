"""FastAPI application for ULTIMUNE | Journey Analytics."""
from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

import os
import secrets

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from .engine.compare import CompareRequest, compare
from .engine.entry import EntryRequest, anchor_options, entry_analysis
from .engine.graph import GraphRequest, build_graph
from .engine.overview import overview
from .engine.search import PathDetailRequest, SearchRequest, path_detail, search
from .engine.timeline import TimelineRequest, timeline
from .filters import Filters
from .state import state
from .validation import run_validation


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.load()
    yield


app = FastAPI(title="ULTIMUNE | Journey Analytics API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- optional HTTP Basic auth for hosted deployments (set APP_USER / APP_PASSWORD) ---------
_AUTH_USER = os.environ.get("APP_USER", "")
_AUTH_PASSWORD = os.environ.get("APP_PASSWORD", "")


@app.middleware("http")
async def basic_auth_middleware(request: Request, call_next):
    if _AUTH_PASSWORD and not request.url.path.startswith("/api/health"):
        header = request.headers.get("authorization", "")
        ok = False
        if header.lower().startswith("basic "):
            import base64

            try:
                raw = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
                user, _, pw = raw.partition(":")
                ok = secrets.compare_digest(user, _AUTH_USER) and secrets.compare_digest(pw, _AUTH_PASSWORD)
            except Exception:
                ok = False
        if not ok:
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="ULTIMUNE Journey Analytics"'}, content="認証が必要です")
    return await call_next(request)


def _ds():
    try:
        return state.require()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


def _cached(key_parts, fn):
    ds = _ds()
    key = ("api",) + tuple(json.dumps(k, sort_keys=True, default=str) if not isinstance(k, str) else k for k in key_parts)
    hit = ds.cache.get(key)
    if hit is not None:
        return hit
    t = time.time()
    res = fn(ds)
    if isinstance(res, dict):
        res["_timing_ms"] = round((time.time() - t) * 1000)
    ds.cache.set(key, res)
    return res


class FiltersBody(BaseModel):
    filters: Filters = Field(default_factory=Filters)


@app.get("/api/health")
def health():
    return {"ok": state.dataset is not None, "error": state.error, "loaded_at": state.loaded_at}


@app.get("/api/meta")
def meta():
    return state.meta()


@app.post("/api/overview")
def api_overview(body: FiltersBody):
    return _cached(("overview", body.model_dump()), lambda ds: overview(ds, body.filters))


@app.get("/api/overview")
def api_overview_get():
    return _cached(("overview", {}), lambda ds: overview(ds, Filters()))


@app.post("/api/paths/graph")
def api_graph(req: GraphRequest):
    if req.mode == "anchor" and not req.anchor:
        raise HTTPException(400, "anchor モードでは anchor を指定してください")
    return _cached(("graph", req.model_dump()), lambda ds: build_graph(ds, req))


@app.post("/api/paths/compare")
def api_compare(req: CompareRequest):
    return _cached(("compare", req.model_dump()), lambda ds: compare(ds, req))


@app.post("/api/paths/entry")
def api_entry(req: EntryRequest):
    return _cached(("entry", req.model_dump()), lambda ds: entry_analysis(ds, req))


@app.get("/api/paths/entry/options")
def api_entry_options(granularity: str = Query("variable")):
    ds = _ds()
    return {"granularity": granularity, "options": anchor_options(ds, granularity)}


@app.post("/api/paths/search")
def api_search(req: SearchRequest):
    return _cached(("search", req.model_dump()), lambda ds: search(ds, req))


@app.post("/api/paths/detail")
def api_detail(req: PathDetailRequest):
    return _cached(("detail", req.model_dump()), lambda ds: path_detail(ds, req))


@app.post("/api/timeline")
def api_timeline(req: TimelineRequest):
    return _cached(("timeline", req.model_dump()), lambda ds: timeline(ds, req))


@app.get("/api/labels")
def api_labels(granularity: str = Query("category")):
    ds = _ds()
    return {"granularity": granularity, "labels": ds.labels_for(granularity)}


@app.get("/api/dictionary")
def api_dictionary():
    ds = _ds()
    d = ds.dictionary
    counts = ds.events.groupby("individual_variable").agg(events=("person_id", "size"), persons=("person_id", "nunique")).to_dict("index")
    table = []
    for row in d.table():
        c = counts.get(row["individual_variable"], {"events": 0, "persons": 0})
        table.append({**row, "events": int(c["events"]), "persons": int(c["persons"]), "in_csv": row["individual_variable"] in counts})
    return {
        "source": d.source,
        "table": table,
        "categories": d.categories,
        "broad_categories": sorted(set(d.variable_to_broad.values())),
        "mismatches": d.mismatches,
        "processing_summary": d.processing_summary,
        "quality": ds.quality,
        "inputs": {k: v.as_dict() for k, v in state.inputs.items()},
        "loaded_at": state.loaded_at,
    }


@app.get("/api/validation")
def api_validation():
    ds = _ds()
    if state.validation is None:
        state.validation = run_validation(ds, state.inputs)
    return state.validation


@app.post("/api/reload")
def api_reload(force: bool = Query(True)):
    state.load(force=force)
    if state.error:
        raise HTTPException(500, state.error)
    return state.meta()


@app.post("/api/cache/clear")
def api_cache_clear():
    ds = _ds()
    ds.cache.clear()
    state.validation = None
    return {"ok": True}


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    name = Path(file.filename or "upload").name
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dest = config.UPLOAD_DIR / f"{stamp}_{name}"
    content = await file.read()
    dest.write_bytes(content)
    lower = name.lower()
    if lower.endswith(".csv"):
        state.csv_override = dest
        state.load(force=True)
        if state.error:
            state.csv_override = None
            state.load(force=False)
            raise HTTPException(400, f"CSVの読み込みに失敗しました: {state.error}")
        persisted = None
        if not any(p.suffix.lower() == ".csv" for p in config.RAW_DIR.glob("*") if p.is_file()):
            # no CSV under data/raw yet: keep a copy there so the data survives a restart (never overwrites)
            target = config.RAW_DIR / name
            if not target.exists():
                target.write_bytes(content)
                persisted = str(target)
                state.csv_override = None
                state.load(force=False)
        return {"ok": True, "saved_to": persisted or str(dest), "role": "csv", "persisted": persisted is not None,
                "message": None if persisted else "data/raw に既存CSVがあるため、このセッションのみ差し替えました（再起動後は data/raw のCSVに戻ります）", "meta": state.meta()}
    if lower.endswith(".xlsx"):
        # Excel files are copied next to the raw inputs only if the role is recognisable; raw files are never overwritten
        role = "main_xlsx" if "パス分析結果" in name else "additional_xlsx" if "追加集計" in name else "processing_xlsx" if "行動変数加工" in name else None
        if role is None:
            return {"ok": False, "saved_to": str(dest), "role": None, "message": "役割を判定できないExcelです（ファイル名に『パス分析結果』『追加集計』『行動変数加工』を含めてください）"}
        target = config.RAW_DIR / name
        if target.exists():
            return {"ok": False, "saved_to": str(dest), "role": role, "message": f"同名ファイルが data/raw に存在するため上書きしません: {target.name}"}
        target.write_bytes(content)
        state.load(force=True)
        return {"ok": True, "saved_to": str(target), "role": role, "meta": state.meta()}
    raise HTTPException(400, "CSV または XLSX をアップロードしてください")


# --- static frontend (built with `npm run build:static` -> frontend/out) ---------------------
_STATIC_DIR = Path(os.environ.get("STATIC_DIR", str(config.PROJECT_DIR / "frontend" / "out")))
if _STATIC_DIR.exists():

    @app.get("/", include_in_schema=False)
    def _root():
        return RedirectResponse("/golden-path/")

    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
