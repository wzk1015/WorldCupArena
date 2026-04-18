"""Runner for Anthropic Claude (plain LLM and with web_search / extended_thinking)."""

from __future__ import annotations

from typing import Any

import anthropic

from .base import BaseRunner


class AnthropicRunner(BaseRunner):
    category = "closed_llm"

    def __init__(self, model_cfg: dict[str, Any]):
        super().__init__(model_cfg)
        tools = model_cfg.get("tools") or []
        self.use_search = "web_search" in tools
        self.use_thinking = "extended_thinking" in tools

    def _client(self) -> anthropic.Anthropic:
        return anthropic.Anthropic(api_key=self.api_key(), base_url=self.base_url())

    def generate(self, system_prompt: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        client = self._client()

        tools: list[dict[str, Any]] = []
        if self.use_search:
            tools.append({"type": "web_search_20250305", "name": "web_search"})

        kwargs: dict[str, Any] = {
            "model": self.cfg["model"],
            "system": system_prompt,
            "messages": messages,
            "max_tokens": self.cfg.get("max_tokens", 8192),
            "temperature": self.cfg.get("temperature", 0.3),
        }
        if tools:
            kwargs["tools"] = tools
        if self.use_thinking:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": 4096}

        resp = client.messages.create(**kwargs)

        text = ""
        thinking = None
        tool_calls = 0
        sources: list[dict[str, Any]] = []
        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text += block.text
            elif btype == "thinking":
                thinking = (thinking or "") + block.thinking
            elif btype == "tool_use":
                tool_calls += 1
            elif btype == "web_search_tool_result":
                for r in getattr(block, "content", []) or []:
                    if hasattr(r, "url"):
                        sources.append({
                            "url": r.url,
                            "accessed_at": self.now_iso(),
                            "title": getattr(r, "title", None),
                        })

        return {
            "text": text,
            "thinking": thinking,
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "tool_calls": tool_calls,
            "sources": sources,
        }
