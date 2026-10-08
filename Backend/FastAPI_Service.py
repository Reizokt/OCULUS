import datetime as dt
import logging
import math
import os
from typing import Optional
import numpy as np
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from app.Service import service
from app.Analysis.Rankings_Based_on.Broker_Analysis import cohort_summary
from app.Cache.Cache import make_key, resolve

log = logging.getLogger("api")

TTL = {  # seconds
    "ihsg": 900, "fundamentals": 86400, "technical": 900, "narrative": 3600,
    "sectors": 900, "sector_triggers": 900, "brokers": 3600, "foreign_flow": 3600,
    "price": 900, "rag_context": 900, "rag_summary": 3600,
    "companies": 900,"ihsg_chart": 900
}

app = FastAPI(title="Market Intelligence API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET"], allow_headers=["*"],
)


# ---------- make pandas/numpy output JSON-safe BEFORE it is cached ----------
def jsonable(o):
    if o is pd.NaT:
        return None
    if isinstance(o, pd.DataFrame):
        default_idx = o.index.name is None and pd.api.types.is_integer_dtype(o.index)
        o = o.reset_index(drop=True) if default_idx else o.reset_index()
        return jsonable(o.to_dict("records"))
    if isinstance(o, pd.Series):
        return jsonable(o.to_dict())
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return f if math.isfinite(f) else None      # NaN/inf are invalid JSON for the browser
    if isinstance(o, (pd.Timestamp, dt.datetime, dt.date)):
        return o.isoformat()
    return o


import threading

_LOCKS, _GUARD = {}, threading.Lock()
_NARRATIVE_ONE_AT_A_TIME = threading.Semaphore(1)

def _lock_for(key):
    with _GUARD:
        return _LOCKS.setdefault(key, threading.Lock())

def _is_empty(x) -> bool:
    return x is None or (isinstance(x, (dict, list, tuple, set, str)) and len(x) == 0)

HIT_ONCE = os.getenv("HIT_ONCE", "1") == "1"      # testing stage: one upstream call per key
ONCE_TTL = 60 * 60 * 24 * 365     

def _fetch_once(ns: str, fn, params):
    """Call upstream exactly once. Failure or empty result -> None (and that gets cached)."""
    try:
        out = jsonable(fn(**params))
    except Exception:
        log.exception("%s upstream failed; caching null", ns)
        return None
    return None if _is_empty(out) else out


def serve(ns: str, fn, refresh: bool = False, **params):
    key = make_key(ns, **params)
    ttl = ONCE_TTL if HIT_ONCE else TTL[ns]
    if HIT_ONCE:
        refresh = False                            # ignore ?refresh=true while testing

    def loader():
        return _fetch_once(ns, fn, params) if HIT_ONCE else jsonable(fn(**params))

    try:
        with _lock_for(key):
            if ns == "narrative":
                with _NARRATIVE_ONE_AT_A_TIME:
                    entry, hit = resolve(key, ttl, loader, force=refresh)
            else:
                entry, hit = resolve(key, ttl, loader, force=refresh)
    except Exception as e:
        log.exception("%s failed", ns)
        raise HTTPException(502, f"{ns} failed: {type(e).__name__}: {e}")

    return {"data": entry["data"],                 # null when nothing came back
            "meta": {"cached": hit, "fetched_at": entry["fetched_at"], "ttl": ttl}}


def _sym(symbol: str) -> str:
    s = symbol.upper().strip()
    return s if "." in s else f"{s}.JK"

def _rag_summary(symbol: str):
   return service.run_rag_summary(symbol, refresh=False)


# ---------- wrappers for functions that return tuples / need extra inputs ----------
def _broker_ranking(date: Optional[str] = None):
    d, ranked = service.run_broker_ranking(date=date)
    return {"date": d, "cohort_summary": cohort_summary(ranked), "ranking": ranked}

def _foreign_flow(date: Optional[str] = None):
    return service.run_foreign_flow(service.load_companies(), date=date)

def _fetch_once(ns: str, fn, params):
    """Call upstream once. Exceptions propagate (-> 502) so failures are never cached."""
    out = jsonable(fn(**params))
    return None if _is_empty(out) else out

# ---------- routes (one per block of your old __main__) ----------
@app.get("/api/health")
def health():
    return {"ok": True}


# ----------IHSG Market Trend----------
@app.get("/api/market/ihsg")
def ihsg(refresh: bool = False):
    return serve("ihsg", service.run_ihsg_market_trend, refresh)

#------ IHSG Market Chart
@app.get("/api/market/ihsg/chart")
def ihsg_chart(refresh: bool = False):
    return serve("ihsg_chart", service.run_ihsg_chart, refresh)


# ---------- Stock data ----------
@app.get("/api/stocks/{symbol}/price")
def stock_price(symbol: str, bars: int = Query(65, ge=1, le=500), refresh: bool = False):
    return serve("price", service.run_stock_price, refresh, symbol=_sym(symbol), bars=bars)


# ---------- Per-symbol analysis ----------
@app.get("/api/stocks/{symbol}/technical")
def technical(symbol: str,
              horizon: int = Query(5, ge=1, le=30),
              bars: int = Query(65, ge=30, le=500),
              refresh: bool = False):
    return serve("technical", service.run_technical_analysis, refresh,
                 symbol=_sym(symbol), horizon=horizon, bars=bars)

@app.get("/api/stocks/{symbol}/fundamentals")
def fundamentals(symbol: str, refresh: bool = False):
    return serve("fundamentals", service.get_fundamentals, refresh, symbol=_sym(symbol))

@app.get("/api/stocks/{symbol}/narrative")
def narrative(symbol: str, sector: Optional[str] = None, refresh: bool = False):
    return serve("narrative", service.run_narrative_analysis, refresh,
                 symbol=_sym(symbol), sector=sector)


# ---------- Sectors ----------
@app.get("/api/sectors")
def sectors(n: int = Query(10, ge=1, le=50), refresh: bool = False):
    return serve("sectors", service.run_sector_analysis, refresh, n=n)

@app.get("/api/sectors/triggers")
def sector_triggers(n: int = Query(10, ge=1, le=50), refresh: bool = False):
    return serve("sector_triggers", service.run_sector_triggers_analysis, refresh, n=n)


# ---------- Brokers ----------
@app.get("/api/brokers")
def brokers(date: Optional[str] = None, refresh: bool = False):
    return serve("brokers", _broker_ranking, refresh, date=date)

@app.get("/api/brokers/foreign-flow")
def foreign_flow(date: Optional[str] = None, refresh: bool = False):
    return serve("foreign_flow", _foreign_flow, refresh, date=date)


# ---------- RAG / LLM ----------
@app.get("/api/rag/{symbol}/context")      # retrieve only, no Gemini call
def rag_context(symbol: str, refresh: bool = False):
    return serve("rag_context", service.run_rag_context, refresh, symbol=_sym(symbol))

@app.get("/api/rag/{symbol}/summary")      # ingest + Gemini summary (slow, uses credits)
def rag_summary(symbol: str, refresh: bool = False):
    return serve("rag_summary", _rag_summary, refresh, symbol=_sym(symbol))

#----- Company List -----
@app.get("/api/companies")
def companies(refresh: bool = False):
    return serve("companies", service.run_company_list, refresh)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))