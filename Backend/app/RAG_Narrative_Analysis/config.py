import os
from pathlib import Path

from dotenv import load_dotenv

# Backend/app/RAG/config.py -> parents[2] = Backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

# ---- Gemini (free tier) ----
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Tried in order. If the first name is not available for your key, the next one is used.
# Override in .env:  GEMINI_MODELS=gemini-3.5-flash,gemini-3.1-flash-lite
LLM_MODELS = [
    m.strip()
    for m in os.getenv("GEMINI_MODELS", "gemini-flash-latest,gemini-3.1-flash-lite").split(",")
    if m.strip()
]
LLM_TEMPERATURE = 0.2
LLM_MAX_RETRIES = 3          # for 429 / 5xx

# ---- Storage ----
VECTORDB_DIR = BACKEND_DIR / "data" / "vectordb"
CACHE_DIR = BACKEND_DIR / "data" / "cache"
COLLECTION = "analysis"

# ---- Chunking ----
CHUNK_CHARS = 1000
MAX_LIST_ITEMS = 30          # cap long lists (e.g. top-20 companies) when flattening

# ---- Output ----
DEFAULT_LANGUAGE = "Indonesian"