import re
from typing import Optional

_CONSTITUENCY_CLEAN_REGEX = re.compile(r"\s*\((?:SC|ST)\)\s*$", flags=re.IGNORECASE)


def normalize_place(text: Optional[str]) -> Optional[str]:
    """
    Normalise place name (state, district, constituency):
    - upper case
    - trim
    - collapse spaces
    - remove a trailing '(SC)' or '(ST)'
    """
    if text is None:
        return None
    val = str(text).strip()
    if not val:
        return None
    # Remove trailing (SC) or (ST)
    val = _CONSTITUENCY_CLEAN_REGEX.sub("", val).strip()
    # Collapse whitespace and convert to upper case
    val = re.sub(r"\s+", " ", val).strip().upper()
    return val if val else None
