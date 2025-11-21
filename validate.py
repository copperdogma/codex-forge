from typing import List, Dict, Set, Tuple
from schemas import Paragraph


class ValidationError(Exception):
    pass


def validate_pages(paragraphs: List[Paragraph], strict: bool = True) -> None:
    ids: Set[str] = set()
    for p in paragraphs:
        if p.id in ids:
            raise ValidationError(f"Duplicate paragraph id {p.id}")
        ids.add(p.id)

    if strict:
        # Check choice targets exist
        unknown_targets: List[Tuple[str, str]] = []
        for p in paragraphs:
            for c in p.choices:
                if c.target not in ids:
                    unknown_targets.append((p.id, c.target))
        if unknown_targets:
            raise ValidationError(f"Unknown choice targets: {unknown_targets}")

    # Basic range check
    numeric_ids = sorted(int(x) for x in ids)
    if numeric_ids and (numeric_ids[0] < 1 or numeric_ids[-1] > 400):
        raise ValidationError("Paragraph id out of expected range 1-400")
