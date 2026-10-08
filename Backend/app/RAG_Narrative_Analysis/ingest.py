"""
Analysis dict -> plain python -> text lines -> one chunk group per top-level key -> Chroma.
Embeddings: Chroma's default local model (no API key). Each chunk carries metadata
{ticker, section, key}, so retrieval can filter by layer and by block (e.g. section=narrative, key=insider).
"""
import math
from datetime import date, datetime

import chromadb
import numpy as np
import pandas as pd

from .config import CHUNK_CHARS, COLLECTION, MAX_LIST_ITEMS, VECTORDB_DIR

_client = None


def get_collection():
    global _client
    if _client is None:
        VECTORDB_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(VECTORDB_DIR))
    return _client.get_or_create_collection(COLLECTION)


def to_plain(obj):
    """numpy / pandas / dates -> plain python. NaN and inf -> None. Floats -> 6 significant digits."""
    if obj is None or obj is pd.NaT:
        return None
    if isinstance(obj, dict):
        return {str(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, pd.DataFrame):
        df = obj if isinstance(obj.index, pd.RangeIndex) else obj.reset_index()
        return to_plain(df.to_dict("records"))
    if isinstance(obj, pd.Series):
        return to_plain(obj.to_dict())
    if isinstance(obj, np.ndarray):
        return [to_plain(v) for v in obj.tolist()]
    if isinstance(obj, (list, tuple, set)):
        return [to_plain(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, (datetime, date, pd.Timestamp)):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return float(f"{obj:.6g}")
    if isinstance(obj, (bool, int, str)):
        return obj
    return str(obj)


def flatten(obj, path: str) -> list[str]:
    """Nested value -> 'path.to.field: value' lines. Missing values show as n/a, empty containers as (empty)."""
    if obj is None:
        return [f"{path}: n/a"]
    if isinstance(obj, dict):
        if not obj:
            return [f"{path}: (empty)"]
        lines: list[str] = []
        for k, v in obj.items():
            lines += flatten(v, f"{path}.{k}")
        return lines
    if isinstance(obj, list):
        if not obj:
            return [f"{path}: (empty)"]
        items = obj[:MAX_LIST_ITEMS]
        if len(items) <= 6 and all(not isinstance(v, (dict, list)) and v is not None for v in items):
            sep = " | " if any(isinstance(v, str) for v in items) else ", "
            return [f"{path}: " + sep.join(str(v) for v in items)]
        lines = []
        for i, v in enumerate(items, 1):
            lines += flatten(v, f"{path}[{i}]")
        return lines
    return [f"{path}: {obj}"]


def split_lines(lines: list[str], size: int = CHUNK_CHARS) -> list[str]:
    """Group whole lines into chunks of roughly `size` characters (never cuts a line in half)."""
    chunks, current, length = [], [], 0
    for line in lines:
        if current and length + len(line) > size:
            chunks.append("\n".join(current))
            current, length = [], 0
        current.append(line)
        length += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def ingest(ticker: str, analysis: dict) -> dict[str, int]:
    """
    analysis = adapters.build_analysis(...) -> {"technical": {...}, "narrative": {...}, "fundamentals": {...},
                                                "sector": {...}, "broker": {...}}
    Missing / empty layers are skipped. Re-ingesting replaces ALL old chunks of that ticker.
    Returns {layer: number_of_chunks}.
    """
    col = get_collection()

    # Build every new chunk first, so a failure never leaves the ticker wiped.
    new: dict[str, tuple[list, list, list]] = {}
    for section, payload in (analysis or {}).items():
        payload = to_plain(payload)
        if not payload:
            continue
        if not isinstance(payload, dict):
            payload = {"data": payload}

        ids, docs, metas = [], [], []
        for key, value in payload.items():
            for i, chunk in enumerate(split_lines(flatten(value, key))):
                ids.append(f"{ticker}-{section}-{key}-{i}")
                docs.append(f"[{ticker} | {section} | {key}]\n{chunk}")
                metas.append({"ticker": ticker, "section": section, "key": key, "chunk": i})
        if ids:
            new[section] = (ids, docs, metas)

    if not new:
        raise RuntimeError(f"ingest({ticker}): analysis produced no chunks, keeping existing data")

    col.delete(where={"ticker": ticker})   # drop everything old for this ticker, incl. demo leftovers

    counts: dict[str, int] = {}
    for section, (ids, docs, metas) in new.items():
        col.upsert(ids=ids, documents=docs, metadatas=metas)
        counts[section] = len(ids)
    return counts