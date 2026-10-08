"""
Turns the raw outputs of your analysis modules into the dicts that ingest() expects.
Rule: one top-level key = one chunk group = one retrievable topic.

  technical    : technical_analysis/forecast output (dict)
  narrative    : narrative_analysis output (dict)
  fundamentals : fundamentals analysis output (dict)
  sector       : SUB-SECTOR level (detail + top DataFrames from your sector scoring)
  broker       : market-wide brokers + foreign flow of the ticker's SUB-SECTOR
"""
from __future__ import annotations


def _group(d: dict, groups: dict[str, list[str]]) -> dict:
    """Collect scalar header keys under one key; every other key stays as it is."""
    out, used = {}, set()
    for new_key, keys in groups.items():
        sub = {k: d[k] for k in keys if k in d}
        if sub:
            out[new_key] = sub
            used.update(sub)
    for k, v in d.items():
        if k not in used:
            out[k] = v
    return out


# ---------------------------------------------------------------- per-ticker layers
def technical_payload(d: dict) -> dict:
    return _group(d, {
        "forecast": ["horizon_bars", "last_close", "bars_used", "range_68pct", "range_95pct", "all_horizons"],
    })  # other keys stay: volatility, trend, structure, volume, data_notes


def narrative_payload(d: dict) -> dict:
    return _group(d, {"meta": ["symbol", "window"]})
    # stays: sentiment, themes, insider, upcoming, flags, event_alignment, top_headlines


def fundamentals_payload(d: dict) -> dict:
    return _group(d, {
        "profile": ["symbol", "name", "sector", "sub_sector", "is_bank",
                    "annual_year", "ttm_as_of", "price", "market_cap"],
    })  # "flags" and every metric group stay as their own keys


# ---------------------------------------------------------------- sub-sector / market layers
def _by_sub_sector(df):
    if df is None or len(df) == 0:
        return None
    return df.set_index("sub_sector") if "sub_sector" in df.columns else df


def _pick(row: dict, keys: list[str]) -> dict:
    return {k: row[k] for k in keys if k in row}


def sector_payload(sub_sector: str, detail=None, top=None) -> dict:
    """
    detail: DataFrame from run_subsector_detail (columns: sector, companies, mcap_tn, chg_1w, ..., vol)
    top   : DataFrame from run_sector_scoring (sorted, one row per sub-sector, with the score columns)
    """
    detail, top = _by_sub_sector(detail), _by_sub_sector(top)

    row = {}
    if detail is not None and sub_sector in detail.index:
        row = detail.loc[sub_sector].to_dict()

    position = _pick(row, ["sector", "companies", "mcap_tn", "chg_1w", "chg_ytd", "chg_1y", "mom_3m"])
    position["sub_sector"] = sub_sector

    out = {
        "position": position,
        "valuation": _pick(row, ["pe", "pe_vs_hist", "pb", "eps_last", "eps_fwd", "rev_fwd"]),
        "stability": _pick(row, ["max_dd", "vol"]),
    }

    if top is not None and sub_sector in top.index:
        order = list(top.index)
        out["ranking"] = {
            "rank_in_top_table": order.index(sub_sector) + 1,
            "of": len(order),
            **top.loc[sub_sector].to_dict(),
        }
    return {k: v for k, v in out.items() if v}


def broker_payload(sub_sector: str, ranked=None, cohorts=None, foreign_sub=None, top_n: int = 8) -> dict:
    """
    ranked      : rank_brokers(...) DataFrame (market-wide)
    cohorts     : cohort_summary(...) DataFrame (market-wide)
    foreign_sub : foreign_flow_by_subsector(...) DataFrame, index = sub_sector, sorted by net_pct_turnover
    """
    out = {}

    if foreign_sub is not None and sub_sector in foreign_sub.index:
        order = list(foreign_sub.index)
        out["foreign_flow_subsector"] = {
            "sub_sector": sub_sector,
            **foreign_sub.loc[sub_sector].to_dict(),
            "rank_by_net_pct_turnover": order.index(sub_sector) + 1,
            "of_sub_sectors": len(order),
        }

    if ranked is not None and len(ranked):
        cols = [c for c in ["broker_code", "name", "is_foreign", "cohort", "net_bn",
                            "foreign_net_bn", "gross_bn", "foreign_share", "direction"] if c in ranked.columns]
        out["top_brokers"] = ranked[cols].head(top_n).to_dict("records")

    if cohorts is not None and len(cohorts):
        out["cohorts"] = cohorts.reset_index().to_dict("records")

    return out


def build_analysis(technical=None, narrative=None, fundamentals=None, sector=None, broker=None) -> dict:
    """sector / broker must already be built with sector_payload() / broker_payload()."""
    return {
        "technical": technical_payload(technical) if technical else None,
        "narrative": narrative_payload(narrative) if narrative else None,
        "fundamentals": fundamentals_payload(fundamentals) if fundamentals else None,
        "sector": sector or None,
        "broker": broker or None,
    }