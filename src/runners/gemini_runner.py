"""Runner for Google Gemini via the native Gen AI SDK."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, urlunparse

from google import genai
from google.genai import types

from .base import BaseRunner


class GeminiRunner(BaseRunner):
    category = "closed_llm"

    def __init__(self, model_cfg: dict[str, Any]):
        super().__init__(model_cfg)
        tools = model_cfg.get("tools") or []
        self.use_search = "google_search" in tools
        self.use_thinking = "thinking" in self.model_id or bool(
            model_cfg.get("thinking_level") or model_cfg.get("thinking_budget")
        )

    def _http_options(self) -> types.HttpOptions:
        url = self.base_url() or "https://generativelanguage.googleapis.com/v1beta"
        api_version = "v1beta"
        url = url.rstrip("/")
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        for version in ("/v1beta", "/v1", "/v1alpha"):
            if path.endswith(version):
                api_version = version.lstrip("/")
                path = path[: -len(version)]
                break

        is_official = parsed.netloc == "generativelanguage.googleapis.com"
        if is_official:
            return types.HttpOptions(api_version=api_version)

        base_url = urlunparse(parsed._replace(path=path or "", params="", query="", fragment=""))
        return types.HttpOptions(base_url=base_url, api_version=api_version)

    def _client(self) -> genai.Client:
        return genai.Client(api_key=self.api_key(), http_options=self._http_options())

    def _config(self, system_prompt: str) -> types.GenerateContentConfig:
        tools: list[types.Tool] = []
        if self.use_search:
            tools.append(types.Tool(google_search=types.GoogleSearch()))

        thinking_config = None
        if self.use_thinking:
            thinking_kwargs: dict[str, Any] = {
                "include_thoughts": self.cfg.get("include_thoughts", True)
            }
            if self.cfg.get("thinking_level"):
                thinking_kwargs["thinking_level"] = self.cfg["thinking_level"]
            elif self.cfg.get("thinking_budget") is not None:
                thinking_kwargs["thinking_budget"] = self.cfg["thinking_budget"]
            else:
                thinking_kwargs["thinking_level"] = "low"
            thinking_config = types.ThinkingConfig(**thinking_kwargs)

        return types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=self.cfg.get("temperature", 0.3),
            max_output_tokens=self.cfg.get("max_tokens", 8192),
            response_mime_type="application/json",
            tools=tools or None,
            thinking_config=thinking_config,
        )

    @staticmethod
    def _contents(messages: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for message in messages:
            content = message.get("content", "")
            if isinstance(content, str):
                parts.append(content)
            else:
                parts.append(str(content))
        return "\n\n".join(parts)

    def generate(self, system_prompt: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        client = self._client()
        resp = client.models.generate_content(
            model=self.cfg["model"],
            contents=self._contents(messages),
            config=self._config(system_prompt),
        )

        text_parts: list[str] = []
        thinking_parts: list[str] = []
        sources: list[dict[str, Any]] = []
        search_queries: set[str] = set()

        for candidate in resp.candidates or []:
            content = candidate.content
            for part in (content.parts if content and content.parts else []):
                if not part.text:
                    continue
                if part.thought:
                    thinking_parts.append(part.text)
                else:
                    text_parts.append(part.text)

            grounding = candidate.grounding_metadata
            if grounding:
                for query in grounding.web_search_queries or []:
                    search_queries.add(query)
                for chunk in grounding.grounding_chunks or []:
                    web = chunk.web
                    if web and web.uri:
                        source = {
                            "url": web.uri,
                            "accessed_at": self.now_iso(),
                            "title": web.title,
                        }
                        if source not in sources:
                            sources.append(source)

        text = "".join(text_parts) or (resp.text or "")
        thinking = "".join(thinking_parts) or None
        usage = resp.usage_metadata
        input_tokens = usage.prompt_token_count if usage else 0
        if usage and usage.total_token_count is not None and input_tokens is not None:
            output_tokens = max(0, usage.total_token_count - input_tokens)
        elif usage:
            output_tokens = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
        else:
            output_tokens = 0

        tool_calls = 0
        if self.use_search:
            tool_calls = len(search_queries) or (1 if sources else 0)

        return {
            "text": text,
            "thinking": thinking,
            "input_tokens": input_tokens or 0,
            "output_tokens": output_tokens or 0,
            "tool_calls": tool_calls,
            "sources": sources,
        }
