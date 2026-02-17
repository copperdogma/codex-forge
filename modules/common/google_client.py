"""Lightweight Google Gemini vision client with usage logging.

Mirrors the pattern in openai_client.py — centralizes API calls and
logs token usage via log_llm_usage().
"""

from __future__ import annotations

import base64
import os
from typing import Any, Optional, Tuple

from modules.common.utils import log_llm_usage

try:
    from google import genai
    from google.genai import types

    _GENAI_IMPORT_ERROR = None
except Exception as e:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]
    _GENAI_IMPORT_ERROR = e


def _decode_data_uri(data_uri: str) -> Tuple[bytes, str]:
    """Extract raw bytes and mime type from a data URI."""
    if data_uri.startswith("data:"):
        header, b64_data = data_uri.split(",", 1)
        mime_type = header.split(":")[1].split(";")[0]
    else:
        b64_data = data_uri
        mime_type = "image/jpeg"
    return base64.b64decode(b64_data), mime_type


class GeminiVisionClient:
    """Stateless helper for Gemini vision calls with usage logging."""

    def __init__(self, api_key: Optional[str] = None):
        if genai is None:
            raise RuntimeError(
                "google-genai package not installed; pip install google-genai"
            ) from _GENAI_IMPORT_ERROR
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self._api_key:
            raise RuntimeError(
                "GEMINI_API_KEY or GOOGLE_API_KEY must be set in the environment"
            )
        self._client = genai.Client(api_key=self._api_key)

    def generate_vision(
        self,
        model: str,
        system_prompt: str,
        user_text: str,
        image_data: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Tuple[str, Optional[Any], Optional[str]]:
        """Call Gemini with a vision prompt.

        Args:
            model: Gemini model ID (e.g. "gemini-3-pro-preview")
            system_prompt: System instruction text
            user_text: User message text
            image_data: Base64 data URI (data:image/jpeg;base64,...)
            temperature: Sampling temperature
            max_tokens: Max output tokens

        Returns:
            (raw_text, usage_metadata, response_id)
        """
        image_bytes, mime_type = _decode_data_uri(image_data)
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        resp = self._client.models.generate_content(
            model=model,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=user_text),
                        image_part,
                    ],
                ),
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="text/plain",
            ),
        )

        raw = resp.text or ""
        response_id = getattr(resp, "response_id", None)

        # Extract usage for logging
        usage_meta = getattr(resp, "usage_metadata", None)
        prompt_tokens = 0
        completion_tokens = 0
        if usage_meta:
            prompt_tokens = getattr(usage_meta, "prompt_token_count", 0) or 0
            completion_tokens = getattr(usage_meta, "candidates_token_count", 0) or 0

        log_llm_usage(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            provider="google",
        )

        return raw, usage_meta, response_id
