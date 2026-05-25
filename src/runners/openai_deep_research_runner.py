"""Runner for OpenAI Deep Research models via the Responses API."""

from __future__ import annotations

import time
from typing import Any

from openai import OpenAI

from .base import BaseRunner


class OpenAIDeepResearchRunner(BaseRunner):
    category = "deep_research_agent"

    def _client(self) -> OpenAI:
        return OpenAI(
            api_key=self.api_key(),
            base_url=self.base_url(),
            timeout=float(self.cfg.get("timeout_seconds", 120)),
        )

    def generate(self, system_prompt: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        client = self._client()
        user_text = self._contents(messages)
        user_text = (
            f"{user_text}\n\n"
            "After completing the research, return the final forecast as one valid JSON object "
            "that matches the supplied schema. Do not wrap the JSON in Markdown."
        )

        kwargs: dict[str, Any] = {
            "model": self.cfg["model"],
            "instructions": system_prompt,
            "input": user_text,
            "background": self.cfg.get("background", True),
            "max_output_tokens": self.cfg.get("max_tokens", 20000),
            "tools": [{"type": self.cfg.get("web_search_tool", "web_search_preview")}],
        }
        if self.cfg.get("reasoning_summary"):
            kwargs["reasoning"] = {"summary": self.cfg["reasoning_summary"]}
        if self.cfg.get("include_sources", True):
            kwargs["include"] = ["web_search_call.action.sources"]
        if self.cfg.get("timeout_seconds"):
            kwargs["timeout"] = float(self.cfg["timeout_seconds"])

        resp = client.responses.create(**kwargs)
        resp = self._poll_until_done(client, resp)
        return self._extract_response(resp)

    @staticmethod
    def _contents(messages: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for message in messages:
            content = message.get("content", "")
            parts.append(content if isinstance(content, str) else str(content))
        return "\n\n".join(parts)

    def _poll_until_done(self, client: OpenAI, resp: Any) -> Any:
        max_wait_seconds = int(self.cfg.get("max_wait_seconds", 1200))
        poll_seconds = float(self.cfg.get("poll_seconds", 10))
        started = time.time()

        while getattr(resp, "status", None) in {"queued", "in_progress"}:
            if time.time() - started > max_wait_seconds:
                raise TimeoutError(
                    f"{self.model_id}: deep research still {resp.status!r} after {max_wait_seconds}s"
                )
            time.sleep(poll_seconds)
            retrieve_kwargs: dict[str, Any] = {}
            if self.cfg.get("include_sources", True):
                retrieve_kwargs["include"] = ["web_search_call.action.sources"]
            if self.cfg.get("timeout_seconds"):
                retrieve_kwargs["timeout"] = float(self.cfg["timeout_seconds"])
            resp = client.responses.retrieve(resp.id, **retrieve_kwargs)

        status = getattr(resp, "status", None)
        if status and status not in {"completed"}:
            details = getattr(resp, "error", None) or getattr(resp, "incomplete_details", None)
            raise RuntimeError(f"{self.model_id}: deep research status={status!r}, details={details!r}")
        return resp

    def _extract_response(self, resp: Any) -> dict[str, Any]:
        text = getattr(resp, "output_text", None) or ""
        thinking_parts: list[str] = []
        sources: list[dict[str, Any]] = []
        tool_calls = 0

        for item in getattr(resp, "output", None) or []:
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
                    self._append_source(
                        sources,
                        {
                            "url": getattr(source, "url", None),
                            "accessed_at": self.now_iso(),
                            "title": getattr(source, "title", None),
                        },
                    )
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

        usage = getattr(resp, "usage", None)
        input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "output_tokens", 0) if usage else 0
        cost = self.price_tokens(input_tokens or 0, output_tokens or 0)
        cost += tool_calls * float(self.cfg.get("price_per_tool_call", 0))
        if cost == 0 and self.cfg.get("fallback_price_per_run_usd"):
            cost = float(self.cfg["fallback_price_per_run_usd"])

        return {
            "text": text,
            "thinking": "\n\n".join(thinking_parts) or None,
            "input_tokens": input_tokens or 0,
            "output_tokens": output_tokens or 0,
            "tool_calls": tool_calls,
            "sources": sources,
            "cost_usd": cost,
        }

    @staticmethod
    def _append_source(sources: list[dict[str, Any]], source: dict[str, Any]) -> None:
        if not source.get("url"):
            return
        if all(existing.get("url") != source["url"] for existing in sources):
            sources.append(source)
