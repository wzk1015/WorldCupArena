"""Runner registry: maps model entries from configs/models.yaml to runner classes."""

from __future__ import annotations

from typing import Any

from .base import BaseRunner, RunnerResult
from .openai_compat import OpenAICompatRunner
from .anthropic_runner import AnthropicRunner
from .gemini_runner import GeminiRunner

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
    # Dedicated runners
    "anthropic":   AnthropicRunner,
    "google":      GeminiRunner,
    # "miromind": MiroThinkerRunner,     # not yet implemented
}


def build_runner(model_cfg: dict[str, Any]) -> BaseRunner:
    provider = model_cfg["provider"]
    if provider not in PROVIDER_RUNNERS:
        raise NotImplementedError(f"No runner registered for provider={provider}")
    return PROVIDER_RUNNERS[provider](model_cfg)


__all__ = ["BaseRunner", "RunnerResult", "build_runner", "PROVIDER_RUNNERS",
           "OpenAICompatRunner", "AnthropicRunner", "GeminiRunner"]
