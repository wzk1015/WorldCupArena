"""Runner registry: maps model entries from configs/models.yaml to runner classes."""

from __future__ import annotations

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
    # Dedicated runners
    "anthropic":   AnthropicRunner,
    "google":      GeminiRunner,
    "openai_deep_research": OpenAIDeepResearchRunner,
    "google_deep_research": GeminiDeepResearchRunner,
    # "miromind": MiroThinkerRunner,     # not yet implemented
}


def build_runner(model_cfg: dict[str, Any]) -> BaseRunner:
    provider = model_cfg["provider"]
    if provider not in PROVIDER_RUNNERS:
        raise NotImplementedError(f"No runner registered for provider={provider}")
    return PROVIDER_RUNNERS[provider](model_cfg)


__all__ = ["BaseRunner", "RunnerResult", "build_runner", "PROVIDER_RUNNERS",
           "OpenAICompatRunner", "AnthropicRunner", "GeminiRunner",
           "OpenAIDeepResearchRunner", "GeminiDeepResearchRunner"]
