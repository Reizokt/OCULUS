from typing import Literal, Optional

from pydantic import BaseModel, Field

Layer = Literal["technical", "narrative", "fundamentals", "sector", "broker"]


class Signal(BaseModel):
    layer: Layer
    name: str                                   # "insider bias", "sigma_ewma_pct", "pe_vs_hist", "net_foreign_bn"
    actual: str                                 # value as found in the context
    reference: Optional[str] = None             # prior period, sector level, history, threshold (if the data has one)
    reading: Literal["above", "below", "in_line", "unknown"] = "unknown"
    meaning: str                                # one-line interpretation


class PriceRange(BaseModel):
    """Copied from the forecast block (range_68pct / range_95pct). Low is the bear level, high is the bull level."""
    horizon_bars: Optional[int] = None
    confidence: Literal["68%", "95%"]
    low: float
    high: float


class NarrativeLLMOutput(BaseModel):
    """What the LLM must return (this schema is shown to the model)."""
    stance: Literal["bullish", "bearish", "neutral", "mixed"]
    signals: list[Signal]
    last_close: Optional[float] = None
    price_ranges: list[PriceRange] = Field(default_factory=list)
    paragraph_data: str                         # para 1: what each layer says (actual vs reference)
    paragraph_implication: str                  # para 2: implication, agreement/conflict between layers, what changes the view
    bull_levels: list[str] = Field(default_factory=list)
    bear_levels: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)   # dated upcoming events, insider activity, etc.
    caveats: list[str] = Field(default_factory=list)     # fundamentals flags, data_notes, narrative flags, missing layers


class NarrativeSummary(NarrativeLLMOutput):
    """Final object returned to the rest of the backend."""
    ticker: str
    sources: list[str] = Field(default_factory=list)    # chunk ids filled by code, not by the LLM
    generated_at: str = ""