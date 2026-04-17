"""Runner registry: maps model entries from configs/models.yaml to runner classes."""

from __future__ import annotations

from typing import Any

from .base import BaseRunner, RunnerResult
from .openai_compat import OpenAICompatRunner
from .anthropic_runner import AnthropicRunner

# provider -> runner class
PROVIDER_RUNNERS: dict[str, type[BaseRunner]] = {
    "openai": OpenAICompatRunner,
    "deepseek": OpenAICompatRunner,
    "together": OpenAICompatRunner,
    "dashscope": OpenAICompatRunner,
    "xai": OpenAICompatRunner,
    "perplexity": OpenAICompatRunner,
    "anthropic": AnthropicRunner,
    # Placeholders implemented later:
    # "google": GeminiRunner,
    # "miromind": MiroThinkerRunner,
}


def build_runner(model_cfg: dict[str, Any]) -> BaseRunner:
    provider = model_cfg["provider"]
    if provider not in PROVIDER_RUNNERS:
        raise NotImplementedError(f"No runner registered for provider={provider}")
    return PROVIDER_RUNNERS[provider](model_cfg)


__all__ = ["BaseRunner", "RunnerResult", "build_runner", "PROVIDER_RUNNERS"]
