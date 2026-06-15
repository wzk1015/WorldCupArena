"""Runner registry: maps model entries from configs/models.yaml to runner classes."""

from __future__ import annotations

import os
from typing import Any

from .base import BaseRunner, RunnerResult
from .openai_compat import OpenAICompatRunner
from .anthropic_runner import AnthropicRunner
from .gemini_runner import GeminiRunner
from .openai_deep_research_runner import OpenAIDeepResearchRunner
from .gemini_deep_research_runner import GeminiDeepResearchRunner

# provider -> runner class
PROVIDER_RUNNERS: dict[str, type[BaseRunner]] = {
    # OpenAI and OpenAI-compatible providers
    "openai":      OpenAICompatRunner,
    "deepseek":    OpenAICompatRunner,
    "together":    OpenAICompatRunner,
    "dashscope":   OpenAICompatRunner,   # Alibaba Qwen
    "xai":         OpenAICompatRunner,   # Grok
    "perplexity":  OpenAICompatRunner,
    "moonshot":    OpenAICompatRunner,   # Kimi K2
    "zhipu":       OpenAICompatRunner,   # GLM
    "yunwu":       OpenAICompatRunner,   # OpenAI-compatible aggregation proxy
    "openrouter":  OpenAICompatRunner,   # OpenRouter aggregation proxy
    "gptplus5":    OpenAICompatRunner,   # GPTPlus5/New API aggregation proxy
    # Dedicated runners
    "anthropic":   AnthropicRunner,
    "google":      GeminiRunner,
    "openai_deep_research": OpenAIDeepResearchRunner,
    "google_deep_research": GeminiDeepResearchRunner,
    # "miromind": MiroThinkerRunner,     # not yet implemented
}


GPTPLUS5_BASE_URL = "https://az.gptplus5.com/v1"
GPTPLUS5_MODEL_MAP: dict[str, str] = {
    # closed_llm
    "gemini-3.1-pro-preview-thinking": "gemini-3.1-pro-preview-thinking",
    "claude-opus-4-7-thinking": "claude-opus-4-7",
    "gpt-5.4": "gpt-5.4",
    # open_llm
    "deepseek-r1": "deepseek-v4-pro",
    "qwen3-max": "qwen3-max",
    "kimi-k2": "kimi-k2.6",
    "glm-4.5": "glm-5.1",
    "doubao-seed-1.6-thinking": "doubao-seed-2-0-lite-260428",
    "minimax-m2.7": "MiniMax-M2.7",
    # search_llm
    "gemini-3.1-pro-preview-thinking-search": "gemini-3.1-pro-preview-thinking",
    "claude-opus-4-7-thinking-search": "claude-opus-4-7",
    "gpt-5.4-search": "gpt-5.4",
    # deep_research_agent: GPTPlus5 does not expose the native Google
    # Interactions deep-research agent, so this routes to the closest
    # OpenAI-compatible Gemini thinking model with S2 web-search enabled.
    "gemini-deep-research": "gemini-3.1-pro-preview-thinking",
}
GPTPLUS5_PROXIED_CATEGORIES = {"closed_llm", "open_llm", "search_llm", "deep_research_agent"}


def _apply_model_proxy(model_cfg: dict[str, Any]) -> dict[str, Any]:
    proxy = os.environ.get("WCA_MODEL_PROXY", "").strip().lower()
    if proxy not in {"gptplus5", "gptplus5-api"}:
        return model_cfg
    category = model_cfg.get("model_category")
    if category not in GPTPLUS5_PROXIED_CATEGORIES:
        return model_cfg

    model_id = model_cfg.get("id", "")
    proxy_model = model_cfg.get("gptplus5_model") or GPTPLUS5_MODEL_MAP.get(model_id)
    if not proxy_model:
        print(
            f"[runner] WCA_MODEL_PROXY=gptplus5 requested, but no GPTPlus5 model mapping for {model_id}; "
            "using the configured provider instead.",
            flush=True,
        )
        return model_cfg

    routed = dict(model_cfg)
    routed["provider"] = "gptplus5"
    routed["model"] = proxy_model
    routed["api_key_env"] = "GPTPLUS5_API_KEY"
    routed["base_url_env"] = "GPTPLUS5_BASE_URL"
    routed["base_url"] = GPTPLUS5_BASE_URL
    if category == "search_llm":
        if model_id == "claude-opus-4-7-thinking-search":
            # GPTPlus5 currently turns Claude + web_search_options into raw
            # search results for the full prompt instead of a forecast JSON.
            routed["tools"] = []
            routed["json_mode"] = True
        else:
            routed["tools"] = ["web_search"]
            routed["json_mode"] = model_id == "gemini-3.1-pro-preview-thinking-search"
        routed.setdefault("max_tokens", 32000)
    elif category == "deep_research_agent":
        routed["tools"] = ["web_search"]
        routed["json_mode"] = model_id == "gemini-deep-research"
        routed["max_tokens"] = routed.get("json_compiler_max_tokens") or routed.get("max_tokens", 20000)
        routed.setdefault("timeout_seconds", 600)
        routed.setdefault("assumed_tool_calls", 1)
    elif model_id == "doubao-seed-1.6-thinking":
        routed["json_mode"] = False
    routed.setdefault("default_headers", {})
    return routed


def build_runner(model_cfg: dict[str, Any], apply_proxy: bool = True) -> BaseRunner:
    if apply_proxy:
        model_cfg = _apply_model_proxy(model_cfg)
    provider = model_cfg["provider"]
    if provider not in PROVIDER_RUNNERS:
        raise NotImplementedError(f"No runner registered for provider={provider}")
    return PROVIDER_RUNNERS[provider](model_cfg)


def _source_label(cfg: dict[str, Any]) -> str:
    """Short human label for which source/variant a runner ended up using."""
    return cfg.get("gptplus5_model") or cfg.get("model") or cfg.get("provider") or "primary"


def build_runner_chain(model_cfg: dict[str, Any]) -> list[tuple[str, BaseRunner]]:
    """Primary source plus any configured ``fallbacks``, as (label, runner) pairs.

    Each entry in ``model_cfg["fallbacks"]`` is a partial override, tried in order
    when the preceding source yields no usable prediction (5xx / timeout / unparseable
    output). This lets an unstable model auto-retry on an alternate variant or source.
    Common shapes::

        fallbacks:
          - {gptplus5_model: doubao-...-260215}  # same GPTPlus5 proxy, alt model variant
          - {source: native}                     # the model's own provider (bypass proxy)
          - {provider: openrouter, model: ..., api_key_env: OPENROUTER_API_KEY,
             base_url_env: OPENROUTER_BASE_URL}   # explicit alternate source

    Fallbacks that cannot be built (missing key / mapping / runner) are skipped, not fatal.
    """
    base = {k: v for k, v in model_cfg.items() if k != "fallbacks"}
    chain: list[tuple[str, BaseRunner]] = [(_source_label(_apply_model_proxy(base)), build_runner(base))]
    for fb in (model_cfg.get("fallbacks") or []):
        # Re-route through the GPTPlus5 proxy only when the fallback names a proxy
        # variant; `native` / explicit-source fallbacks use their own config verbatim.
        use_proxy = "gptplus5_model" in fb
        merged = {**base, **{k: v for k, v in fb.items() if k != "source"}}
        try:
            runner = build_runner(merged, apply_proxy=use_proxy)
        except (NotImplementedError, RuntimeError) as e:
            print(f"[runner] skip fallback {fb} for {model_cfg.get('id')}: {e}", flush=True)
            continue
        label = _source_label(_apply_model_proxy(merged) if use_proxy else merged)
        chain.append((label, runner))
    return chain


__all__ = ["BaseRunner", "RunnerResult", "build_runner", "build_runner_chain", "PROVIDER_RUNNERS",
           "OpenAICompatRunner", "AnthropicRunner", "GeminiRunner",
           "OpenAIDeepResearchRunner", "GeminiDeepResearchRunner"]
