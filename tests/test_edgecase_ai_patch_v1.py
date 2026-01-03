import modules.adapter.edgecase_ai_patch_v1.main as patcher


def test_extract_patches_defaults_on_bad_payload():
    data = patcher._extract_patches([{"patches": [1]}])
    assert data["confidence"] == "low"
    assert data["patches"] == []


def test_extract_patches_valid():
    payload = {"confidence": "high", "patches": [{"section_id": "1", "reason_code": "x", "path": "/a", "op": "remove"}]}
    data = patcher._extract_patches(payload)
    assert data["confidence"] == "high"
    assert len(data["patches"]) == 1


def test_extract_patches_invalid_confidence():
    payload = {"confidence": "maybe", "patches": []}
    data = patcher._extract_patches(payload)
    assert data["confidence"] == "low"


def test_coerce_patch_validates_sequence_value():
    patch = {
        "section_id": "1",
        "reason_code": "x",
        "path": "/sections/1/sequence/0",
        "op": "replace",
        "value": {"kind": "death", "outcome": {"terminal": {"kind": "death"}}},
    }
    assert patcher._coerce_patch(patch)

    bad = {
        "section_id": "1",
        "reason_code": "x",
        "path": "/sections/1/sequence/0",
        "op": "replace",
        "value": {"type": "death"},
    }
    assert patcher._coerce_patch(bad) is None
