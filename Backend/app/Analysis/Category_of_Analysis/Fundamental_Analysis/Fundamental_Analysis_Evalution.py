"""
fundamentals_analysis.py -- core FUNDAMENTAL analysis (pure functions, no API calls).

Input : the raw `report` and `quarters` returned by data_api_call.fetch_company()
Output: metrics + status + 4 pillar scores + overall fundamental_score

    result = analyze(report, quarters)
"""
from datetime import date

IDN_CORP_TAX = 0.22


# ------------------------------------------------------------------ helpers
def div(a, b):
    return None if a is None or b in (None, 0) else a / b


def growth(cur, prev):
    """Growth on a zero/negative base is meaningless -> None."""
    return None if cur is None or prev is None or prev <= 0 else (cur - prev) / prev


def ttm_from_quarters(quarters):
    if len(quarters) < 4:
        return {}
    q = sorted(quarters, key=lambda x: x["date"], reverse=True)[:4]

    def tsum(k):
        v = [x.get(k) for x in q]
        return None if any(i is None for i in v) else sum(v)

    return {"as_of": q[0]["date"], "revenue": tsum("revenue"), "earnings": tsum("earnings"),
            "total_equity": q[0].get("total_equity"), "total_assets": q[0].get("total_assets")}


# ------------------------------------------------------------------ metrics
def compute_metrics(report, quarters, extras=False):
    ov, val, fin, fut = (report.get(k, {}) for k in ("overview", "valuation", "financials", "future"))

    hist = sorted((r for r in fin.get("historical_financials", []) if r.get("year") is not None),
                  key=lambda r: int(r["year"]))
    cur, prev = (hist[-1], hist[-2] if len(hist) > 1 else {}) if hist else ({}, {})
    year = int(cur["year"]) if cur else None

    ratios = {int(r["year"]): r for r in fin.get("historical_financial_ratio", [])}
    r = ratios.get(year, {})
    prof, liq, cap = r.get("profitability", {}), r.get("liquidity", {}), r.get("capital", {})

    ttm = ttm_from_quarters(quarters)
    is_bank = (ov.get("sub_sector") or "").lower() == "banks"

    revenue, ni, fcf = cur.get("revenue"), cur.get("earnings"), cur.get("free_cash_flow")
    equity, assets, debt = cur.get("total_equity"), cur.get("total_assets"), cur.get("total_debt")
    cash = cur.get("cash_and_equivalents") or cur.get("cash_only")
    ebit, ebitda, shares = cur.get("ebit"), cur.get("ebitda"), cur.get("outstanding_shares")
    price = val.get("last_close_price") or ov.get("last_close_price")

    # API tax is an AMOUNT, so rate = tax / pre-tax earnings
    t = div(cur.get("tax"), cur.get("earnings_before_tax"))
    tax_rate = min(max(t, 0), 0.4) if t is not None else IDN_CORP_TAX
    nopat = ebit * (1 - tax_rate) if ebit is not None else None
    invested = debt + equity - cash if None not in (debt, equity, cash) else None

    ni_ttm, eq_now, as_now = ttm.get("earnings"), ttm.get("total_equity"), ttm.get("total_assets")

    # 1. PROFITABILITY
    profitability = {
        "roe": div(ni_ttm, eq_now) if ni_ttm is not None else (prof.get("roe") or div(ni, equity)),
        "roa": div(ni_ttm, as_now) if ni_ttm is not None else (prof.get("roa") or div(ni, assets)),
        "net_profit_margin": div(ni_ttm, ttm.get("revenue")) if ni_ttm is not None
                             else (prof.get("net_profit_margin") or div(ni, revenue)),
    }
    if is_bank:
        profitability["net_interest_margin"] = prof.get("net_interest_margin")
        profitability["cost_to_income"] = prof.get("cost_to_income_ratio")
    else:
        profitability["roic"] = div(nopat, invested)
        profitability["fcf_margin"] = div(fcf, revenue)

    # 2. FINANCIAL HEALTH
    if is_bank:
        health = {"capital_adequacy_ratio": cap.get("capital_adequacy_ratio"),
                  "npl_ratio": div(cur.get("non_performing_loan"), cur.get("gross_loan")),
                  "loan_to_deposit": liq.get("loan_to_deposit_ratio"),
                  "casa_ratio": liq.get("casa_ratio")}
    else:
        health = {"debt_to_equity": div(debt, equity),
                  "debt_to_ebitda": div(debt, ebitda) if ebitda and ebitda > 0 else None,
                  "interest_coverage": div(ebit, abs(cur["interest_expense"])) if cur.get("interest_expense") else None,
                  "current_ratio": div(cur.get("current_assets"), cur.get("current_liabilities")),
                  "cash_to_debt": div(cash, debt),
                  # API's debt_to_equity_ratio is total LIABILITIES / equity (BBCA 2018: 4.43)
                  "liabilities_to_equity": r.get("leverage", {}).get("debt_to_equity_ratio")}

    # 3. GROWTH
    g = {"revenue_growth": growth(revenue, prev.get("revenue")),
         "eps_growth": fin.get("historical_eps", {}).get(str(year), {}).get("eps_growth"),
         "yoy_quarter_revenue_growth": fin.get("yoy_quarter_revenue_growth"),
         "yoy_quarter_earnings_growth": fin.get("yoy_quarter_earnings_growth")}
    if not is_bank:
        g["fcf_growth"] = growth(fcf, prev.get("free_cash_flow"))

    # 4. VALUATION
    hv = max(val.get("historical_valuation", []), key=lambda x: x["year"], default={})
    eps_ttm = div(ni_ttm, shares)
    pe = div(price, eps_ttm) if eps_ttm and eps_ttm > 0 else (
        div(price, fin.get("eps")) if fin.get("eps") and fin["eps"] > 0 else None)
    bvps = div(eq_now, shares)
    v = {"pe": pe, "pb": div(price, bvps) if bvps and bvps > 0 else hv.get("pb")}
    if not is_bank:
        v["ev_to_ebitda"] = hv.get("enterprise_to_ebitda")
        v["ev_to_revenue"] = hv.get("enterprise_to_revenue")

    flags = []
    if is_bank:
        flags.append("bank: scored on bank metrics (NIM, cost-to-income, CAR, NPL)")
    elif ebit is None:
        flags.append("no EBIT reported (non-bank financial?) - some metrics unavailable")
    if ni is not None and ni <= 0:
        flags.append("negative earnings - P/E and growth not meaningful")
    if year and year < date.today().year - 1:
        flags.append(f"latest annual data is {year} (stale)")
    if not ttm:
        flags.append("quarterly TTM unavailable - using annual figures")

    if extras:   # displayed only, never scored
        ratio = div(val.get("intrinsic_value"), price)
        ok = ratio is not None and ratio <= 5
        v["intrinsic_upside"] = ratio - 1 if ok else None
        v["forward_pe"] = val.get("forward_pe")
        if ratio and not ok:
            flags.append(f"intrinsic_value is {ratio:.0f}x price - unreliable")
        fc = sorted(fut.get("company_growth_forecasts") or [], key=lambda x: x["estimate_year"])
        if fc:
            g["forecast_eps_growth"] = fc[0].get("eps_growth")
            g["forecast_revenue_growth"] = fc[0].get("revenue_growth")

    return {"symbol": report.get("symbol"), "name": report.get("company_name"),
            "sector": ov.get("sector"), "sub_sector": ov.get("sub_sector"), "is_bank": is_bank,
            "annual_year": year, "ttm_as_of": ttm.get("as_of"), "price": price,
            "market_cap": ov.get("market_cap"), "flags": flags,
            "profitability": profitability, "financial_health": health, "growth": g, "valuation": v}


# ------------------------------------------------------------------ scoring
# (metric, good, bad, higher_is_better)   good=None -> displayed, not scored. Starting points: tune them.
RULES = {
    "profitability": [("roe", .15, .08, True), ("roa", .05, .02, True), ("roic", .12, .06, True),
                      ("net_profit_margin", .10, .03, True), ("fcf_margin", .08, 0, True),
                      ("net_interest_margin", .045, .03, True), ("cost_to_income", .50, .70, False)],
    "financial_health": [("debt_to_equity", .5, 1.5, False), ("debt_to_ebitda", 2, 4, False),
                         ("interest_coverage", 5, 2, True), ("current_ratio", 1.5, 1.0, True),
                         ("cash_to_debt", .5, .2, True), ("capital_adequacy_ratio", .20, .12, True),
                         ("npl_ratio", .03, .05, False), ("loan_to_deposit", None, None, True),
                         ("casa_ratio", None, None, True), ("liabilities_to_equity", None, None, False)],
    "growth": [("revenue_growth", .10, 0, True), ("eps_growth", .10, 0, True), ("fcf_growth", .10, 0, True),
               ("yoy_quarter_revenue_growth", .10, 0, True), ("yoy_quarter_earnings_growth", .10, 0, True),
               ("forecast_eps_growth", None, None, True), ("forecast_revenue_growth", None, None, True)],
    "valuation": [("pe", 12, 25, False), ("pb", 1.5, 3, False), ("ev_to_ebitda", 8, 15, False),
                  ("ev_to_revenue", 2, 5, False), ("intrinsic_upside", None, None, True),
                  ("forward_pe", None, None, False)],
}
WEIGHTS = {"profitability": .30, "financial_health": .25, "growth": .25, "valuation": .20}
POINTS = {"good": 1.0, "ok": 0.5, "bad": 0.0}


def score(m):
    pillars, scored, applicable = {}, 0, 0
    for pillar, rules in RULES.items():
        metrics, pts = {}, []
        for name, good, bad, hi in rules:
            if name not in m[pillar]:
                continue                                  # doesn't apply to this company
            val = m[pillar][name]
            if val is None:
                status = "na"
            elif good is None:
                status = "info"
            elif hi:
                status = "good" if val >= good else "bad" if val < bad else "ok"
            else:
                status = "good" if val <= good else "bad" if val > bad else "ok"
            metrics[name] = {"value": val, "status": status}
            if good is not None:
                applicable += 1
                if status in POINTS:
                    pts.append(POINTS[status]); scored += 1
        pillars[pillar] = {"score": round(100 * sum(pts) / len(pts)) if pts else None, "metrics": metrics}

    avail = {p: WEIGHTS[p] for p, d in pillars.items() if d["score"] is not None}
    total = sum(avail.values())
    overall = round(sum(pillars[p]["score"] * w for p, w in avail.items()) / total) if total else None
    return {"fundamental_score": overall,
            "pillar_scores": {p: d["score"] for p, d in pillars.items()},
            "data_coverage": round(scored / applicable, 2) if applicable else 0,
            "pillars": pillars}


def analyze(report, quarters, extras=False):
    """Main entry point: raw API data in, full fundamental result out."""
    m = compute_metrics(report, quarters, extras)
    head = {k: m[k] for k in ("symbol", "name", "sector", "sub_sector", "is_bank",
                              "annual_year", "ttm_as_of", "price", "market_cap", "flags")}
    return {**head, **score(m)}