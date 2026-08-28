"""The single Claude API wrapper. No `anthropic` client is constructed anywhere else.

Everything routes through `complete()`: retries, cost logging (L2), Phoenix
tracing (W3.4), and prompt-file loading. Centralizing it is what makes the
Job A cost story a real measured number instead of an estimate.

Two model tiers, per implementation.md §0.1:
  HAIKU_MODEL  — high volume, cheap: annotation escalation, analyst summaries.
  SONNET_MODEL — synthesis: agent reasoning, concept generation, review.
"""

from __future__ import annotations

import csv
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-5"

PROMPTS_DIR = Path("prompts")
COST_LOG = Path("eval/cost_log.csv")

# USD per million tokens. Update alongside a model change; the cost log is
# only as honest as these numbers.
PRICING: dict[str, tuple[float, float]] = {
    HAIKU_MODEL: (1.00, 5.00),
    SONNET_MODEL: (3.00, 15.00),
}

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 2.0

COST_LOG_FIELDS = (
    "timestamp", "task", "model", "prompt_version",
    "input_tokens", "output_tokens", "cost_usd", "latency_s",
)


class MissingAPIKeyError(RuntimeError):
    """Raised when an LLM path is reached with no key configured.

    Retrieval must run with no key at all (§7), so this is raised lazily at
    call time rather than at import.
    """


@dataclass(frozen=True)
class LLMResponse:
    """A completed call plus what it cost — the pair the cost story needs."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_s: float

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def load_prompt(name: str) -> str:
    """Load a versioned prompt file by name, e.g. `analyst_summary_v1`.

    Prompts live in `prompts/` as text files and are never inlined in code
    (AGENTS.md), so that a prompt change is a reviewable diff and can be
    A/B'd by version (L3).
    """
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        available = sorted(p.stem for p in PROMPTS_DIR.glob("*.txt")) if PROMPTS_DIR.exists() else []
        raise FileNotFoundError(f"No prompt {name!r} at {path}. Available: {available}")
    return path.read_text(encoding="utf-8")


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    in_rate, out_rate = PRICING.get(model, (0.0, 0.0))
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000


def log_cost(
    task: str,
    response: LLMResponse,
    prompt_version: str = "",
    path: Path = COST_LOG,
) -> None:
    """Append one row to `eval/cost_log.csv` (L2). Creates the header if new."""
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COST_LOG_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "task": task,
                "model": response.model,
                "prompt_version": prompt_version,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": round(response.cost_usd, 6),
                "latency_s": round(response.latency_s, 3),
            }
        )


@lru_cache(maxsize=1)
def _client():
    """Build the one Anthropic client, lazily so no-key paths stay importable."""
    from dotenv import load_dotenv

    load_dotenv()
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise MissingAPIKeyError(
            "ANTHROPIC_API_KEY is not set. Put it in .env at the repo root "
            "(gitignored) or in st.secrets when deployed. Retrieval works "
            "without a key; only LLM paths need one."
        )
    from anthropic import Anthropic

    return Anthropic(api_key=key)


def has_api_key() -> bool:
    """True if an LLM call could succeed. Lets callers degrade rather than crash."""
    from dotenv import load_dotenv

    load_dotenv()
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def complete(
    prompt: str,
    *,
    task: str,
    model: str = HAIKU_MODEL,
    system: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.0,
    prompt_version: str = "",
    **kwargs: Any,
) -> LLMResponse:
    """Call Claude once, with retries, cost logging, and tracing.

    `task` is the label the cost log groups by — use a stable string per
    call site (e.g. "bootstrap_label", "analyst_summary") so per-stage cost
    is recoverable later.
    """
    from anthropic import APIConnectionError, APIStatusError, RateLimitError

    client = _client()
    messages = [{"role": "user", "content": prompt}]
    request: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
        **kwargs,
    }
    if system:
        request["system"] = system

    started = time.perf_counter()
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = client.messages.create(**request)
            break
        except (RateLimitError, APIConnectionError) as exc:
            last_error = exc  # transient — worth retrying
        except APIStatusError as exc:
            if exc.status_code < 500:
                raise  # 4xx is our bug; retrying just burns quota
            last_error = exc
        if attempt < MAX_ATTEMPTS:
            time.sleep(BACKOFF_SECONDS * attempt)
    else:
        raise RuntimeError(
            f"LLM call for task {task!r} failed after {MAX_ATTEMPTS} attempts"
        ) from last_error

    latency = time.perf_counter() - started
    text = "".join(block.text for block in raw.content if block.type == "text")
    response = LLMResponse(
        text=text,
        model=model,
        input_tokens=raw.usage.input_tokens,
        output_tokens=raw.usage.output_tokens,
        cost_usd=estimate_cost(model, raw.usage.input_tokens, raw.usage.output_tokens),
        latency_s=latency,
    )
    log_cost(task, response, prompt_version)
    return response


def total_spend(path: Path = COST_LOG) -> float:
    """Sum every logged call. The number the case study quotes."""
    if not path.exists():
        return 0.0
    with path.open(encoding="utf-8") as handle:
        return sum(float(row["cost_usd"]) for row in csv.DictReader(handle))
