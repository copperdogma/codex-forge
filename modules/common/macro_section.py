import re
from typing import Any, Dict, Optional, Tuple


def _page_num(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        match = re.match(r"^\s*(\d{1,4})", value)
        if not match:
            return None
        try:
            return int(match.group(1))
        except Exception:
            return None
    return None


def _normalize_range(rng: Any) -> Optional[Tuple[int, int]]:
    if not rng or not isinstance(rng, (list, tuple)) or len(rng) < 2:
        return None
    start = _page_num(rng[0])
    end = _page_num(rng[1])
    if start is None or end is None:
        return None
    return (start, end)


def macro_section_for_page(page: Any, segments: Optional[Dict[str, Any]]) -> Optional[str]:
    if segments is None:
        return None
    page_num = _page_num(page)
    if page_num is None:
        return None

    front = _normalize_range(segments.get("frontmatter_pages") or segments.get("front_matter_pages"))
    game = _normalize_range(segments.get("gameplay_pages") or segments.get("game_pages"))
    endm = _normalize_range(segments.get("endmatter_pages") or segments.get("end_matter_pages"))

    if front and front[0] <= page_num <= front[1]:
        return "frontmatter"
    if game and game[0] <= page_num <= game[1]:
        return "gameplay"
    if endm and endm[0] <= page_num <= endm[1]:
        return "endmatter"
    return None


def page_num_from_element_id(element_id: Optional[str]) -> Optional[int]:
    if not element_id:
        return None
    prefix = element_id.split("-", 1)[0]
    return _page_num(prefix)
