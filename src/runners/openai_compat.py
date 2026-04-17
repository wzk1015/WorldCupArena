"""Runner for any OpenAI-compatible chat-completions endpoint.

Works for: OpenAI, DeepSeek, Together, Fireworks, DashScope-compat, vLLM, etc.
Set `base_url` + `api_key_env` in models.yaml per entry.
"""

from __future__ import annotations

import os
import time
from typing import Any

from openai import OpenAI

from .base import BaseRunner, RunnerResult


class OpenAICompatRunner(BaseRunner):
    category = "closed_llm"  # default; override when used for open_llm too

    def _client(self) -> OpenAI:
        api_key_env = self.cfg.get("api_key_env", "OPENAI_API_KEY")
        base_url = self.cfg.get("base_url")
        return OpenAI(api_key=os.environ[api_key_env], base_url=base_url)

    def run(
        self,
        fixture: dict[str, Any],
        setting: dict[str, Any],
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> RunnerResult:
        client = self._client()
        model = self.cfg["model"]

        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=self.cfg.get("temperature", 0.3),
                max_tokens=self.cfg.get("max_tokens", 8192),
            )
            raw = resp.choices[0].message.content or ""
            pred = self.parse_json(raw)
            usage = resp.usage
            itoks = usage.prompt_tokens if usage else 0
            otoks = usage.completion_tokens if usage else 0
            err = None
        except Exception as e:  # noqa: BLE001
            raw, pred, itoks, otoks, err = "", {}, 0, 0, f"{type(e).__name__}: {e}"

        return RunnerResult(
            model_id=self.model_id,
            setting=setting["id"],
            fixture_id=fixture["fixture_id"],
            submitted_at=self.now_iso(),
            prediction=pred,
            raw_text=raw,
            thinking_text=None,
            sources=pred.get("sources", []) if isinstance(pred, dict) else [],
            input_tokens=itoks,
            output_tokens=otoks,
            tool_calls=0,
            cost_usd=self.price_tokens(itoks, otoks),
            wall_seconds=time.time() - t0,
            error=err,
        )
