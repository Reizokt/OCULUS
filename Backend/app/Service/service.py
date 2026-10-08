import sys
from pathlib import Path

# Service -> app -> Backend. Must run before any `app` import.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import json
import pandas as pd
from app.RAG_Narrative_Analysis.adapters import broker_payload, build_analysis, sector_payload
from app.Analysis.Category_of_Analysis.Technical_Analysis.Main_Technical_Analysis import (
    Market_Trends_Analysis, Technical_Forecast,
)
#Fundamental analysis import
from app.Analysis.Category_of_Analysis.Fundamental_Analysis.Fundamental_Analysis_Evalution import analyze

#Narrative analysis import
from app.Analysis.Category_of_Analysis.Narrative_Analysis.Narrative_Analysis import (
    Narrative_Analysis, normalize_corporate_actions, normalize_suspensions,
    normalize_news, normalize_insider,
)
#Data API import
from app.Data.Data_API_Call import (
    IHSG_Index_Market_Summary, fetch_company_fundamentals, fetch_Stock_data,
    get_Corporate_Filings, get_news_articles, get_stock_suspensions, get_corporate_actions,QUARTER_DAYS, INSIDER_DAYS,
    fetch_all_companies,sectors_information,fetch_subsector_list,_norm,_slug,
    fetch_broker_registry, fetch_top_brokers, fetch_foreign_flow
)

#importing Sectors Function 
from app.Analysis.Category_of_Analysis.Sectors_Analysis.Sectors_Analysis import (
    score_sectors, watchlist, flatten_subsector
)

#importing Broker Analysis Function
from app.Analysis.Rankings_Based_on.Broker_Analysis import (
    rank_brokers, cohort_summary, foreign_flow_by_subsector,
)

from app.RAG_Narrative_Analysis.adapters import broker_payload, build_analysis, sector_payload
from app.RAG_Narrative_Analysis.ingest import ingest
from app.RAG_Narrative_Analysis.retrieve import retrieve
from app.RAG_Narrative_Analysis.generate import summarize, _format_context
from datetime import date
from app.RAG_Narrative_Analysis.config import CACHE_DIR, DEFAULT_LANGUAGE 

#-------- getting price stock 
def run_stock_price(symbol="BBCA.JK", bars=65):
    return prepare_ohlcv(fetch_Stock_data(symbol)).tail(bars).reset_index(drop=True)

#---- get Fundamental Data
def get_fundamentals(symbol="BBCA.JK"):
    report, quarters = fetch_company_fundamentals(symbol)
    return analyze(report, quarters)

# getting IHSG market trend
def run_IHSG_Market_trend():
    data = IHSG_Index_Market_Summary()
    df = pd.DataFrame(data).rename(columns={"price": "Close"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return Market_Trends_Analysis(df)

#getting IHSG market data
def run_ihsg_chart():
    data = IHSG_Index_Market_Summary()
    df = pd.DataFrame(data).rename(columns={"price": "Close"})
    df["date"] = pd.to_datetime(df["date"])
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Close"]).sort_values("date").reset_index(drop=True)

    series = df[["date", "Close"]].copy()          # copy before the analysis touches df
    return {"trend": Market_Trends_Analysis(df), "series": series}

#markets 
OHLCV = ["Open", "High", "Low", "Close", "Volume"]

def prepare_ohlcv(data):
    """Raw API rows -> clean DataFrame with Open/High/Low/Close/Volume."""
    rows = data if isinstance(data, list) else (data or {}).get("results")
    if not rows:
        raise ValueError(f"No price data returned: {str(data)[:300]}")
    df = pd.DataFrame(rows)

    # lowercase API columns -> capitalized; IHSG's 'price' -> 'Close'
    df = df.rename(columns={"price": "close"})
    df = df.rename(columns={c.lower(): c for c in OHLCV})

    df["date"] = pd.to_datetime(df["date"])
    df = (df.sort_values("date")
            .drop_duplicates("date", keep="last")
            .reset_index(drop=True))

    for c in OHLCV:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna(subset=["Close"]).reset_index(drop=True)


# tehcnical Analysis 
def run_technical_analysis(symbol="BBCA.JK", horizon=5, bars=65, include_series=False):
    data = fetch_Stock_data(symbol)
    df = prepare_ohlcv(data).tail(bars).reset_index(drop=True)

    if len(df) < 30:
        raise ValueError(f"{symbol}: only {len(df)} bars, need at least 30")  # was missing the f

    result = Technical_Forecast(df, horizon=horizon)

    if not include_series and result.get("volume"):
        result["volume"].pop("bull_volume_series", None)
        result["volume"].pop("bear_volume_series", None)

    result["symbol"] = symbol
    result["date_range"] = (str(df["date"].iloc[0].date()),
                            str(df["date"].iloc[-1].date()))
    return result

# Narrative Analysis 
def _results(resp):
    if resp is None:
        return []
    return resp if isinstance(resp, list) else resp.get("results", [])

def run_narrative_analysis(symbol="BBCA.JK", sector=None, df=None):
    if df is None:
        df = prepare_ohlcv(fetch_Stock_data(symbol))   # price history for spike alignment

    ca   = get_corporate_actions(symbol)
    ins  = get_Corporate_Filings(symbol)
    news = get_news_articles(symbol)
    susp = get_stock_suspensions(symbol)

    events = (normalize_corporate_actions(ca, symbol)
              + normalize_insider(_results(ins), symbol)
              + normalize_news(_results(news), symbol, sector)
              + normalize_suspensions(_results(susp), symbol))

    return Narrative_Analysis(symbol, events, lookback_days=QUARTER_DAYS,
                                 insider_days=INSIDER_DAYS,
                                 spike_dates=volume_spike_dates(df))
    
# Volume Spike date 
def volume_spike_dates(df, window=20, mult=1.5):
    if df is None or df.empty or "Volume" not in df:
        return []
    avg = df["Volume"].rolling(window).mean().shift(1)
    return df.loc[df["Volume"] > avg * mult, "date"].tolist()

# ---------- Sectors ----------
COMPANY_COLS = {"daily_close_change": "chg", "weekly_close_change": "chg_w"}  # fix left side after step 3

def _find(cols, *needles):
    """First column whose name ends with / contains one of the needles."""
    for n in needles:
        for c in cols:
            if c == n or c.endswith("." + n):
                return c
    return None

def load_companies():
    rows = fetch_all_companies()
    if not rows:
        raise ValueError("No companies returned")
    df = pd.json_normalize(rows)            # flattens nested dicts: a.b -> "a.b"
    cols = df.columns.tolist()

    mapping = {
        "symbol":     _find(cols, "symbol"),
        "sub_sector": _find(cols, "sub_sector"),
        "market_cap": _find(cols, "market_cap"),
        "chg":        _find(cols, "daily_close_change", "change_1d", "price_change_1d"),
        "chg_w":      _find(cols, "weekly_close_change", "change_1w", "price_change_1w"),
    }
    missing = [k for k in ("symbol", "sub_sector", "market_cap", "chg") if not mapping[k]]
    if missing:
        raise KeyError(f"missing {missing}; available columns: {cols}")

    df = df.rename(columns={v: k for k, v in mapping.items() if v})
    if "chg_w" not in df:
        print("[warn] no weekly change column, falling back to daily 'chg'", file=sys.stderr)
        df["chg_w"] = df["chg"]
    df["chg_w"] = df["chg_w"].fillna(df["chg"])
    df = df.dropna(subset=["sub_sector", "market_cap", "chg"])
    return df.drop_duplicates("symbol").reset_index(drop=True)

def run_sector_scoring(df=None, n=10):
    """Step 1: rank sub-sectors from the company table."""
    df = load_companies() if df is None else df
    g = score_sectors(df)
    return g.head(n)                        # watchlist() ignores n < 10, so slice here

_SLUGS = None

def _slug_for(name):
    global _SLUGS
    if _SLUGS is None:                       # 1 call, cached 24h
        _SLUGS = {_norm(d["subsector"]): d["subsector"] for d in fetch_subsector_list()}
    return _SLUGS.get(_norm(name)) or _slug(name)

def run_subsector_detail(sub_sectors):
    rows, failed = [], []
    for ss in sub_sectors:
        slug = _slug_for(ss)
        try:
            rows.append(flatten_subsector(sectors_information(slug)))
        except Exception as e:
            failed.append(ss)
            print(f"[warn] {ss} -> {slug}: {type(e).__name__}: {e}", file=sys.stderr)
    return pd.DataFrame(rows), failed

def _clean(df):
    """NaN -> None so the result is JSON-safe later."""
    return df.astype(object).where(df.notna(), None).to_dict("records")

def run_sector_analysis(n=10):
    """Step 3: full pipeline, JSON-safe dict (ready for FastAPI later)."""
    df = load_companies()
    top = run_sector_scoring(df, n)
    detail, failed = run_subsector_detail(top.index)
    return {
        "n_companies": int(len(df)),
        "watchlist": _clean(top.reset_index(names="sub_sector")),
        "detail": _clean(detail),
        "failed": failed,
    }

def run_broker_ranking(date=None):
    resp = fetch_top_brokers(date=date, metric="gross", origin="all")
    df = rank_brokers(pd.DataFrame(resp["results"]), pd.DataFrame(fetch_broker_registry()))
    return resp["date"], df.sort_values("foreign_net", ascending=False)

def run_foreign_flow(companies_df, date=None):
    ff = pd.DataFrame(fetch_foreign_flow(date))      
    return foreign_flow_by_subsector(ff, companies_df)

    
    #--------------- Market trend analysis------------------    
def run_ihsg_market_trend():
    return run_IHSG_Market_trend()
    
    #------------- Sector Triggers Analysis + 2 functions 
def run_sector_triggers_analysis(n=10):
    df = load_companies()                                   
    top = run_sector_scoring(df, n)                         
    detail, failed = run_subsector_detail(top.index)        

    return {
        "n_companies": int(len(df)),                        
        "n_sub_sectors": int(df["sub_sector"].nunique()),   
        "sub_sector_counts": {                              
            str(k): int(v) for k, v in df["sub_sector"].value_counts().head(15).items()
        },
        "top": _clean(top.round(2).reset_index(names="sub_sector")), 
        "detail": _clean(detail.round(2)),                  
        "failed": failed,                                   
    }
    
    #------------------broker ranking--------------------------
def run_broker_analysis(date=None):
    d, ranked = run_broker_ranking(date)
    return {
        "date": d,
        "summary": cohort_summary(ranked),   
        "top": _clean(ranked.head(10)),
        "bottom": _clean(ranked.tail(10)),
    } 
    
#--------------- LLM-Rag Service 
def _build_rag_analysis(symbol):
    df = load_companies()                                   # loaded once, reused below

    row = df.loc[df["symbol"] == symbol]
    if row.empty:
        raise ValueError(f"{symbol} not found in companies list")
    sub_sector = row.iloc[0]["sub_sector"]

    # sector
    top = run_sector_scoring(df, n=len(df))                 # full ranking, so the ticker's sub-sector is always in it
    detail, _failed = run_subsector_detail([sub_sector])
    detail.index = [sub_sector]                             # demo.py expects index named "sub_sector"
    detail.index.name = "sub_sector"

    # broker
    _date, ranked = run_broker_ranking()
    cohorts = cohort_summary(ranked)
    foreign_sub = run_foreign_flow(df)                      # ~23 credits first time, then cached

    full_set_analysis = build_analysis(
        technical=run_technical_analysis(symbol),
        narrative=run_narrative_analysis(symbol),
        fundamentals=get_fundamentals(symbol),
        sector=sector_payload(sub_sector, detail=detail, top=top),
        broker=broker_payload(sub_sector, ranked=ranked, cohorts=cohorts, foreign_sub=foreign_sub),
    )
    return full_set_analysis

def _has_chunks(symbol: str) -> bool:
    grouped = retrieve(symbol)
    return any(d["chunks"] for d in grouped.values())

def _summary_cached_today(symbol: str) -> bool:
    return (CACHE_DIR / f"narrative_{symbol}_{DEFAULT_LANGUAGE}_{date.today().isoformat()}.json").exists()

def run_rag_ingest(symbol="BBCA.JK"):
    return ingest(symbol, _build_rag_analysis(symbol))

def run_rag_summary(symbol="BBCA.JK", refresh=False):
    if refresh or not _has_chunks(symbol) or not _summary_cached_today(symbol):
        analysis = _build_rag_analysis(symbol)
        if not analysis:
            raise RuntimeError(f"No analysis data built for {symbol}")
        n = ingest(symbol, analysis)
        print(f"[rag] ingested {symbol}: {n}")
    return summarize(symbol, refresh=refresh).model_dump(mode="json")

def run_rag_context(symbol="BBCA.JK"):
    return {"context": _format_context(retrieve(symbol))}

#company list 
def run_company_list():
    df = load_companies()
    name_col = next((c for c in df.columns if c == "name" or c.endswith("company_name") or c.endswith(".name")), None)
    out = df[["symbol", "sub_sector", "market_cap", "chg", "chg_w"]].copy()
    out["name"] = df[name_col] if name_col else df["symbol"]
    return out