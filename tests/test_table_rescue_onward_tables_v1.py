from types import SimpleNamespace

from modules.adapter.table_rescue_onward_tables_v1.main import _call_ocr


class _DummyResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text="<p>ok</p>", usage=None, id="resp_test")


class _DummyOpenAI:
    responses_instance = None

    def __init__(self, timeout=None):
        self.timeout = timeout
        self.responses = _DummyResponses()
        _DummyOpenAI.responses_instance = self.responses


def test_call_ocr_omits_temperature_for_gpt5_models(monkeypatch):
    monkeypatch.setattr(
        "modules.adapter.table_rescue_onward_tables_v1.main.OpenAI",
        _DummyOpenAI,
    )

    _call_ocr(
        "gpt-5",
        "system prompt",
        "data:image/jpeg;base64,abc",
        0.0,
        512,
        30.0,
    )

    call = _DummyOpenAI.responses_instance.calls[0]
    assert call["model"] == "gpt-5"
    assert "temperature" not in call
    assert call["max_output_tokens"] == 512


def test_call_ocr_keeps_temperature_for_non_gpt5_models(monkeypatch):
    monkeypatch.setattr(
        "modules.adapter.table_rescue_onward_tables_v1.main.OpenAI",
        _DummyOpenAI,
    )

    _call_ocr(
        "gpt-4.1",
        "system prompt",
        "data:image/jpeg;base64,abc",
        0.0,
        512,
        30.0,
    )

    call = _DummyOpenAI.responses_instance.calls[0]
    assert call["model"] == "gpt-4.1"
    assert call["temperature"] == 0.0
    assert call["max_output_tokens"] == 512
