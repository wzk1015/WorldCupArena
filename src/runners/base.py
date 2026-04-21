"""Base runner interface for all model categories.

A Runner takes a (fixture, setting, prompt) and returns a raw prediction JSON + metadata.
The orchestrator layer wraps this with schema-and-semantic validation + format repair.
"""

from __future__ import annotations

import abc
import dataclasses
import datetime as dt
import json
import os
from typing import Any, Callable


@dataclasses.dataclass
class RunnerResult:
    model_id: str
    setting: str
    fixture_id: str
    submitted_at: str
    prediction: dict[str, Any]      # parsed JSON (may still need validation)
    raw_text: str                   # last response, for audit
    thinking_text: str | None
    sources: list[dict[str, Any]]
    input_tokens: int
    output_tokens: int
    tool_calls: int
    cost_usd: float
    wall_seconds: float
    repair_retries: int = 0
    validation_errors: list[str] | None = None
    error: str | None = None


class BaseRunner(abc.ABC):
    """One subclass per (provider, interaction mode).

    Concrete runners MUST honour:
      - `self.cfg.get("api_key_env")`  -> read API key from that env var.
      - `self.cfg.get("base_url_env")` -> read base URL override from that env var;
        if unset or empty, fall back to `self.cfg.get("base_url")` (the official
        default). This lets users point at a 中转/proxy via `.env` without editing
        models.yaml.
    """

    category: str  # closed_llm | open_llm | search_llm | deep_research_agent

    def __init__(self, model_cfg: dict[str, Any]):
        self.cfg = model_cfg
        self.model_id = model_cfg["id"]

    # ---- Required API ----

    @abc.abstractmethod
    def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Low-level call: one provider request.

        Returns a dict with keys:
            text (str)            : assistant response text
            thinking (str|None)   : thinking trace if any
            input_tokens (int)
            output_tokens (int)
            tool_calls (int)
            sources (list[dict])  : discovered via tool use (optional)
        """

    # ---- High-level orchestration ----

    def run(
        self,
        fixture: dict[str, Any],
        setting: dict[str, Any],
        system_prompt: str,
        user_prompt: str,
        validate_fn: Callable[[dict[str, Any], Callable[[str], dict[str, Any]]], tuple[dict[str, Any], Any, int]] | None = None,
    ) -> RunnerResult:
        import time
        t0 = time.time()

        # messages = [{"role": "user", "content": user_prompt}]
        totals = {"input_tokens": 0, "output_tokens": 0, "tool_calls": 0, "cost": 0.0}
        sources: list[dict[str, Any]] = []
        thinking = None
        err = None
        pred: dict[str, Any] = {}
        raw = ""
        repair_retries = 0
        validation_errors: list[str] | None = None

        def _call(usr_prompt: str) -> dict[str, Any]:
            """Used by validate_fn as the retry hook."""
            msgs = [{"role": "user", "content": usr_prompt}]
            out = self.generate(system_prompt, msgs)
            # import ipdb; ipdb.set_trace()
            totals["input_tokens"] += out.get("input_tokens", 0)
            totals["output_tokens"] += out.get("output_tokens", 0)
            totals["tool_calls"] += out.get("tool_calls", 0)
            totals["cost"] += self.price_tokens(out.get("input_tokens", 0), out.get("output_tokens", 0))
            nonlocal raw, thinking
            raw = out.get("text", "")
            if out.get("thinking"):
                thinking = (thinking or "") + out["thinking"]
            for s in out.get("sources", []) or []:
                if s not in sources:
                    sources.append(s)
            return self.parse_json(raw)

        try:
            pred = _call(user_prompt)
            if validate_fn is not None:
                pred, report, repair_retries = validate_fn(pred, _call)
                validation_errors = report.errors if hasattr(report, "errors") else None
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"

        # merge model-declared sources with observed tool sources
        model_sources = pred.get("sources", []) if isinstance(pred, dict) else []
        all_sources = sources + [s for s in model_sources if s not in sources]

        return RunnerResult(
            model_id=self.model_id,
            setting=setting["id"],
            fixture_id=fixture["fixture_id"],
            submitted_at=self.now_iso(),
            prediction=pred,
            raw_text=raw,
            thinking_text=thinking,
            sources=all_sources,
            input_tokens=totals["input_tokens"],
            output_tokens=totals["output_tokens"],
            tool_calls=totals["tool_calls"],
            cost_usd=totals["cost"],
            wall_seconds=time.time() - t0,
            repair_retries=repair_retries,
            validation_errors=validation_errors,
            error=err,
        )

    # ---- helpers ----

    @staticmethod
    def now_iso() -> str:
        return dt.datetime.now(dt.timezone.utc).isoformat()

    def api_key(self) -> str:
        env = self.cfg.get("api_key_env")
        if not env:
            raise RuntimeError(f"{self.model_id}: api_key_env not set in models.yaml")
        try:
            return os.environ[env]
        except KeyError as e:
            raise RuntimeError(f"{self.model_id}: env var {env} not set") from e

    def base_url(self) -> str | None:
        env = self.cfg.get("base_url_env")
        if env:
            override = os.environ.get(env)
            if override:
                return override
        return self.cfg.get("base_url") or None

    def price_tokens(self, input_tokens: int, output_tokens: int) -> float:
        p = self.cfg.get("price_per_mtok") or {}
        return (input_tokens * p.get("input", 0) + output_tokens * p.get("output", 0)) / 1_000_000

    def parse_json(self, text: str) -> dict[str, Any]:
        """Best-effort extraction of the JSON object from the model's response."""
        text = (text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
            if "```" in text:
                text = text.split("```", 1)[0]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start : end + 1])
            raise
