# Broker_Analysis.py
import numpy as np
import pandas as pd


def rank_brokers(top, registry):
    """top: /brokers/top/ results as DataFrame. registry: /brokers/ as DataFrame."""
    reg = registry.rename(columns={"code": "broker_code"})
    df = top.merge(reg[["broker_code", "name", "is_foreign", "cohort"]],
                   on="broker_code", how="left")
    df["foreign_share"] = (df["foreign_gross"] / df["gross"]).round(3)
    for c in ("net", "foreign_net", "gross", "foreign_gross"):
        df[c + "_bn"] = (df[c] / 1e9).round(1)
    df["direction"] = np.select(
    [df["foreign_net"] > 0, df["foreign_net"] < 0],
    ["INFLOW", "OUTFLOW"],
    default="NONE",
)
    return df


def cohort_summary(df):
    cols = ["gross_bn", "net_bn", "foreign_gross_bn", "foreign_net_bn"]
    d = df.assign(gross_bn=df["gross"] / 1e9, net_bn=df["net"] / 1e9,
                  foreign_gross_bn=df["foreign_gross"] / 1e9,
                  foreign_net_bn=df["foreign_net"] / 1e9)
    return d.groupby(["is_foreign", "cohort"], dropna=False)[cols].sum().round(1)


def foreign_flow_by_subsector(ff, companies):
    """ff: /foreign-flow/ rows. companies: your load_companies() frame."""
    m = ff.merge(companies[["symbol", "sub_sector", "market_cap"]],
                 on="symbol", how="inner")
    m["foreign_turnover"] = m["foreign_buy_idr"] + m["foreign_sell_idr"]
    g = m.groupby("sub_sector").agg(
        tickers=("symbol", "count"),
        net_foreign_bn=("net_foreign_inflow", lambda x: x.sum() / 1e9),
        foreign_turnover_bn=("foreign_turnover", lambda x: x.sum() / 1e9),
        pct_net_buy=("net_foreign_inflow", lambda x: (x > 0).mean() * 100),
        mcap=("market_cap", "sum"),
    )
    g["net_pct_turnover"] = g["net_foreign_bn"] / g["foreign_turnover_bn"] * 100
    g["net_bps_mcap"] = g["net_foreign_bn"] * 1e9 / g["mcap"] * 1e4
    return g.drop(columns="mcap").sort_values("net_pct_turnover", ascending=False)