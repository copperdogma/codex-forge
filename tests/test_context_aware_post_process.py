from argparse import Namespace

from modules.adapter.context_aware_post_process_v1.main import should_repair_portion


def test_should_repair_based_on_dictionary_score():
    args = Namespace(dictionary_threshold=0.1, char_confusion_threshold=0.2, min_chars=5)
    text = "This is a single line of text that is long enough."
    metrics = {"dictionary_score": 0.15, "char_confusion_score": 0.05}
    should, reasons = should_repair_portion(text, metrics, args)
    assert should is True
    assert any("dictionary_score" in reason for reason in reasons)


def test_should_repair_based_on_char_confusion():
    args = Namespace(dictionary_threshold=0.5, char_confusion_threshold=0.2, min_chars=5)
    text = "Another portion text that is long enough."
    metrics = {"dictionary_score": 0.1, "char_confusion_score": 0.25}
    should, reasons = should_repair_portion(text, metrics, args)
    assert should is True
    assert any("char_confusion" in reason for reason in reasons)


def test_should_not_repair_short_fragments():
    args = Namespace(dictionary_threshold=0.0, char_confusion_threshold=0.0, min_chars=50)
    text = "Short"
    metrics = {"dictionary_score": 1.0, "char_confusion_score": 1.0}
    should, reasons = should_repair_portion(text, metrics, args)
    assert should is False
    assert reasons == []
