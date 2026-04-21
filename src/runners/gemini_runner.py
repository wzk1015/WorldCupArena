"""Runner for Google Gemini via its OpenAI-compatible endpoint.

Google exposes an OpenAI-compatible chat-completions API at:
  https://generativelanguage.googleapis.com/v1beta/openai

The only difference from OpenAICompatRunner is:
  - base_url must end with /openai (appended automatically if missing)
  - auth uses X-goog-api-key header, but the openai SDK also accepts it as
    a bearer token (api_key="...") which Google's compat layer accepts

Supports response_format={"type":"json_object"} for Gemini 2.5+.
"""

from __future__ import annotations

from typing import Any

from .openai_compat import OpenAICompatRunner

# _COMPAT_SUFFIX = "/openai"


class GeminiRunner(OpenAICompatRunner):
    category = "closed_llm"

    def base_url(self) -> str:
        url = super().base_url() or "https://generativelanguage.googleapis.com/v1beta"
        url = url.rstrip("/")
        # if not url.endswith(_COMPAT_SUFFIX):
        #     url += _COMPAT_SUFFIX
        return url
