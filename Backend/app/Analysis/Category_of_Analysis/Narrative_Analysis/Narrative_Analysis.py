#Narrative analysis Tags 
# narrative_analysis.py
import pandas as pd

def _d(x):
    return pd.to_datetime(x).normalize() if x else None

def event(date, source, category, direction, weight, title, detail=None):
    return {"date": _d(date), "source": source, "category": category,
            "direction": direction, "weight": weight, "title": title,
            "detail": detail or {}}

def _row_symbols(r):
    s = r.get("symbols") or r.get("tickers") or r.get("symbol") or []
    s = [s] if isinstance(s, str) else list(s)
    return {x.split(".")[0].upper() for x in s if x}

def _mentions(title, symbol):
    return symbol.split(".")[0].lower() in title.lower()

def _bare(s):
    return str(s or "").split(".")[0].upper()

def normalize_corporate_actions(ca, symbol):
    acts = (ca or {}).get("corporate_actions", ca or {})   # per-company endpoint wraps the lists
    out = []

    def first(r, *keys):
        for k in keys:
            if r.get(k) not in (None, ""):
                return r[k]
        return None

    for r in (acts.get("dividend") or acts.get("dividends") or []):
        ex = first(r, "ex_date", "ex_dividend_date")
        if not ex:
            continue
        amount = first(r, "dividend_amount", "amount", "cash_dividend", "value")
        y = (r.get("dividend_yield") or 0) * 100
        out.append(event(ex, "corporate_action", "Dividend", 1, 0.3,
            f"Dividend Rp{amount} (yield {y:.2f}%)",
            {"amount": amount, "payment_date": first(r, "payment_date", "pay_date")}))

    for r in (acts.get("stock_split") or acts.get("stock_splits") or []):
        d = first(r, "date", "ex_date", "split_date")
        if d:
            out.append(event(d, "corporate_action", "Stock split", 0, 0.0,
                f"Stock split {first(r, 'ratio', 'split_ratio')}",
                {"ratio": first(r, "split_ratio", "ratio")}))

    for r in (acts.get("right_issue") or acts.get("rights_issue") or []):
        ex = first(r, "ex_date", "cum_date")
        if ex:
            out.append(event(ex, "corporate_action", "Rights issue", -1, 0.5,
                f"Rights issue at Rp{r.get('price')} ({r.get('old_ratio')}:{r.get('new_ratio')})",
                {"price": r.get("price")}))

    for r in (acts.get("agm") or []):
        if r.get("agm_date"):
            out.append(event(r["agm_date"], "corporate_action", "AGM", 0, 0.0, "AGM / RUPS",
                {"place": r.get("agm_place"), "result": r.get("agm_result")}))
    return out

#Normalize insider transactions
def normalize_insider(rows, symbol):
    want = symbol.split(".")[0].upper()
    out = []
    for r in rows:
        if want not in _row_symbols(r):
            continue
        t = (r.get("transaction_type") or "").lower()
        if t not in ("buy", "sell"):
            continue
        sign = 1 if t == "buy" else -1
        pct = abs(float(r.get("share_percentage_transaction") or 0))
        val = abs(float(r.get("transaction_value") or 0))
        out.append(event(r["timestamp"], "insider", "Insider " + t,
            sign, min(pct / 2, 1.0),                      # a 2% stake change = full weight
            r.get("title", ""),
            {"holder": r.get("holder_name"), "holder_type": r.get("holder_type"),
             "pct_before": r.get("share_percentage_before"),
             "pct_after": r.get("share_percentage_after"),
             "value": sign * val}))
    return out

#Normalize news articles
def normalize_news(rows, symbol, sector=None):
    want = symbol.split(".")[0].upper()
    out = []
    for r in rows:
        tags = {t.lower() for t in r.get("tags", [])}
        direction = 1 if "bullish" in tags else -1 if "bearish" in tags else 0
        direct = want in _row_symbols(r)
        if not direct and not (sector and r.get("sector") == sector):
            continue
        n = max(len(r.get("symbols", [])), 1)
        weight = max(0.3, 1.0 - 0.1 * (n - 1)) if direct else 0.3   # many-ticker articles count less
        out.append(event(r["timestamp"], "news", "News", direction, weight,
            r["title"],
            {"tags": r.get("tags", []), "url": r["source"],
             "dimensions": [k for k, v in r.get("dimension", {}).items() if v]}))
    return out

def normalize_suspensions(rows, symbol):
    want = _bare(symbol)
    out = []
    for r in rows:
        if want not in _row_symbols(r):
            continue
        d = r.get("suspension_date") or r.get("date") or r.get("timestamp")
        if not d:
            continue
        out.append(event(d, "suspension", "Suspension", -1, 1.0, "Trading suspended",
                         {"reason": r.get("reason"), "pdf": r.get("pdf_url")}))
    return out
    
def Narrative_Analysis(symbol, events, today=None, lookback_days=90,
                       upcoming_days=30, half_life=14, spike_dates=None, insider_days=365):
    today = pd.Timestamp(today or pd.Timestamp.today()).normalize()
    start = today - pd.Timedelta(days=lookback_days)
    end   = today + pd.Timedelta(days=upcoming_days)

    past     = [e for e in events if e["date"] and start <= e["date"] <= today]
    upcoming = sorted([e for e in events if e["date"] and today < e["date"] <= end],
                      key=lambda e: e["date"])

    # News sentiment: recency-decayed weighted average, -1..1
    num = den = 0.0
    news = [e for e in past if e["source"] == "news"]
    for e in news:
        w = e["weight"] * 0.5 ** ((today - e["date"]).days / half_life)
        num += e["direction"] * w
        den += w
    score = num / den if den else 0.0
    label = "Positive" if score > 0.25 else "Negative" if score < -0.25 else "Neutral"

    # Insider flow: sparse data, so it gets its own, longer window
    ins_start = today - pd.Timedelta(days=insider_days)
    ins = sorted([e for e in events
                  if e["source"] == "insider" and e["date"] and ins_start <= e["date"] <= today],
                 key=lambda e: e["date"])
    net = sum(e["detail"]["value"] for e in ins)
    net_recent = sum(e["detail"]["value"] for e in ins if e["date"] >= start)
    last_ins = ins[-1]["date"] if ins else None
    days_since = (today - last_ins).days if last_ins is not None else None

    # Hard flags
    flags = []
    if any(e["category"] == "Suspension" for e in past):
        flags.append("Recent suspension: check the stock has resumed trading")
    if any(e["category"] == "Stock split" for e in past):
        flags.append("Stock split in window: confirm prices are split-adjusted before trusting technicals")
    if ins and days_since > lookback_days:
        flags.append(f"Insider activity is stale: last transaction {last_ins.date()} ({days_since} days ago)")
    for e in upcoming:
        if e["category"] == "Dividend":
            flags.append(f"Ex-dividend {e['date'].date()}: price will drop by about Rp{e['detail']['amount']}; forecast ranges ignore this")
        if e["category"] == "Rights issue":
            flags.append(f"Rights issue ex-date {e['date'].date()}: dilution risk")
        if e["category"] == "Stock split":
            flags.append(f"Stock split {e['date'].date()}: price series will change")

    # Link events to technical signals (spike_dates comes from the service)
    history = [e for e in events if e["date"] and e["date"] <= today]
    aligned = []
    for d in (spike_dates or []):
        d = pd.Timestamp(d).normalize()
        near = [e for e in history if abs((e["date"] - d).days) <= 1 and e["category"] != "AGM"]
        near.sort(key=lambda e: (not _mentions(e["title"], symbol),
                                 abs((e["date"] - d).days),
                                 -e["weight"]))
        if near:
            aligned.append({"date": str(d.date()), "technical": "Volume spike",
                            "n_events": len(near),
                            "explained_by": [e["title"] for e in near[:3]]})

    themes = {}
    for e in news:
        for dim in e["detail"]["dimensions"]:
            themes[dim] = themes.get(dim, 0) + 1

    return {
        "symbol": symbol,
        "window": (str(start.date()), str(today.date())),
        "sentiment": {"label": label, "score": round(score, 2), "n_articles": len(news)},
        "themes": dict(sorted(themes.items(), key=lambda kv: -kv[1])),
        "insider": {
            "window_days": insider_days,
            "net_value": net,
            "net_value_recent": net_recent,
            "bias": ("Accumulation" if net > 0 else "Distribution" if net < 0
                     else ("Balanced" if ins else "No filings")),
            "transactions": len(ins),
            "last_transaction": str(last_ins.date()) if last_ins is not None else None,
            "days_since_last": days_since,
            "recent": bool(days_since is not None and days_since <= lookback_days),
        },
        "upcoming": [{"date": str(e["date"].date()), "type": e["category"], "title": e["title"]}
                     for e in upcoming],
        "flags": flags,
        "event_alignment": aligned,
        "top_headlines": [e["title"] for e in sorted(news, key=lambda e: -e["weight"] * (e["date"] - start).days)[:5]],
    }