from __future__ import annotations
import re
from typing import Optional, Tuple

# Return type: (scale_name, matched_phrase) or (None, None)
# Recognizes many variants such as:
#   (Dollars in Millions)
#   Dollars in Millions
#   ($ in millions)
#   (Millions), ($ Millions)
#   reported in millions of dollars
#   ($ in M) / (K|M|B)

_PATTERNS = [
    # Classic forms
    re.compile(r"\(\s*\$?\s*in\s*(thousands|millions|billions)\s*\)", re.I),
    re.compile(r"\b(amounts?|figures?|values?)\s+in\s+(thousands|millions|billions)\b", re.I),
    re.compile(r"\b(?:in|reported in)\s+(thousands|millions|billions)\s+of\s+(?:dollars|usd)\b", re.I),

    # BI Publisher special: "(Dollars in Millions)" / "Dollars in Millions"
    re.compile(r"\(\s*(?:dollars|usd)\s+in\s+(thousands|millions|billions)\s*\)", re.I),
    re.compile(r"\b(?:dollars|usd)\s+in\s+(thousands|millions|billions)\b", re.I),

    # Short-hand header-like variants
    re.compile(r"\(\s*\$?\s*(thousands|millions|billions)\s*\)", re.I),

    # Abbreviations
    re.compile(r"\(\s*\$?\s*(?:in\s+)?(K|M|B)\s*\)", re.I),
]

_ABBR = {"K": "thousands", "M": "millions", "B": "billions"}


def page_scale_hint(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Detect a page-level scale cue.

    Returns:
        (scale, matched_phrase) where scale in {"thousands","millions","billions"},
        or (None, None) if not found.
    """
    if not text:
        return None, None
    for pat in _PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        grp = m.group(1)
        if grp and grp.upper() in _ABBR:  # K/M/B path
            scale = _ABBR[grp.upper()]
        else:
            scale = grp.lower() if grp else None
        return scale, m.group(0)
    return None, None