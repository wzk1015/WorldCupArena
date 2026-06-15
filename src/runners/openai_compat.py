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

    def __init__(self, model_cfg: dict[str, Any]):
        super().__init__(model_cfg)
        tools = model_cfg.get("tools") or []
        self.use_search = "web_search" in tools or "google_search" in tools
        self.use_reasoning = bool(
            model_cfg.get("reasoning_effort")
            or (model_cfg.get("provider") == "openai" and model_cfg.get("model", "").startswith("gpt-5"))
        )

    def _is_official_openai_api(self) -> bool:
        url = self.base_url() or ""
        return self.cfg.get("provider") == "openai" and "api.openai.com" in url

    def _client(self) -> OpenAI:
        kwargs: dict[str, Any] = {
            "api_key": self.api_key(),
            "base_url": self.base_url(),
        }
        if self.cfg.get("timeout_seconds"):
            kwargs["timeout"] = float(self.cfg["timeout_seconds"])
        headers = dict(self.cfg.get("default_headers") or {})
        if self.cfg.get("provider") == "openrouter":
            headers.setdefault("HTTP-Referer", "https://github.com/wzk1015/WorldCupArena")
            headers.setdefault("X-Title", "WorldCupArena")
        if headers:
            kwargs["default_headers"] = headers
        return OpenAI(**kwargs)

    def _cost_payload(self, input_tokens: int, output_tokens: int, tool_calls: int = 0) -> dict[str, Any]:
        cost = self.price_tokens(input_tokens, output_tokens)
        cost += tool_calls * float(self.cfg.get("price_per_tool_call", 0))
        return {"cost_usd": cost}

    def generate(self, system_prompt: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        if self._is_official_openai_api() and (self.use_reasoning or self.use_search):
            return self._generate_responses(system_prompt, messages)
        return self._generate_chat_completions(system_prompt, messages)

    def _generate_chat_completions(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        client = self._client()

        kwargs: dict[str, Any] = {
            "model": self.cfg["model"],
            "messages": [{"role": "system", "content": system_prompt}, *messages],
        }
        if not self.cfg.get("omit_temperature"):
            kwargs["temperature"] = self.cfg.get("temperature", 0.3)
        if self.cfg.get("json_mode", True):
            kwargs["response_format"] = {"type": "json_object"}
        if "gpt" in self.cfg["model"]:
            kwargs["max_completion_tokens"] = self.cfg.get("max_tokens", 32000)
            if self.use_reasoning:
                kwargs["reasoning_effort"] = self.cfg.get("reasoning_effort", "low")
        else:
            # max_tokens is universally supported across all OpenAI-compat providers
            # (Zhipu, Moonshot, DashScope, xAI, etc.); max_completion_tokens is OpenAI-only
            kwargs["max_tokens"] = self.cfg.get("max_tokens", 32000)
        if self.use_search:
            kwargs["web_search_options"] = self.cfg.get("web_search_options", {})
        if self.cfg.get("extra_body"):
            kwargs["extra_body"] = self.cfg["extra_body"]
        if self.cfg.get("stream"):
            kwargs["stream"] = True
            kwargs["stream_options"] = {"include_usage": True}

        resp = client.chat.completions.create(**kwargs)
        if self.cfg.get("stream"):
            text_parts: list[str] = []
            usage = None
            for chunk in resp:
                if getattr(chunk, "usage", None):
                    usage = chunk.usage
                for choice in chunk.choices or []:
                    delta = getattr(choice, "delta", None)
                    content = getattr(delta, "content", None)
                    if content:
                        text_parts.append(content)
            return {
                "text": "".join(text_parts),
                "thinking": None,
                "input_tokens": usage.prompt_tokens if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0,
                "tool_calls": 0,
                "sources": [],
                **self._cost_payload(
                    usage.prompt_tokens if usage else 0,
                    usage.completion_tokens if usage else 0,
                    int(self.cfg.get("assumed_tool_calls", 0)),
                ),
            }
        message = resp.choices[0].message
        text = message.content or ""
        thinking = getattr(message, "reasoning", None) or getattr(message, "reasoning_content", None)
        sources: list[dict[str, Any]] = []
        for ann in getattr(message, "annotations", None) or []:
            if getattr(ann, "type", None) == "url_citation":
                self._append_source(
                    sources,
                    {
                        "url": getattr(ann, "url", None),
                        "accessed_at": self.now_iso(),
                        "title": getattr(ann, "title", None),
                    },
                )
        usage = resp.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        tool_calls = int(self.cfg.get("assumed_tool_calls", 0))
        return {
            "text": text,
            "thinking": thinking,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "tool_calls": tool_calls,
            "sources": sources,
            **self._cost_payload(input_tokens, output_tokens, tool_calls),
        }

    def _generate_responses(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        client = self._client()
        kwargs: dict[str, Any] = {
            "model": self.cfg["model"],
            "instructions": system_prompt,
            "input": messages,
            "max_output_tokens": self.cfg.get("max_tokens", 32000),
        }
        if not self.use_search:
            kwargs["text"] = {"format": {"type": "json_object"}}
        if self.use_reasoning:
            kwargs["reasoning"] = {
                "effort": self.cfg.get("reasoning_effort", "low"),
                "summary": self.cfg.get("reasoning_summary", "auto"),
            }
        if self.use_search:
            kwargs["tools"] = [{"type": "web_search"}]
            kwargs["tool_choice"] = "auto"
            kwargs["include"] = ["web_search_call.action.sources"]

        resp = client.responses.create(**kwargs)

        text = getattr(resp, "output_text", None) or ""
        thinking_parts: list[str] = []
        sources: list[dict[str, Any]] = []
        tool_calls = 0

        for item in resp.output or []:
            item_type = getattr(item, "type", None)
            if item_type == "reasoning":
                for summary in getattr(item, "summary", None) or []:
                    summary_text = getattr(summary, "text", None)
                    if summary_text:
                        thinking_parts.append(summary_text)
            elif item_type == "web_search_call":
                tool_calls += 1
                action = getattr(item, "action", None)
                for source in getattr(action, "sources", None) or []:
                    url = getattr(source, "url", None)
                    if url:
                        self._append_source(sources, {"url": url, "accessed_at": self.now_iso()})
                url = getattr(action, "url", None)
                if url:
                    self._append_source(sources, {"url": url, "accessed_at": self.now_iso()})
            elif item_type == "message":
                for content in getattr(item, "content", None) or []:
                    if not text and getattr(content, "text", None):
                        text += content.text
                    for ann in getattr(content, "annotations", None) or []:
                        if getattr(ann, "type", None) == "url_citation":
                            self._append_source(
                                sources,
                                {
                                    "url": getattr(ann, "url", None),
                                    "accessed_at": self.now_iso(),
                                    "title": getattr(ann, "title", None),
                                },
                            )

        usage = resp.usage
        return {
            "text": text,
            "thinking": "\n\n".join(thinking_parts) or None,
            "input_tokens": usage.input_tokens if usage else 0,
            "output_tokens": usage.output_tokens if usage else 0,
            "tool_calls": tool_calls,
            "sources": sources,
        }

    @staticmethod
    def _append_source(sources: list[dict[str, Any]], source: dict[str, Any]) -> None:
        if not source.get("url"):
            return
        if all(existing.get("url") != source["url"] for existing in sources):
            sources.append(source)
