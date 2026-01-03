from typing import Any, Dict, Iterable, List, Tuple


def _claim_key(claim: Dict[str, Any]) -> Tuple[str, str, str, str]:
    target = str(claim.get("target") or "").strip()
    claim_type = str(claim.get("claim_type") or "").strip()
    module_id = str(claim.get("module_id") or "").strip()
    evidence_path = str(claim.get("evidence_path") or "").strip()
    return (target, claim_type, module_id, evidence_path)


def _normalize_claim_dict(claim: Any) -> Dict[str, Any]:
    if isinstance(claim, dict):
        return claim
    if hasattr(claim, "model_dump"):
        return claim.model_dump()
    if hasattr(claim, "dict"):
        return claim.dict()
    return {}


def merge_turn_to_claims(existing: Iterable[Dict[str, Any]], new_claims: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen = set()

    for claim in existing or []:
        claim_dict = _normalize_claim_dict(claim)
        if not claim_dict:
            continue
        key = _claim_key(claim_dict)
        if not key[0]:
            continue
        if key in seen:
            continue
        seen.add(key)
        merged.append(claim_dict)

    for claim in new_claims or []:
        claim_dict = _normalize_claim_dict(claim)
        if not claim_dict:
            continue
        key = _claim_key(claim_dict)
        if not key[0]:
            continue
        if key in seen:
            continue
        seen.add(key)
        merged.append(claim_dict)

    return merged
