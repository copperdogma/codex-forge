from __future__ import annotations

from typing import Any, Optional, Tuple

from modules.common.utils import log_llm_usage

try:  # pragma: no cover - import is environment-dependent
    from openai import OpenAI as _OpenAI  # type: ignore
    _OPENAI_IMPORT_ERROR = None
except Exception as e:  # pragma: no cover
    _OpenAI = None
    _OPENAI_IMPORT_ERROR = e


def _extract_usage(response: Any) -> Tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    if isinstance(usage, dict):
        prompt = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        completion = usage.get("completion_tokens") or usage.get("output_tokens") or 0
        return int(prompt), int(completion)
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    if prompt is None:
        prompt = getattr(usage, "input_tokens", 0)
    if completion is None:
        completion = getattr(usage, "output_tokens", 0)
    return int(prompt or 0), int(completion or 0)


class _ChatCompletionsProxy:
    def __init__(self, client: Any, logger):
        self._client = client
        self._logger = logger

    def create(self, **kwargs):
        response = self._client.chat.completions.create(**kwargs)
        self._logger(response, kwargs.get("model"))
        return response


class _ChatProxy:
    def __init__(self, client: Any, logger):
        self.completions = _ChatCompletionsProxy(client, logger)


class _ResponsesProxy:
    def __init__(self, client: Any, logger):
        self._client = client
        self._logger = logger

    def create(self, **kwargs):
        if not hasattr(self._client, "responses"):
            raise RuntimeError("OpenAI client does not support responses API")
        response = self._client.responses.create(**kwargs)
        self._logger(response, kwargs.get("model"))
        return response


class OpenAI:
    """
    Wrapper for OpenAI client that centralizes usage logging.
    Mimics the public surface used across modules: client.chat.completions.create / client.responses.create.
    """

    def __init__(self, *args, **kwargs):
        if _OpenAI is None:
            raise RuntimeError("openai package not installed; pip install openai") from _OPENAI_IMPORT_ERROR
        self._client = _OpenAI(*args, **kwargs)
        self.chat = _ChatProxy(self._client, self._log_usage)
        if hasattr(self._client, "responses"):
            self.responses = _ResponsesProxy(self._client, self._log_usage)

    def _log_usage(self, response: Any, model: Optional[str]):
        prompt_tokens, completion_tokens = _extract_usage(response)
        if model is None:
            model = getattr(response, "model", None)
        log_llm_usage(
            model=model or "unknown",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            provider="openai",
        )
