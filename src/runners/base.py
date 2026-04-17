"""Base runner interface for all model categories.

A Runner takes a (fixture, setting, prompt) and returns a raw prediction JSON + metadata.
The pipeline is responsible for validation, retries, and cost accounting.
"""

from __future__ import annotations

import abc
import dataclasses
import datetime as dt
import json
from typing import Any


@dataclasses.dataclass
class RunnerResult:
    model_id: str
    setting: str
    fixture_id: str
    submitted_at: str
    prediction: dict[str, Any]      # parsed JSON (may fail schema validation — caller checks)
    raw_text: str                   # original text response, for audit
    thinking_text: str | None
    sources: list[dict[str, Any]]
    input_tokens: int
    output_tokens: int
    tool_calls: int
    cost_usd: float
    wall_seconds: float
    error: str | None = None


class BaseRunner(abc.ABC):
    """One subclass per (provider, interaction mode)."""

    category: str  # closed_llm | open_llm | search_llm | deep_research_agent

    def __init__(self, model_cfg: dict[str, Any]):
        self.cfg = model_cfg
        self.model_id = model_cfg["id"]

    @abc.abstractmethod
    def run(
        self,
        fixture: dict[str, Any],
        setting: dict[str, Any],
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> RunnerResult: ...

    # ---- helpers ----

    @staticmethod
    def now_iso() -> str:
        return dt.datetime.now(dt.timezone.utc).isoformat()

    def price_tokens(self, input_tokens: int, output_tokens: int) -> float:
        p = self.cfg.get("price_per_mtok", {})
        return (input_tokens * p.get("input", 0) + output_tokens * p.get("output", 0)) / 1_000_000

    def parse_json(self, text: str) -> dict[str, Any]:
        """Best-effort extraction of the JSON object from the model's response."""
        text = text.strip()
        if text.startswith("```"):
            # strip code fence
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
            # close fence at end
            if "```" in text:
                text = text.split("```", 1)[0]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # fall back: locate the outermost { ... }
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start : end + 1])
            raise
