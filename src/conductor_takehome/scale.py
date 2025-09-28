from __future__ import annotations

from typing import List, Tuple, Optional, Dict, Any

# Reuse the package's scale phrase recognizers
from .filters import _PATTERNS as SCALE_PATTERNS  # type: ignore[attr-defined]
from .filters import _ABBR as SCALE_ABBR  # type: ignore[attr-defined]


def _lines_by_y(words: List[dict], bucket: float = 10.0) -> Dict[float, List[dict]]:
    lines: Dict[float, List[dict]] = {}
    for w in words:
        y = round(float(w.get("top", 0.0)) / bucket) * bucket
        lines.setdefault(y, []).append(w)
    return lines


def _line_text_and_spans(line_words: List[dict]) -> Tuple[str, List[Tuple[int, int]]]:
    # Join words with a single space; keep indices to map back to bbox later
    spans: List[Tuple[int, int]] = []
    parts: List[str] = []
    pos = 0
    for i, w in enumerate(line_words):
        t = str(w.get("text", ""))
        if i > 0:
            parts.append(" ")
            pos += 1
        start = pos
        parts.append(t)
        pos += len(t)
        spans.append((start, pos))
    return ("".join(parts), spans)


def _bbox_for_char_span(line_words: List[dict], spans: List[Tuple[int, int]], start: int, end: int) -> Optional[Tuple[float, float, float, float]]:
    # Select words that overlap [start, end)
    selected: List[dict] = []
    for w, (s, e) in zip(line_words, spans):
        if s < end and e > start:
            selected.append(w)
    if not selected:
        return None
    x0 = min(float(w.get("x0", 0.0)) for w in selected)
    top = min(float(w.get("top", 0.0)) for w in selected)
    x1 = max(float(w.get("x1", 0.0)) for w in selected)
    bottom = max(float(w.get("bottom", 0.0)) for w in selected)
    return (x0, top, x1, bottom)


def detect_scale_phrase(words: List[dict]) -> Tuple[Optional[str], Optional[str], Optional[Tuple[float, float, float, float]]]:
    """Find a page-level scale phrase like "Dollars in Millions" and return (scale, phrase, bbox).

    - scale is one of {"thousands","millions","billions"} or None
    - phrase is the matched string, or None
    - bbox is the rectangle covering the phrase on the page, or None
    """
    if not words:
        return None, None, None

    lines = _lines_by_y(words)
    for _, line_words in sorted(lines.items(), key=lambda kv: kv[0]):
        text, spans = _line_text_and_spans(line_words)
        if not text:
            continue
        for pat in SCALE_PATTERNS:
            m = pat.search(text)
            if not m:
                continue
            grp = m.group(1)
            if grp and grp.upper() in SCALE_ABBR:
                scale = SCALE_ABBR[grp.upper()]
            else:
                scale = grp.lower() if grp else None
            bbox = _bbox_for_char_span(line_words, spans, m.start(), m.end())
            return scale, m.group(0), bbox

    return None, None, None


def scale_factor(scale: Optional[str]) -> float:
    return {"thousands": 1_000.0, "millions": 1_000_000.0, "billions": 1_000_000_000.0}.get((scale or "").lower(), 1.0)


def _inside(box: Tuple[float, float, float, float], region: Tuple[float, float, float, float], tol: float = 0.5) -> bool:
    x0, y0, x1, y1 = box
    rx0, ry0, rx1, ry1 = region
    return (x0 >= rx0 - tol) and (x1 <= rx1 + tol) and (y0 >= ry0 - tol) and (y1 <= ry1 + tol)


def detect_scale_phrase_in_region(
    words: List[dict],
    region: Tuple[float, float, float, float],
) -> Tuple[Optional[str], Optional[str], Optional[Tuple[float, float, float, float]]]:
    """Detect scale phrase using only words inside the given region bbox."""
    sub_words = []
    for w in words:
        bbox = (
            float(w.get("x0", 0.0)),
            float(w.get("top", 0.0)),
            float(w.get("x1", 0.0)),
            float(w.get("bottom", 0.0)),
        )
        if _inside(bbox, region):
            sub_words.append(w)
    if not sub_words:
        return None, None, None
    return detect_scale_phrase(sub_words)


def apply_natural_scale(
    value: float,
    *,
    page_words: List[dict],
    page_image: Any | None = None,
    draw_kwargs: Optional[dict] = None,
) -> Tuple[float, Optional[str], Optional[str], Optional[Tuple[float, float, float, float]]]:
    """Given a numeric value on a page, detect a scale phrase and apply it.

    Args:
        value: The numeric value to scale.
        page_words: pdfplumber page.extract_words(...) for the page.
        page_image: Optional pdfplumber PageImage (from page.to_image()) to draw on.
        draw_kwargs: Optional kwargs for drawing the bbox (e.g., stroke, stroke_width).

    Returns:
        (scaled_value, scale_name, matched_phrase, bbox)
    """
    scale, phrase, bbox = detect_scale_phrase(page_words)
    factor = scale_factor(scale)
    if page_image is not None and bbox is not None:
        dk = {"stroke": "blue", "stroke_width": 2}
        if draw_kwargs:
            dk.update(draw_kwargs)
        page_image.draw_rects([
            {"x0": bbox[0], "top": bbox[1], "x1": bbox[2], "bottom": bbox[3]}
        ], **dk)
    return value * factor, scale, phrase, bbox
