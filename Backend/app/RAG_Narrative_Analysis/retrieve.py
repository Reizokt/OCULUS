from .ingest import get_collection
from .topics import TOPICS


def _where(ticker: str, cfg: dict) -> dict:
    conds = [{"ticker": ticker}, {"section": cfg["section"]}]
    if cfg.get("keys"):
        conds.append({"key": {"$in": cfg["keys"]}})
    if cfg.get("exclude_keys"):
        conds.append({"key": {"$nin": cfg["exclude_keys"]}})
    return {"$and": conds}


def retrieve(ticker: str, topics: list[str] | None = None, debug: bool = False) -> dict:
    """
    Returns {topic: {"frame": str, "chunks": [str], "ids": [str]}}.
    `topics` limits which topics run (e.g. ["forecast_ranges", "volatility"] for a forecast-only page).
    debug=True prints distances so you can tune queries (lower distance = closer match).
    """
    col = get_collection()
    out: dict = {}

    for name, cfg in TOPICS.items():
        if topics and name not in topics:
            continue

        where = _where(ticker, cfg)
        seen: set[str] = set()
        ids: list[str] = []
        chunks: list[str] = []

        for q in cfg["queries"]:
            res = col.query(
                query_texts=[q],
                n_results=cfg["k"],
                where=where,
                include=["documents", "distances"],
            )
            if debug:
                print(f"[{name}] {q!r} -> {[round(d, 3) for d in res['distances'][0]]}")
            for id_, doc in zip(res["ids"][0], res["documents"][0]):
                if id_ not in seen:
                    seen.add(id_)
                    ids.append(id_)
                    chunks.append(doc)

        out[name] = {"frame": cfg["frame"], "chunks": chunks, "ids": ids}

    return out