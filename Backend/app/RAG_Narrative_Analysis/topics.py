"""
Retrieval plan, matched to the real output of each analysis module.

Each topic = layer (section) + optional block filter (keys / exclude_keys) + semantic queries + a 'frame'
(how the LLM should write about that group of chunks).

Queries use the actual field names (range_68pct, sigma_ewma_pct, net_value, pe_vs_hist ...) because
chunks are flattened to 'path.to.field: value' lines, so matching on field names works best.

Scope warning: sector = SUB-SECTOR level, broker = market-wide ranking + the ticker's SUB-SECTOR foreign flow.
The frames tell the LLM not to attribute those to the ticker itself.
"""

TOPICS = {
    # ------------------------------------------------------------ technical (forecast module)
    "forecast_ranges": {
        "section": "technical", "keys": ["forecast", "data_notes"], "k": 3,
        "queries": [
            "range_68pct range_95pct price range horizon",
            "last_close bars_used horizon_bars",
            "all_horizons range_68 range_95",
            "data_notes",
        ],
        "frame": "Report last_close and the 68% and 95% price ranges for the stated horizon (in bars). "
                 "In each range the lower value is the bear level and the higher value is the bull level. "
                 "These ranges are volatility based, not a directional call; say so. Mention data_notes if any.",
    },
    "volatility": {
        "section": "technical", "keys": ["volatility"], "k": 3,
        "queries": [
            "volatility state sigma_ewma_pct",
            "outlier_in_window method",
        ],
        "frame": "State the volatility regime (state) and sigma_ewma_pct, and whether an outlier sits in the window, "
                 "because an outlier can distort the ranges.",
    },
    "trend": {
        "section": "technical", "keys": ["trend"], "k": 3,
        "queries": [
            "trend window direction slope",
            "market trend close short window long window",
        ],
        "frame": "Compare the trend across the windows (short versus long). Say whether they agree or conflict, "
                 "using exactly the fields shown.",
    },
    "structure_volume": {
        "section": "technical", "keys": ["structure", "volume"], "k": 3,
        "queries": [
            "price action structure support resistance swing high low",
            "volume analysis open close volume",
        ],
        "frame": "Give structure levels (support, resistance, swings) exactly as shown, and say whether volume "
                 "confirms or contradicts the price move.",
    },

    # ------------------------------------------------------------ narrative
    "narrative_sentiment": {
        "section": "narrative", "keys": ["sentiment", "themes", "top_headlines", "meta"], "k": 3,
        "queries": [
            "sentiment label score n_articles",
            "themes",
            "top_headlines",
        ],
        "frame": "Give the sentiment label, score and number of articles (a small n_articles means a weak signal). "
                 "Name the main themes and at most two headlines.",
    },
    "narrative_insider": {
        "section": "narrative", "keys": ["insider"], "k": 3,
        "queries": [
            "insider net_value bias Accumulation Distribution",
            "insider transactions last_transaction days_since_last recent",
        ],
        "frame": "State the insider bias, net_value, number of transactions and how recent it is "
                 "(days_since_last, recent). If recent is false or there are no filings, say the insider signal "
                 "is weak or absent.",
    },
    "narrative_events": {
        "section": "narrative", "keys": ["upcoming", "flags", "event_alignment"], "k": 3,
        "queries": [
            "upcoming date type title",
            "flags",
            "event_alignment",
        ],
        "frame": "List upcoming dated events as catalysts, and any narrative flags (put flags in caveats). "
                 "Say what event_alignment shows about whether news and events point the same way.",
    },

    # ------------------------------------------------------------ fundamentals
    "fundamentals_profile": {
        "section": "fundamentals", "keys": ["profile", "flags"], "k": 3,
        "queries": [
            "profile symbol sector sub_sector is_bank annual_year ttm_as_of price market_cap",
            "flags",
        ],
        "frame": "State whether it is a bank (is_bank), the annual_year and ttm_as_of period, and the market cap. "
                 "Copy every flag: flags are data-quality or risk warnings and belong in caveats.",
    },
    "fundamentals_metrics": {
        "section": "fundamentals", "exclude_keys": ["profile", "flags"], "k": 3,
        "queries": [
            "score rating overall",
            "profitability roe roa margin",
            "growth revenue earnings",
            "valuation pe pbv",
            "financial risk leverage npl car ldr",
            "data coverage ttm",
        ],
        "frame": "Give each metric with its value and any reference found in the data (sector, prior period, threshold). "
                 "Banks are scored with bank-specific metrics. Only call something a weakness if a number supports it.",
    },

    # ------------------------------------------------------------ sector (SUB-SECTOR level)
    "sector_position": {
        "section": "sector", "keys": ["position", "ranking"], "k": 3,
        "queries": [
            "position sector sub_sector companies mcap_tn chg_1w chg_ytd chg_1y mom_3m",
            "ranking rank_in_top_table score",
        ],
        "frame": "This block describes the ticker's SUB-SECTOR, not the ticker. State its rank among the scored "
                 "sub-sectors and its performance (chg_1w, chg_ytd, chg_1y, mom_3m) as given.",
    },
    "sector_valuation": {
        "section": "sector", "keys": ["valuation", "stability"], "k": 3,
        "queries": [
            "valuation pe pe_vs_hist pb",
            "eps_last eps_fwd rev_fwd growth",
            "stability max_dd vol",
        ],
        "frame": "Sub-sector level. Compare pe with pe_vs_hist (valuation against its own history), then pb, "
                 "last and forward eps / revenue growth, and max_dd and vol as stability. Use the values as given.",
    },

    # ------------------------------------------------------------ broker
    "broker_foreign_flow": {
        "section": "broker", "keys": ["foreign_flow_subsector"], "k": 3,
        "queries": [
            "foreign_flow_subsector net_foreign_bn foreign_turnover_bn",
            "pct_net_buy net_pct_turnover net_bps_mcap rank_by_net_pct_turnover",
        ],
        "frame": "Foreign flow of the ticker's SUB-SECTOR (not ticker specific): net_foreign_bn in billion IDR, "
                 "net_pct_turnover, pct_net_buy (share of tickers with net foreign buying) and its rank among "
                 "sub-sectors.",
    },
    "broker_players": {
        "section": "broker", "keys": ["top_brokers", "cohorts"], "k": 3,
        "queries": [
            "top_brokers broker_code name net_bn foreign_net_bn direction",
            "cohorts is_foreign cohort gross_bn net_bn",
        ],
        "frame": "Market-wide broker ranking and cohort totals, NOT specific to this ticker. "
             "direction (INFLOW or OUTFLOW) describes FOREIGN flow only, so ignore it for brokers with "
             "is_foreign False and use net_bn instead. "
             "Never claim a broker traded this ticker.",
    },
}