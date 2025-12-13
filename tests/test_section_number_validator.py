from modules.validator.section_number_validator_v1.main import check_section_number


def make_portion(section_id, text):
    return {"section_id": section_id, "raw_text": text, "portion_id": section_id}


def test_detects_missing_number():
    portion = make_portion("4", "in 4 the darkness")
    warning = check_section_number(portion)
    assert warning
    assert warning["reason"] == "missing_or_misaligned_section_number"


def test_all_good():
    portion = make_portion("7", "7  You step forward.")
    assert check_section_number(portion) == {}
