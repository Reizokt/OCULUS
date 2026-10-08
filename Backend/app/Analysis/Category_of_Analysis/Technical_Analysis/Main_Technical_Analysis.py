#imports 
import pandas as pd 
import numpy as np
import math 

# 1. Market Trends 
def Market_Trends_Analysis(Data):
    close = Data['Close']
    n = len(close)

    if n < 2:
        return {"slope": 0, "degree": 0, "trend": "Neutral", "normalize_slope": 0.5}

    x = np.arange(n)  # ← moved outside the if block
    slope, _ = np.polyfit(x, close.values, 1)

    # Normalise slope as % of mean price so degree is scale-independent
    slope_pct = (slope / close.mean()) * 100

    # Convert to angle in degrees
    degree = math.degrees(math.atan(slope_pct))

    # Classify by degree threshold
    if degree > 20:
        trend = "Strong Bull"
    elif degree > 7:
        trend = "Bull"
    elif degree < -20:
        trend = "Strong Bear"
    elif degree < -7:
        trend = "Bear"
    else:
        trend = "Sideways / Neutral"

    # Smooth 0-1 normalisation via tanh so it never hits hard edges
    normalize = (math.tanh(slope_pct / 2) + 1) / 2
    
    return{
        "slope": round(slope, 6),
        "slope_pct_per_bar": round(slope_pct, 4),
        "degree": round(degree, 2),
        "trend": trend,
        "normalize_slope": round(normalize, 4),
    }

# 2. Price Action Analysis/ area of support and Resistance + equilibrium zone 
def Price_Action_Analysis(Data, tolerance=0.03, min_touches=2, required_touches=3):
    if len(Data) < 10:
        return {"zones": [], "equilibrium": None, "range": (None, None),
                "validity": "Insufficient data", "breakout": None, "position_pct": None}

    # Range is built WITHOUT the latest bar, so one anomaly bar can't rewrite it
    ref       = Data.iloc[:-1]
    highs     = ref['High'].values
    lows      = ref['Low'].values
    ref_close = float(ref['Close'].iloc[-1])
    last      = float(Data['Close'].iloc[-1])

    thr = (highs.max() - lows.min()) * tolerance      # cluster radius

    def cluster_levels(levels, thr):
        levels = sorted(levels)
        used, out = [False] * len(levels), []
        for i in range(len(levels)):
            if used[i]:
                continue
            grp = [levels[i]]
            for j in range(i + 1, len(levels)):
                if not used[j] and abs(levels[j] - levels[i]) <= thr:
                    grp.append(levels[j])
                    used[j] = True
            out.append(np.mean(grp))
            used[i] = True
        return out

    def visits(level):
        # separate visits, not bars: consecutive bars near a level count once
        hit = (np.abs(highs - level) <= thr) | (np.abs(lows - level) <= thr)
        return int((hit & ~np.r_[False, hit[:-1]]).sum())

    zones = []
    for lvl in cluster_levels(np.concatenate([highs, lows]), thr):
        v = visits(lvl)
        if v >= min_touches:
            zones.append({
                "level":     round(lvl, 4),
                "touches":   v,
                "validated": v >= required_touches,
                "type":      "Support" if lvl < ref_close else "Resistance",
            })
    zones.sort(key=lambda z: z["level"])

    supports    = [z for z in zones if z["type"] == "Support"]
    resistances = [z for z in zones if z["type"] == "Resistance"]
    s = max(supports,    key=lambda z: z["level"]) if supports else None
    r = min(resistances, key=lambda z: z["level"]) if resistances else None

    equilibrium, position = None, None
    if s and r:
        equilibrium = {
            "zone_low":  s["level"],
            "zone_high": r["level"],
            "midpoint":  round((s["level"] + r["level"]) / 2, 4),
        }
        if r["level"] > s["level"]:
            position = round((last - s["level"]) / (r["level"] - s["level"]) * 100, 1)

    s_ok = bool(s and s["validated"])
    r_ok = bool(r and r["validated"])
    validity = ("Validated" if s_ok and r_ok
                else "Partial (support only)" if s_ok
                else "Partial (resistance only)" if r_ok
                else "Not validated")

    if r and last > r["level"]:
        breakout = "Above range"
    elif s and last < s["level"]:
        breakout = "Below range"
    else:
        breakout = "Inside range"

    return {
        "zones":              zones,
        "equilibrium":        equilibrium,
        "range":              (s["level"] if s else None, r["level"] if r else None),
        "support_touches":    s["touches"] if s else 0,
        "resistance_touches": r["touches"] if r else 0,
        "validity":           validity,
        "last_close":         round(last, 2),
        "position_pct":       position,     # 0 = at support, 100 = at resistance
        "breakout":           breakout,     # judged against the range built before the latest bar
    }
    
def Volatility_Analysis(Data, window=14, horizon=5, lam=0.94, hist=500,horizons=(1, 5, 10, 20)):
    cl   = Data['Close'].astype(float)
    last = float(cl.iloc[-1])
    rets = np.log(cl).diff().dropna()
    horizons = sorted(set(horizons) | {horizon})

    # ATR (only if High/Low exist)
    atr = atr_pct = None
    if {'High', 'Low'} <= set(Data.columns):
        hi, lo = Data['High'].astype(float), Data['Low'].astype(float)
        tr = pd.concat([hi - lo, (hi - cl.shift()).abs(), (lo - cl.shift()).abs()], axis=1).max(axis=1)
        a = tr.rolling(window).mean().iloc[-1]
        if not np.isnan(a):
            atr, atr_pct = float(a), float(a) / last * 100

    # Plain and robust volatility
    recent    = rets.tail(window)
    daily_std = float(recent.std())
    long_std  = float(rets.tail(60).std() if len(rets) >= 60 else rets.std())
    mad       = float(np.median(np.abs(recent - np.median(recent))) * 1.4826)
    outlier_ratio = round(daily_std / mad, 2) if mad else None

    ratio = daily_std / long_std if long_std else np.nan
    state = ("Elevated" if ratio > 1.3 else "Compressed" if ratio < 0.7 else "Normal")

    # EWMA volatility (RiskMetrics)
    r      = rets.tail(hist)
    ew_var = (r ** 2).ewm(alpha=1 - lam, adjust=False).mean()
    sig_d  = float(np.sqrt(ew_var.iloc[-1]))                 # current daily sigma

    # Empirical quantiles of vol-standardized horizon returns
    z = (r / np.sqrt(ew_var).shift(1)).dropna()              # standardized by prior-day sigma
    ranges, method = {}, "empirical"
    for h in horizons:
        zh = (z.rolling(h).sum() / np.sqrt(h)).dropna()
        if len(zh) >= 100:
            q = zh.quantile([0.025, 0.16, 0.84, 0.975]).values
        else:
            q, method = np.array([-1.96, -1.0, 1.0, 1.96]), "normal (too little history)"
        s = sig_d * np.sqrt(h)
        ranges[h] = {
            "range_68": (round(last * np.exp(q[1] * s), 2), round(last * np.exp(q[2] * s), 2)),
            "range_95": (round(last * np.exp(q[0] * s), 2), round(last * np.exp(q[3] * s), 2)),
        }

    return {
        "atr": round(atr, 4) if atr is not None else None,
        "atr_pct": round(atr_pct, 2) if atr_pct is not None else None,
        "daily_std_pct": round(daily_std * 100, 3),
        f"{horizon}d_std_pct": round(daily_std * np.sqrt(horizon) * 100, 3),   # kept for old callers
        "sigma_ewma_pct": round(sig_d * 100, 3),
        f"{horizon}d_ewma_pct": round(sig_d * np.sqrt(horizon) * 100, 3),
        "vol_ratio_vs_60d": round(ratio, 2) if not np.isnan(ratio) else None,
        "state": state,
        "outlier_ratio": outlier_ratio,                        # std / robust sigma
        "outlier_in_window": bool(outlier_ratio and outlier_ratio > 1.5),
        "method": method,
        "ranges": ranges,                                      # {horizon: {range_68, range_95}}
    }

#7. Volume Analysis
def Volume_Analysis(Data, window=20):
    cl  = Data['Close'].values
    op  = Data['Open'].values
    vol = Data['Volume'].values

    avg_vol = pd.Series(vol).rolling(window).mean().values

    bull_vol = np.where(cl > op, vol, 0)
    bear_vol = np.where(cl < op, vol, 0)

    total        = vol.sum()
    bull_ratio   = bull_vol.sum() / total if total else 0
    bear_ratio   = bear_vol.sum() / total if total else 0

    # Bias on most-recent `window` bars
    rb = bull_vol[-window:].sum()
    rr = bear_vol[-window:].sum()

    if rb > rr * 1.2:
        volume_bias = "Bullish Volume Dominance"
    elif rr > rb * 1.2:
        volume_bias = "Bearish Volume Dominance"
    else:
        volume_bias = "Balanced / Neutral Volume"

    last_avg    = avg_vol[-1]
    vol_spike   = bool(vol[-1] > last_avg * 1.5) if not np.isnan(last_avg) else False
    spike_type  = ("Bull Spike" if (vol_spike and cl[-1] > op[-1])
                   else "Bear Spike" if (vol_spike and cl[-1] < op[-1])
                   else None)

    return {
        "bull_ratio":         round(bull_ratio, 4),
        "bear_ratio":         round(bear_ratio, 4),
        "volume_bias":        volume_bias,
        "last_volume":        int(vol[-1]),
        "last_avg_volume":    round(last_avg, 2) if not np.isnan(last_avg) else None,
        "is_volume_spike":    vol_spike,
        "spike_type":         spike_type,
        "bull_volume_series": bull_vol.tolist(),
        "bear_volume_series": bear_vol.tolist(),
    }

def Technical_Forecast(Data, horizon=5, trend_windows=(14, 22)):
    cols  = set(Data.columns)
    n     = len(Data)
    last  = float(Data['Close'].iloc[-1])
    notes = []

    def run(name, fn, needs, min_bars):
        missing = [c for c in needs if c not in cols]
        if missing:
            notes.append(f"{name}: skipped, missing {missing}")
            return None
        if n < min_bars:
            notes.append(f"{name}: skipped, {n} bars (needs {min_bars})")
            return None
        try:
            return fn()
        except Exception as e:
            notes.append(f"{name}: error {type(e).__name__}: {e}")
            return None

    vol = run("volatility", lambda: Volatility_Analysis(Data, horizon=horizon), ['Close'], 15)

    out = {
        "horizon_bars": horizon,
        "last_close":   round(last, 2),
        "bars_used":    n,
    }

    if vol:
        out["range_68pct"]  = vol["ranges"][horizon]["range_68"]
        out["range_95pct"]  = vol["ranges"][horizon]["range_95"]
        out["all_horizons"] = vol["ranges"]
        out["volatility"]   = {k: vol[k] for k in
                               ("state", "sigma_ewma_pct", "outlier_in_window", "method")}

    # Context sections (they never change the ranges above)
    out["trend"] = {f"window_{w}": run(f"trend_{w}",
                        lambda w=w: Market_Trends_Analysis(Data.tail(w)), ['Close'], w)
                    for w in trend_windows}
    out["structure"] = run("price_action", lambda: Price_Action_Analysis(Data.tail(120)),
                           ['High', 'Low', 'Close'], 30)
    out["volume"]    = run("volume", lambda: Volume_Analysis(Data),
                           ['Open', 'Close', 'Volume'], 20)

    out["data_notes"] = notes
    return out

