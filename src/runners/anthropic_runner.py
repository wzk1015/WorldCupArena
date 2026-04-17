"""Runner for Anthropic Claude (plain LLM and with web_search tool)."""

from __future__ import annotations

import os
import time
from typing import Any

import anthropic

from .base import BaseRunner, RunnerResult


class AnthropicRunner(BaseRunner):
    category = "closed_llm"

    def __init__(self, model_cfg: dict[str, Any]):
        super().__init__(model_cfg)
        self.use_search = "web_search" in (model_cfg.get("tools") or [])
        self.use_thinking = "extended_thinking" in (model_cfg.get("tools") or [])

    def run(
        self,
        fixture: dict[str, Any],
        setting: dict[str, Any],
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> RunnerResult:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        tools: list[dict[str, Any]] = []
        if self.use_search:
            tools.append({"type": "web_search_20250305", "name": "web_search"})

        kwargs: dict[str, Any] = {
            "model": self.cfg["model"],
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": self.cfg.get("max_tokens", 8192),
            "temperature": self.cfg.get("temperature", 0.3),
        }
        if tools:
            kwargs["tools"] = tools
        if self.use_thinking:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": 4096}

        t0 = time.time()
        raw, pred, thinking, itoks, otoks, tool_calls, err = "", {}, None, 0, 0, 0, None
        sources: list[dict[str, Any]] = []

        try:
            resp = client.messages.create(**kwargs)
            for block in resp.content:
                btype = getattr(block, "type", None)
                if btype == "text":
                    raw += block.text
                elif btype == "thinking":
                    thinking = (thinking or "") + block.thinking
                elif btype == "tool_use":
                    tool_calls += 1
                elif btype == "web_search_tool_result":
                    for r in getattr(block, "content", []) or []:
                        if hasattr(r, "url"):
                            sources.append({"url": r.url, "accessed_at": self.now_iso(),
                                            "title": getattr(r, "title", None)})
            pred = self.parse_json(raw) if raw else {}
            itoks = resp.usage.input_tokens
            otoks = resp.usage.output_tokens
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
            input_tokens=itoks,
            output_tokens=otoks,
            tool_calls=tool_calls,
            cost_usd=self.price_tokens(itoks, otoks),
            wall_seconds=time.time() - t0,
            error=err,
        )
