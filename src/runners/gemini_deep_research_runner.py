"""Runner for the Gemini Deep Research agent via the Interactions API."""

from __future__ import annotations

import time
from typing import Any

from google.genai import types

from .gemini_runner import GeminiRunner


class GeminiDeepResearchRunner(GeminiRunner):
    category = "deep_research_agent"

    def generate(self, system_prompt: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        client = self._client()
        user_text = self._contents(messages)
        user_text = (
            f"{system_prompt}\n\n{user_text}\n\n"
            "After completing the research, return the final forecast as one valid JSON object "
            "that matches the supplied schema. Do not wrap the JSON in Markdown."
        )

        interaction = client.interactions.create(
            input=user_text,
            agent=self.cfg.get("agent", self.cfg["model"]),
            background=True,
            store=True,
            agent_config={
                "type": "deep-research",
                "thinking_summaries": self.cfg.get("thinking_summaries", "auto"),
                "visualization": self.cfg.get("visualization", "off"),
            },
        )
        interaction = self._poll_until_done(client, interaction)
        out = self._extract_interaction(interaction)
        try:
            self.parse_json(out["text"])
        except Exception:  # noqa: BLE001
            out = self._compile_report_to_json(client, system_prompt, user_text, out)
        return out

    def _poll_until_done(self, client: Any, interaction: Any) -> Any:
        max_wait_seconds = int(self.cfg.get("max_wait_seconds", 1200))
        poll_seconds = float(self.cfg.get("poll_seconds", 10))
        started = time.time()

        while getattr(interaction, "status", None) in {"in_progress", "requires_action"}:
            if time.time() - started > max_wait_seconds:
                raise TimeoutError(
                    f"{self.model_id}: deep research still {interaction.status!r} after {max_wait_seconds}s"
                )
            time.sleep(poll_seconds)
            interaction = client.interactions.get(interaction.id)

        status = getattr(interaction, "status", None)
        if status and status not in {"completed"}:
            details = getattr(interaction, "error", None)
            raise RuntimeError(f"{self.model_id}: deep research status={status!r}, details={details!r}")
        return interaction

    def _extract_interaction(self, interaction: Any) -> dict[str, Any]:
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        sources: list[dict[str, Any]] = []
        tool_calls = 0

        for item in getattr(interaction, "outputs", None) or []:
            item_type = getattr(item, "type", None)
            if item_type == "text":
                text = getattr(item, "text", None)
                if text:
                    text_parts.append(text)
                for ann in getattr(item, "annotations", None) or []:
                    if getattr(ann, "type", None) == "url_citation":
                        self._append_source(
                            sources,
                            {
                                "url": getattr(ann, "url", None),
                                "accessed_at": self.now_iso(),
                                "title": getattr(ann, "title", None),
                            },
                        )
            elif item_type == "thought":
                for summary in getattr(item, "summary", None) or []:
                    summary_text = getattr(summary, "text", None)
                    if summary_text:
                        thinking_parts.append(summary_text)
            elif item_type == "google_search_call":
                tool_calls += 1
            elif item_type == "url_context_result":
                for result in getattr(item, "result", None) or []:
                    self._append_source(
                        sources,
                        {"url": getattr(result, "url", None), "accessed_at": self.now_iso()},
                    )

        usage = getattr(interaction, "usage", None)
        input_tokens = getattr(usage, "total_input_tokens", 0) if usage else 0
        output_tokens = 0
        if usage:
            output_tokens += getattr(usage, "total_output_tokens", 0) or 0
            output_tokens += getattr(usage, "total_thought_tokens", 0) or 0
        cost = self.price_tokens(input_tokens or 0, output_tokens or 0)
        if cost == 0 and self.cfg.get("fallback_price_per_run_usd"):
            cost = float(self.cfg["fallback_price_per_run_usd"])

        return {
            "text": "\n\n".join(text_parts),
            "thinking": "\n\n".join(thinking_parts) or None,
            "input_tokens": input_tokens or 0,
            "output_tokens": output_tokens or 0,
            "tool_calls": tool_calls,
            "sources": sources,
            "cost_usd": cost,
        }

    def _compile_report_to_json(
        self,
        client: Any,
        system_prompt: str,
        task_prompt: str,
        out: dict[str, Any],
    ) -> dict[str, Any]:
        report = out.get("text", "")
        compiler_prompt = (
            "Convert the Deep Research report below into the exact JSON object requested by the "
            "original forecasting task. Preserve calibrated probabilities and cited-source URLs "
            "from the report where possible. Return JSON only.\n\n"
            "### Original task\n"
            f"{task_prompt}\n\n"
            "### Deep Research report\n"
            f"{report}"
        )
        resp = client.models.generate_content(
            model=self.cfg.get("json_compiler_model", "gemini-3.1-pro-preview"),
            contents=compiler_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0,
                max_output_tokens=self.cfg.get("json_compiler_max_tokens", 8192),
                response_mime_type="application/json",
            ),
        )

        usage = resp.usage_metadata
        input_tokens = usage.prompt_token_count if usage else 0
        if usage and usage.total_token_count is not None and input_tokens is not None:
            output_tokens = max(0, usage.total_token_count - input_tokens)
        elif usage:
            output_tokens = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
        else:
            output_tokens = 0

        merged = dict(out)
        merged["text"] = resp.text or ""
        merged["input_tokens"] = (merged.get("input_tokens") or 0) + (input_tokens or 0)
        merged["output_tokens"] = (merged.get("output_tokens") or 0) + (output_tokens or 0)
        merged["cost_usd"] = (merged.get("cost_usd") or 0) + self.price_tokens(input_tokens or 0, output_tokens or 0)
        note = "Deep Research report converted to schema JSON with a Gemini compiler pass."
        merged["thinking"] = "\n\n".join([x for x in [merged.get("thinking"), note] if x])
        return merged

    @staticmethod
    def _append_source(sources: list[dict[str, Any]], source: dict[str, Any]) -> None:
        if not source.get("url"):
            return
        if all(existing.get("url") != source["url"] for existing in sources):
            sources.append(source)
