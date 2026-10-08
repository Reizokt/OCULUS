import json
from datetime import date, datetime

from .config import CACHE_DIR, DEFAULT_LANGUAGE
from .llm import complete
from .retrieve import retrieve
from .schemas import NarrativeLLMOutput, NarrativeSummary

PROMPT = """You are an equity analyst for Indonesian (IDX) stocks.
Use ONLY the context below. Return ONLY valid JSON that matches this schema (no markdown, no comments):

SCHEMA_HERE

The context has five layers, each split into topics with a HOW TO WRITE THIS instruction:
technical (forecast ranges, volatility, trend, structure, volume), narrative (sentiment, insider, upcoming events),
fundamentals, sector (SUB-SECTOR level, not the ticker), broker (market-wide ranking and the foreign flow of the
ticker's SUB-SECTOR). Respect those scopes: never present sub-sector or market-wide data as the ticker's own.

paragraph_data: State the main readings of each available layer as actual versus reference where the data gives
a reference (previous period, history, sector level, threshold, longer window). Say whether each is above, below
or in line, then one sentence on what the combined picture shows.

paragraph_implication: State what this implies for the stock, which layers agree or conflict, and the likely price
behaviour inside the forecast ranges. The ranges are volatility based, so do not present them as a directional call.
End with what would change the view.

Rules:
- Every number must come from the context. If a value or reference is missing, say it is not available.
- price_ranges: copy range_68pct and range_95pct (and other horizons if shown). In each pair the lower value is
  low and the higher value is high. last_close comes from the forecast block.
- bull_levels and bear_levels: exact levels or conditions from the context (range edges, support, resistance).
- catalysts: dated upcoming events and recent insider activity, only if present.
- caveats: every fundamentals flag, every narrative flag, every data_notes item, and any layer that has no data.
- signals: one entry per important reading with layer, name, actual, reference, reading and meaning.
- Write paragraph_data, paragraph_implication, meaning and the text in lists in LANGUAGE_HERE.
  Keep JSON keys and enum values in English.

TICKER: TICKER_HERE

CONTEXT:
CONTEXT_HERE
"""


def _format_context(grouped: dict) -> str:
    parts = []
    for topic, d in grouped.items():
        body = "\n\n".join(d["chunks"]) if d["chunks"] else "(no data)"
        parts.append(f"## {topic.upper()}\nHOW TO WRITE THIS: {d['frame']}\n\n{body}")
    return "\n\n".join(parts)


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()


def _build_prompt(ticker: str, language: str, context: str) -> str:
    schema = json.dumps(NarrativeLLMOutput.model_json_schema(), indent=1)
    return (
        PROMPT.replace("SCHEMA_HERE", schema)
        .replace("LANGUAGE_HERE", language)
        .replace("TICKER_HERE", ticker)
        .replace("CONTEXT_HERE", context)
    )


def summarize(
    ticker: str,
    language: str = DEFAULT_LANGUAGE,
    topics: list[str] | None = None,
    refresh: bool = False,
) -> NarrativeSummary:
    """
    Retrieve -> prompt Gemini -> validated NarrativeSummary.
    Cached per ticker + language + day (saves free-tier calls). refresh=True forces a new call.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"narrative_{ticker}_{language}_{date.today().isoformat()}.json"
    if cache_file.exists() and not refresh and not topics:
        return NarrativeSummary.model_validate_json(cache_file.read_text(encoding="utf-8"))

    grouped = retrieve(ticker, topics=topics)
    if not any(d["chunks"] for d in grouped.values()):
        raise RuntimeError(f"No chunks found for {ticker}. Run ingest() first.")

    prompt = _build_prompt(ticker, language, _format_context(grouped))

    parsed = None
    error = ""
    for _ in range(2):  # one retry if the JSON is malformed
        raw = complete(prompt + (f"\n\nYour previous answer was invalid ({error}). Return valid JSON only." if error else ""))
        try:
            parsed = NarrativeLLMOutput.model_validate_json(_clean_json(raw))
            break
        except Exception as e:  # noqa: BLE001
            error = str(e)[:300]
    if parsed is None:
        raise RuntimeError(f"Gemini returned invalid JSON twice: {error}")

    summary = NarrativeSummary(
        **parsed.model_dump(),
        ticker=ticker,
        sources=[i for d in grouped.values() for i in d["ids"]],
        generated_at=datetime.now().isoformat(timespec="seconds"),
    )
    if not topics:
        cache_file.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    return summary