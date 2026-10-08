#import 
import numpy as np
import pandas as pd

# Analysis to Sector Mapping 
MIN_COMPANIES = 5
def score_sectors(df, min_companies=MIN_COMPANIES, min_sectors=10):
    def agg(x):
        cap = x["market_cap"]
        return pd.Series({
            "companies": len(x),
            "median_chg": x["chg_w"].median(),
            "weighted_chg": (x["chg_w"] * cap).sum() / cap.sum(),
            "pct_advancing": (x["chg"] > 0).mean() * 100,
            "top_cap_share": cap.max() / cap.sum() * 100,
            "total_cap_tn": cap.sum() / 1e12,
            "best": x.loc[x["chg"].idxmax(), "symbol"],
            "worst": x.loc[x["chg"].idxmin(), "symbol"],
        })

    g_all = pd.DataFrame([agg(x).rename(name) for name, x in df.groupby("sub_sector")])

    # relax the minimum company count until at least `min_sectors` qualify
    mc = min_companies
    while mc > 1 and (g_all["companies"] >= mc).sum() < min_sectors:
        mc -= 1
    g = g_all[g_all["companies"] >= mc].copy()
    if mc < min_companies:
        print(f"note: only {(g_all['companies'] >= min_companies).sum()} sub-sectors had "
              f">= {min_companies} companies; relaxed to >= {mc}")

    g["strength"] = (
        0.4 * g["weighted_chg"].rank(pct=True)
        + 0.3 * g["median_chg"].rank(pct=True)
        + 0.3 * g["pct_advancing"].rank(pct=True)
    )
    narrow = g["top_cap_share"] > 60
    g.loc[narrow, "strength"] = 0.5 + (g.loc[narrow, "strength"] - 0.5) * 0.5
    g["flag"] = np.where(narrow, "one stock dominates", "")

    # attention = distance from neutral, in either direction
    g["attention"] = (g["strength"] - 0.5).abs() * 2
    g["direction"] = np.where(g["strength"] >= 0.5, "STRONG", "WEAK")
    return g.sort_values("attention", ascending=False)

def watchlist(g, n=10):
    cols = ["direction", "companies", "median_chg", "weighted_chg",
            "pct_advancing", "total_cap_tn", "best", "worst", "flag"]
    wl = g.head(max(n, 10))
    print(f"\n=== SECTORS TO WATCH ({len(wl)}) ===")
    print(wl[cols].round(2).to_string())
    return wl


def _pct(x):
    return np.nan if x is None else x * 100

def flatten_subsector(d):
    mc = (d.get("market_cap") or {}).get("mcap_summary") or {}
    ch = mc.get("mcap_change") or {}
    monthly = [v for _, v in sorted((mc.get("monthly_performance") or {}).items())
               if v is not None]
    mom_3m = np.prod([1 + v for v in monthly[-3:]]) - 1 if monthly else np.nan

    val = (d.get("valuation") or {}).get("historical_valuation") or {}
    years = sorted(val)
    cur = val[years[-1]] if years else {}
    hist_pe = [val[y]["pe"] for y in years[:-1]
               if val[y].get("pe") and val[y]["pe"] > 0]
    pe_vs_hist = (cur["pe"] / np.mean(hist_pe) - 1
                  if hist_pe and cur.get("pe") else np.nan)

    growth = d.get("growth") or {}
    g = growth.get("weighted_avg_growth_data") or {}
    last_eps_g = next((g[y]["avg_annual_earning_growth"] for y in sorted(g, reverse=True)
                       if g[y].get("avg_annual_earning_growth") is not None), np.nan)
    fc = growth.get("growth_forecasts") or {}
    fwd = fc[sorted(fc)[0]] if fc else {}

    stats = d.get("statistics") or {}
    stab = d.get("stability") or {}
    total_mc = (d.get("market_cap") or {}).get("total_market_cap")

    return {
        "sector": d.get("sector"), "sub_sector": d.get("sub_sector"),
        "companies": stats.get("total_companies"),
        "mcap_tn": np.nan if total_mc is None else total_mc / 1e12,
        "chg_1w": _pct(ch.get("1w")), "chg_ytd": _pct(ch.get("ytd")), "chg_1y": _pct(ch.get("1y")),
        "mom_3m": _pct(mom_3m),
        "pe": stats.get("filtered_median_pe"), "pe_vs_hist": _pct(pe_vs_hist),
        "pb": cur.get("pb"),
        "max_dd": _pct(stab.get("weighted_max_drawdown")),
        "vol": stab.get("weighted_rsd_close"),
        "eps_last": _pct(np.clip(last_eps_g, -1, 2)),
        "eps_fwd": _pct(fwd.get("eps_growth")), "rev_fwd": _pct(fwd.get("revenue_growth")),
    }
    
    