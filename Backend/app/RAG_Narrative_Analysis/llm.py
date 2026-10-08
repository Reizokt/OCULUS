"""Gemini free-tier wrapper. One function: complete(prompt) -> text."""
import time

from google import genai
from google.genai import types

from .config import GEMINI_API_KEY, LLM_MAX_RETRIES, LLM_MODELS, LLM_TEMPERATURE

_client = None


def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set. Put it in Backend/.env")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def complete(prompt: str, json_mode: bool = True) -> str:
    client = _get_client()
    cfg = types.GenerateContentConfig(
        temperature=LLM_TEMPERATURE,
        response_mime_type="application/json" if json_mode else None,
    )

    last_err = None
    for model in LLM_MODELS:
        for attempt in range(LLM_MAX_RETRIES):
            try:
                resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
                return resp.text
            except Exception as e:  # noqa: BLE001
                last_err = e
                code = getattr(e, "code", None)
                if code == 404:                      # model name not available -> try next model
                    break
                if code in (429, 500, 503) and attempt < LLM_MAX_RETRIES - 1:
                    time.sleep(5 * (2 ** attempt))   # 5s, 10s ...
                    continue
                if code in (429, 500, 503):          # retries used up -> try next model
                    break
                raise
    raise RuntimeError(f"All Gemini models failed. Last error: {last_err}")