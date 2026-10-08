import os
import sys
import json
import requests
from datetime import date, timedelta, datetime, timezone    
import re
from dotenv import load_dotenv
import time
import hashlib
from pathlib import Path

from app.Cache.Cache import make_key, get_or_fetch

load_dotenv()

API_KEY = os.getenv("SECTORS_API_KEY")
headers = {"Authorization": API_KEY}
BASE = "https://api.sectors.app/v2"
TIMEOUT = 30

# ---------- time windows (one place to change them) ----------
QUARTER_DAYS  = 90    # scoring window: filings, news, suspensions
PRICE_DAYS    = 120   # price/volume history, ~80 trading days
EVENT_DAYS    = PRICE_DAYS   # fetch events as far back as prices so volume spikes can be explained
UPCOMING_DAYS = 30
INSIDER_DAYS  = 365   # fetch insider transactions for the past year
DEFAULT_SYMBOL = "BBCA.JK"      # all data is BBCA.JK for now
PAGE_SIZE = 100

CACHE_DIR = Path(__file__).resolve().parent / ".api_cache"
MIN_INTERVAL = 0.4          # seconds between live calls
_last_call = [0.0]


def _since(days):
    return (date.today() - timedelta(days=days)).isoformat()

def _utc_today():
    return datetime.now(timezone.utc).date()

def _since(days):
    return (_utc_today() - timedelta(days=days)).isoformat()

def _today():
    return _utc_today().isoformat()

def _check(name, resp):
    """Raise on an error body, so a failed call never looks like 'no data'."""
    if isinstance(resp, dict) and "results" not in resp:
        raise RuntimeError(f"/{name}/ returned: {str(resp)[:300]}")
    return resp

def _ts_date(row):
    return datetime.fromisoformat(str(row["timestamp"])[:10]).date()

def _is_err(r):
    return isinstance(r, dict) and ("error" in r or "details" in r)

def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def _get(path, params=None, retries=4, cache_hours=0):
    key = None
    if cache_hours:
        CACHE_DIR.mkdir(exist_ok=True)
        raw = json.dumps([path, params or {}], sort_keys=True, default=str)
        key = CACHE_DIR / (hashlib.md5(raw.encode()).hexdigest() + ".json")
        if key.exists() and (time.time() - key.stat().st_mtime) < cache_hours * 3600:
            return json.loads(key.read_text(encoding="utf-8"))

    for attempt in range(retries + 1):
        wait = MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()

        r = requests.get(f"{BASE}{path}", headers=headers, params=params, timeout=TIMEOUT)
        try:
            data = r.json()
        except ValueError:
            data = {"error": r.text[:200]}

        limited = r.status_code == 429 or (
            isinstance(data, dict) and "RATE_LIMIT" in str(data.get("error", "")))
        if limited and attempt < retries:
            try:
                delay = float(r.headers.get("Retry-After", ""))
            except ValueError:
                delay = min(2 ** (attempt + 1), 20)
            print(f"[rate-limit] {path}: waiting {delay:.0f}s (retry {attempt + 1}/{retries})", file=sys.stderr)
            time.sleep(delay)
            continue

        if key and not (isinstance(data, dict) and "error" in data):   # cache successes only
            key.write_text(json.dumps(data), encoding="utf-8")
        return data

def _rows(resp):
    if resp is None:
        return []
    return resp if isinstance(resp, list) else resp.get("results", [])

def _warn_if_capped(name, resp, limit):
    n = len(_rows(resp))
    if n >= limit:
        print(f"[warn] {name}: got {n} rows = limit {limit}, older rows are cut off", file=sys.stderr)

def _bare(symbol):
    """BBCA.JK -> BBCA (price/fundamental endpoints use the bare ticker)."""
    return symbol.split(".")[0].upper()

def _ttl(hours):
    """hours -> seconds for Redis (min 60s, Redis rejects ex=0)."""
    return max(int(hours * 3600), 60)

def _guard(name, resp):
    """Never cache an error body as if it were data."""
    if _is_err(resp):
        raise RuntimeError(f"/{name}/ returned: {str(resp)[:300]}")
    return resp


# ---------- Technical core data ----------
def IHSG_Index_Market_Summary():
    key = make_key("raw:ihsg")
    def _fetch():
        return _guard("index-daily/ihsg", _get("/index-daily/ihsg/"))
    return get_or_fetch(key, _ttl(0.25), _fetch)

def fetch_Stock_data(symbol=DEFAULT_SYMBOL, days=PRICE_DAYS, chunk_days=60):
    key = make_key("raw:stock_data", symbol=_bare(symbol), days=days, chunk_days=chunk_days)
    def _fetch():
        s = _bare(symbol).lower()
        end = _utc_today()
        cur = end - timedelta(days=days)
        out = []
        while cur <= end:
            chunk_end = min(cur + timedelta(days=chunk_days - 1), end)
            resp = _get(f"/daily/{s}/", {"start": cur.isoformat(), "end": chunk_end.isoformat()}, cache_hours=6)
            if isinstance(resp, list):
                out += resp
                cur = chunk_end + timedelta(days=1)
                continue
            msg = str(resp.get("error", "")) if isinstance(resp, dict) else ""
            m = re.search(r"Today is (\d{4}-\d{2}-\d{2})", msg)
            if m:                                   # server's "today" differs from ours
                end = date.fromisoformat(m.group(1))
                continue
            raise RuntimeError(f"/daily/{s}/ {cur}..{chunk_end} returned: {str(resp)[:300]}")
        return out
    return get_or_fetch(key, _ttl(6), _fetch)

def fetch_report_data():
    key = make_key("raw:sectors_report")
    def _fetch():
        # original range was 29 days, so this endpoint may be capped near 30 days
        return _guard("sectors", _get("/sectors/", {"start": _since(29), "end": _today()}))
    return get_or_fetch(key, _ttl(6), _fetch)


# ---------- Company fundamentals (report + last 4 quarters) ----------
def fetch_company_fundamentals(symbol=DEFAULT_SYMBOL):
    key = make_key("raw:fundamentals", symbol=_bare(symbol))
    def _fetch():
        s = _bare(symbol)
        report = _guard("company/report", _get(f"/company/report/{s}/", {"sections": "overview,valuation,financials"}))
        quarters = _get(f"/financials/quarterly/{s}/", {"n_quarters": 4})

        if not isinstance(quarters, list):  # error body -> analysis falls back to annual numbers
            quarters = []

        return report, quarters
    return get_or_fetch(key, _ttl(24), _fetch)

def fetch_company_report(symbol=DEFAULT_SYMBOL):
    key = make_key("raw:company_report", symbol=_bare(symbol))
    def _fetch():
        return _guard("company/report", _get(f"/company/report/{_bare(symbol)}/"))
    return get_or_fetch(key, _ttl(24), _fetch)


# ---------- Screeners ----------
_WHERE = ("sub_sector+IS+NOT+NULL+and+market_cap+IS+NOT+NULL"
          "+and+daily_close_change+IS+NOT+NULL")

def fetch_all_companies(cache_hours=1, max_pages=30):
    """All IDX companies, paginated. Returns a list of rows."""
    key = make_key("raw:all_companies", max_pages=max_pages)
    def _fetch():
        rows, seen, offset = [], set(), 0
        for _ in range(max_pages):
            resp = _check("companies", _get(
                f"/companies/?where={_WHERE}&order_by=daily_close_change"
                f"&limit={PAGE_SIZE}&offset={offset}&include_query_values=true",
                cache_hours=cache_hours))
            batch = _rows(resp)
            if not batch:                       # stop on empty page, not on a short page,
                break                           # in case the API caps below PAGE_SIZE
            for r in batch:
                if r.get("symbol") not in seen:
                    seen.add(r.get("symbol"))
                    rows.append(r)
            offset += len(batch)
        return rows
    return get_or_fetch(key, _ttl(cache_hours), _fetch)

def sectors_information(sub_sector="banks", cache_hours=6):
    key = make_key("raw:subsector_report", sub_sector=sub_sector)
    def _fetch():
        resp = _get(f"/subsector/report/{sub_sector}/", cache_hours=cache_hours)
        if isinstance(resp, dict) and "error" in resp:
            raise RuntimeError(f"/subsector/report/{sub_sector}/ returned: {str(resp)[:300]}")
        return resp
    return get_or_fetch(key, _ttl(cache_hours), _fetch)

def fetch_subsector_list(cache_hours=24):
    key = make_key("raw:subsector_list")
    def _fetch():
        resp = _get("/subsectors/", cache_hours=cache_hours)
        if _is_err(resp) or not isinstance(resp, list):
            raise RuntimeError(f"/subsectors/ returned: {str(resp)[:300]}")
        return resp
    return get_or_fetch(key, _ttl(cache_hours), _fetch)


# ---------- Narrative: news, filings, corporate actions, suspensions ----------
def get_corporate_actions(symbol=DEFAULT_SYMBOL):
    key = make_key("raw:corporate_actions", symbol=_bare(symbol))
    def _fetch():
        resp = _get(f"/company/corporate-actions/{_bare(symbol)}/", cache_hours=6)
        if isinstance(resp, dict) and "error" in resp:
            raise RuntimeError(f"/company/corporate-actions/ returned: {str(resp)[:300]}")
        return resp
    return get_or_fetch(key, _ttl(6), _fetch)

def get_Corporate_Filings(symbol, days=INSIDER_DAYS, limit=100):
    key = make_key("raw:filings", symbol=symbol, days=days, limit=limit)
    def _fetch():
        resp = _check("filings", _get("/filings/", {"symbol": symbol, "start": _since(days), "limit": limit},
                                      cache_hours=6))
        rows = _rows(resp)

        bare = _bare(symbol)
        foreign = [r for r in rows if bare not in json.dumps(r)]
        if foreign:
            print(f"[warn] filings: {len(foreign)}/{len(rows)} rows are not {bare}, filter ignored by API; "
                  f"filtering locally", file=sys.stderr)
            rows = [r for r in rows if bare in json.dumps(r)]
        _warn_if_capped("filings", {"results": rows}, 30)     # the API returned 30 rows max per call earlier
        print(f"[info] filings for {bare}: {len(rows)} rows", file=sys.stderr)
        return {"results": rows}
    return get_or_fetch(key, _ttl(6), _fetch)

def get_news_articles(symbol, days=EVENT_DAYS, cap=30, max_calls=60, window_days=14):
    key = make_key("raw:news", symbol=symbol, days=days, cap=cap,
                   max_calls=max_calls, window_days=window_days)
    def _fetch():
        calls = [0]

        def fetch(start, end, depth=0):
            if calls[0] >= max_calls:
                return []
            calls[0] += 1
            resp = _check("news", _get("/news/", {"symbols": symbol, "limit": 50,
                                                  "start": start.isoformat(), "end": end.isoformat()},
                                       cache_hours=6))
            rows = _rows(resp)
            inside = [r for r in rows if start <= _ts_date(r) <= end]
            if len(rows) >= cap and len(inside) == len(rows) and (end - start).days >= 1 and depth < 5:
                mid = start + (end - start) // 2
                newer = fetch(mid + timedelta(days=1), end, depth + 1)    # newer half first
                older = fetch(start, mid, depth + 1)
                return newer + older
            return inside

        end = _utc_today()
        windows, cur = [], end - timedelta(days=days)
        while cur <= end:
            w_end = min(cur + timedelta(days=window_days - 1), end)
            windows.append((cur, w_end))
            cur = w_end + timedelta(days=1)

        rows = []
        for start, w_end in reversed(windows):            # newest window first
            rows += fetch(start, w_end)
            if calls[0] >= max_calls:
                print(f"[warn] news hit the {max_calls}-call cap; only the OLDEST windows are missing", file=sys.stderr)
                break

        seen, out = set(), []
        for r in rows:
            if r.get("source") not in seen:
                seen.add(r.get("source"))
                out.append(r)
        return {"results": out}
    return get_or_fetch(key, _ttl(6), _fetch)

def get_stock_suspensions(symbol=DEFAULT_SYMBOL, days=EVENT_DAYS, limit=100):
    key = make_key("raw:suspensions", symbol=symbol, days=days, limit=limit)
    def _fetch():
        params = {"start": _since(days), "limit": limit}
        if symbol:
            params["symbol"] = symbol
        resp = _check("suspensions", _get("/suspensions/", params, cache_hours=6))
        _warn_if_capped("suspensions", resp, limit)
        return resp
    return get_or_fetch(key, _ttl(6), _fetch)


# ---------- Broker Data analysis ----------
def _is_err(r):
    return isinstance(r, dict) and ("error" in r or "details" in r)

def fetch_broker_registry(cache_hours=24 * 7):
    key = make_key("raw:broker_registry")
    def _fetch():
        resp = _get("/brokers/", cache_hours=cache_hours)             # 1 credit
        if _is_err(resp) or not isinstance(resp, list):
            raise RuntimeError(f"/brokers/ returned: {str(resp)[:300]}")
        return resp
    return get_or_fetch(key, _ttl(cache_hours), _fetch)

def fetch_top_brokers(date=None, metric="gross", origin="all", cohort="all",
                      foreign=False, n_brokers=None, cache_hours=6):
    key = make_key("raw:top_brokers", date=date, metric=metric, origin=origin,
                   cohort=cohort, foreign=foreign, n_brokers=n_brokers)
    def _fetch():
        params = {"metric": metric, "origin": origin, "cohort": cohort,
                  "foreign": str(foreign).lower()}
        if date:
            params["date"] = date
        if n_brokers:
            params["n_brokers"] = n_brokers
        resp = _get("/brokers/top/", params, cache_hours=cache_hours)  # 2 credits
        if _is_err(resp) or "results" not in resp:
            raise RuntimeError(f"/brokers/top/ returned: {str(resp)[:300]}")
        if resp.get("origin") != origin:                               # catches the "foreign" default you hit
            raise RuntimeError(f"asked origin={origin}, API returned {resp.get('origin')}")
        return resp
    return get_or_fetch(key, _ttl(cache_hours), _fetch)

def fetch_foreign_flow(date=None, max_pages=30, limit=30):
    """Full-universe foreign flow for one day. ~23 credits, cached."""
    key = make_key("raw:foreign_flow", date=date, max_pages=max_pages, limit=limit)
    cache = 24 * 30 if date else 6          # past dates never change
    def _fetch():
        rows, offset = [], 0
        for _ in range(max_pages):
            params = {"limit": limit, "offset": offset}
            if date:
                params["date"] = date
            resp = _get("/foreign-flow/", params, cache_hours=cache)   # 1 credit per page
            if _is_err(resp) or "results" not in resp:
                raise RuntimeError(f"/foreign-flow/ returned: {str(resp)[:300]}")
            rows += resp["results"]
            pg = resp.get("pagination") or {}
            if not pg.get("has_next"):
                break
            offset = pg["next_offset"]
        return rows
    return get_or_fetch(key, _ttl(cache), _fetch)

def fetch_broker_activity(code, cache_hours=6, **params):
    key = make_key("raw:broker_activity", code=code, **params)
    def _fetch():
        resp = _get(f"/broker-activity/{code}/", params or None, cache_hours=cache_hours)
        if _is_err(resp):
            raise RuntimeError(f"/broker-activity/{code}/ returned: {str(resp)[:300]}")
        return resp
    return get_or_fetch(key, _ttl(cache_hours), _fetch)