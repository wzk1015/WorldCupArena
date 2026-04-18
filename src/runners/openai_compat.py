"""Runner for any OpenAI-compatible chat-completions endpoint.

Works for: OpenAI, DeepSeek, Together, Fireworks, DashScope-compat, vLLM, xAI Grok,
Perplexity Sonar, any OpenAI-protocol 中转/proxy. Set `base_url` + `api_key_env`
in models.yaml per entry.
"""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from .base import BaseRunner


class OpenAICompatRunner(BaseRunner):
    category = "closed_llm"  # overridden at runtime for open_llm / search_llm / agents

    def _client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key(), base_url=self.base_url())

    def generate(self, system_prompt: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        client = self._client()
        resp = client.chat.completions.create(
            model=self.cfg["model"],
            messages=[{"role": "system", "content": system_prompt}, *messages],
            response_format={"type": "json_object"},
            temperature=self.cfg.get("temperature", 0.3),
            max_tokens=self.cfg.get("max_tokens", 8192),
        )
        text = resp.choices[0].message.content or ""
        usage = resp.usage
        return {
            "text": text,
            "thinking": None,
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
            "tool_calls": 0,
            "sources": [],
        }
