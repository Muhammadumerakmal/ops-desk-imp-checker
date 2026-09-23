"""Model provider configuration — FR-1, NFR-1, NFR-2.

The model is attached to each *agent* through an OpenAI-compatible client. It is
never set globally (the forbidden default-client setter — see constitution §1) and
never set per run.

Deliberate deviation from FR-1 (documented in constitution.md §1): the brief asks
for `gemini-2.5-flash` on Gemini's OpenAI-compatible endpoint, but the key we have is
a real OpenAI key. We keep the exact architecture and run `gpt-4o-mini` on OpenAI's
own endpoint. Returning to Gemini is the one-line change marked below.
"""

from __future__ import annotations

import os

from agents import AsyncOpenAI, ModelSettings, OpenAIChatCompletionsModel
from dotenv import load_dotenv

# Load .env once, on import. The key lives only here (NFR-1).
load_dotenv()

# The chat model id used across every agent. Attached per-agent, never globally.
MODEL_NAME = os.getenv("OPS_DESK_MODEL", "gpt-4o-mini")

# Base URL for the OpenAI-compatible endpoint.
#   OpenAI (current):  leave OPS_DESK_BASE_URL unset -> talks to api.openai.com
#   Gemini (per FR-1): set OPS_DESK_BASE_URL to
#       https://generativelanguage.googleapis.com/v1beta/openai/
#   and OPS_DESK_MODEL to gemini-2.5-flash. That is the whole swap.
BASE_URL = os.getenv("OPS_DESK_BASE_URL")  # None -> OpenAI default endpoint

# Turn ceiling for every run (FR-9c, NFR-2). Named here so it has one home.
MAX_TURNS = 8


def _require_key() -> str:
    """Return the API key or fail with a clear, single-sentence error (NFR-1)."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and paste your "
            "key before starting the Ops Desk."
        )
    return key


# One shared async client for the whole process. Built from the env key only.
_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    """Lazily build the single OpenAI-compatible async client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=_require_key(), base_url=BASE_URL)
    return _client


def make_model() -> OpenAIChatCompletionsModel:
    """A fresh model object bound to our client — set on an *agent*, not globally.

    FR-1 is satisfied because every agent receives one of these via `model=...`;
    the global default-client setter never appears anywhere in the codebase.
    """
    return OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=get_client())


def tracing_export_key() -> str:
    """Key used to export traces to the provider dashboard (FR-13, NFR-3).

    Falls back to the main key if a dedicated tracing key is not provided.
    """
    return os.getenv("TRACING_EXPORT_API_KEY") or _require_key()


# Default model settings so every agent declares its own ceiling-aware config
# (NFR-2). Individual agents override temperature to be cold or warm.
BASE_MODEL_SETTINGS = ModelSettings(temperature=0.3, max_tokens=600)
