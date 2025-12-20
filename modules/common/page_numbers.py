from typing import Iterable, Dict, Any, Optional, Tuple, List


def _coerce_int(val: Any) -> Optional[int]:
    if isinstance(val, int):
        return val
    if val is None:
        return None
    digits = ""
    for ch in str(val):
        if ch.isdigit():
            digits += ch
        else:
            break
    if not digits:
        return None
    try:
        return int(digits)
    except Exception:
        return None


def validate_sequential_page_numbers(
    rows: Iterable[Dict[str, Any]],
    *,
    field: str = "page_number",
    allow_gaps: bool = False,
) -> Tuple[bool, List[int]]:
    """
    Validate that page numbers are positive integers and sequential.
    Returns (ok, missing) where missing is the list of absent page numbers.
    """
    nums: List[int] = []
    for row in rows:
        n = _coerce_int(row.get(field))
        if n is not None:
            nums.append(n)
    if not nums:
        return False, []
    nums = sorted(set(nums))
    if nums[0] < 1:
        return False, []
    if allow_gaps:
        return True, []
    expected = list(range(nums[0], nums[-1] + 1))
    missing = [n for n in expected if n not in nums]
    return len(missing) == 0, missing
