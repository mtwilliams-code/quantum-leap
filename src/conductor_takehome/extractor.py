"""
PDF number extraction with intelligent scaling.

This module extracts numeric values from PDFs and applies appropriate scaling
based on context cues like "Dollars in Millions".
"""

from __future__ import annotations

import re
from typing import List, Dict, Tuple, Optional, Any, Iterator
from dataclasses import dataclass

import pdfplumber

from .scale import detect_scale_phrase, detect_scale_phrase_in_region, scale_factor


# Number parsing regex - handles $, commas, decimals, parentheses, %, footnotes
_GROUP_SEP = ",\u00A0\u2009"  # comma, NBSP, thin space
NUM_RE = re.compile(
    r"^\s*(?P<prefix>[\$\(]?)\s*"
    r"(?P<num>(?:\d{1,3}(?:[" + _GROUP_SEP + r"]\d{3})+|\d+)(?:\.\d+)?|(?:\.\d+))"
    r"\s*(?P<suffix>[%\)]?)"
    r"(?P<foot>[\*\u2020\u2021\u00B9\u00B2\u00B3\u2070-\u2079]*)\s*$"
)

# Unit classification patterns
HEADCOUNT_PAT = re.compile(
    r"\b(end\s*strength|work[-\s]*years?|workyears?|fte|headcount|person(n)?el|"
    r"items\s*managed|quantity|issues|receipts|requisitions|contracts|units?)\b",
    re.I,
)
MONEY_HINT_PAT = re.compile(
    r"\$|\b(?:usd|dollars?)\b|\(\s*\$?\s*(?:in\s+)?(?:K|M|B)\s*\)",
    re.I,
)


@dataclass
class NumberHit:
    """Represents a number found in the PDF with scaling and context information."""
    page_num: int
    raw_text: str
    raw_value: float
    scaled_value: float
    bbox: Tuple[float, float, float, float]  # x0, top, x1, bottom
    units: str  # 'people', 'money', or 'unknown'
    scale_name: Optional[str]  # 'thousands', 'millions', 'billions', or None
    scale_phrase: Optional[str]  # The actual phrase found, e.g., "(Dollars in Millions)"
    scale_bbox: Optional[Tuple[float, float, float, float]]  # Bounding box of scale phrase
    table_bbox: Optional[Tuple[float, float, float, float]]  # Table containing this number
    
    def __str__(self) -> str:
        return (f"${self.scaled_value:,.0f} (raw: {self.raw_value} '{self.raw_text}') "
                f"page {self.page_num}, scale: {self.scale_name or 'none'}")


def parse_number(token: str) -> Optional[float]:
    """Parse a token into a numeric value, handling various formats."""
    token = (token or "").strip()
    m = NUM_RE.match(token)
    if not m:
        return None
    
    num = (
        m.group("num")
        .replace(",", "")
        .replace("\u00A0", "")  # NBSP
        .replace("\u2009", "")  # thin space
    )
    
    try:
        val = float(num)
    except ValueError:
        return None
    
    # Handle parentheses (negative) and percentages
    if m.group("prefix") == "(" and m.group("suffix") == ")":
        val = -val
    if m.group("suffix") == "%":
        return None  # Skip percentages in ranking
    
    return val


def classify_units_for_word(word: dict, line_words: List[dict]) -> str:
    """
    Classify the units of a number based on surrounding context.
    
    Returns:
        'people': Headcount, FTE, personnel numbers
        'money': Dollar amounts, financial figures  
        'unknown': Ambiguous cases (will use table/page scaling)
    """
    x_left = float(word.get("x0", 0.0))
    
    # Look at words to the left of this number on the same visual line
    left_text = " ".join(
        str(w.get("text", "")) 
        for w in line_words 
        if float(w.get("x1", 0.0)) <= x_left - 2.0
    )
    
    if not left_text:
        return "unknown"
    
    if HEADCOUNT_PAT.search(left_text):
        return "people"
    if MONEY_HINT_PAT.search(left_text):
        return "money"
    
    return "unknown"


def inside_bbox(box: Tuple[float, float, float, float], 
                region: Tuple[float, float, float, float], 
                tolerance: float = 0.5) -> bool:
    """Check if a bounding box is inside a region with tolerance."""
    x0, y0, x1, y1 = box
    rx0, ry0, rx1, ry1 = region
    return (x0 >= rx0 - tolerance and x1 <= rx1 + tolerance and 
            y0 >= ry0 - tolerance and y1 <= ry1 + tolerance)


def group_words_by_line(words: List[dict], bucket_size: float = 10.0) -> Dict[float, List[dict]]:
    """Group words into approximate lines by Y coordinate."""
    lines = {}
    for w in words:
        y_key = round(float(w.get("top", 0.0)) / bucket_size) * bucket_size
        lines.setdefault(y_key, []).append(w)
    return lines


def extract_numbers_from_pdf(
    pdf_path: str,
    *,
    start_page: int = 1,
    end_page: Optional[int] = None,
    x_tolerance: float = 1.0,
    y_tolerance: float = 1.0,
    max_scaled: Optional[float] = None,
    min_scaled: Optional[float] = None,
    max_raw: Optional[float] = None,
    min_raw: Optional[float] = None,
) -> List[NumberHit]:
    """
    Extract all numbers from a PDF with intelligent scaling.
    
    Args:
        pdf_path: Path to PDF file
        start_page: First page to scan (1-based)
        end_page: Last page to scan (1-based), None for all pages
        x_tolerance: Horizontal tolerance for word grouping
        y_tolerance: Vertical tolerance for word grouping  
        max_scaled: Maximum scaled value to include
        min_scaled: Minimum scaled value to include
        max_raw: Maximum raw value to include
        min_raw: Minimum raw value to include
        
    Returns:
        List of NumberHit objects sorted by scaled value (descending)
    """
    hits = []
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        start_idx = max(1, start_page)
        end_idx = total_pages if end_page is None else min(end_page, total_pages)

        for page_num in range(start_idx, end_idx + 1):
            page = pdf.pages[page_num - 1]
            words = page.extract_words(x_tolerance=x_tolerance, y_tolerance=y_tolerance) or []
            line_map = group_words_by_line(words)

            # Extract tables and their scale information
            try:
                tables = page.find_tables() or []
            except Exception:
                tables = []
            
            table_regions = [t.bbox for t in tables if getattr(t, "bbox", None)]
            table_scales = []
            for table_bbox in table_regions:
                scale_name, scale_phrase, scale_bbox = detect_scale_phrase_in_region(words, table_bbox)
                table_scales.append((table_bbox, scale_name, scale_phrase, scale_bbox))

            # Page-level fallback scale
            page_scale_name, page_scale_phrase, page_scale_bbox = detect_scale_phrase(words)
            page_factor = scale_factor(page_scale_name)

            # Process each word
            for word in words:
                token = str(word.get("text", ""))
                raw_val = parse_number(token)
                if raw_val is None:
                    continue
                
                bbox = (
                    float(word.get("x0", 0)), float(word.get("top", 0)),
                    float(word.get("x1", 0)), float(word.get("bottom", 0))
                )
                
                # Find the line this word belongs to
                y_key = round(float(word.get("top", 0.0)) / 10.0) * 10
                line_words = line_map.get(y_key, [word])

                # Determine which scale to apply (table-specific or page-level)
                scale_name = page_scale_name
                scale_phrase = page_scale_phrase
                scale_bbox = page_scale_bbox
                factor = page_factor
                table_bbox = None
                
                for tb_bbox, tb_scale_name, tb_scale_phrase, tb_scale_bbox in table_scales:
                    if inside_bbox(bbox, tb_bbox):
                        scale_name = tb_scale_name
                        scale_phrase = tb_scale_phrase  
                        scale_bbox = tb_scale_bbox
                        factor = scale_factor(tb_scale_name)
                        table_bbox = tb_bbox
                        break

                # Classify the units and apply appropriate scaling
                units = classify_units_for_word(word, line_words)
                apply_factor = factor if units != "people" else 1.0
                scaled_val = raw_val * apply_factor

                hit = NumberHit(
                    page_num=page_num,
                    raw_text=token,
                    raw_value=raw_val,
                    scaled_value=scaled_val,
                    bbox=bbox,
                    units=units,
                    scale_name=scale_name,
                    scale_phrase=scale_phrase,
                    scale_bbox=scale_bbox,
                    table_bbox=table_bbox,
                )
                hits.append(hit)

    # Apply threshold filters
    def within_threshold(hit: NumberHit) -> bool:
        if max_scaled is not None and hit.scaled_value > max_scaled:
            return False
        if min_scaled is not None and hit.scaled_value < min_scaled:
            return False
        if max_raw is not None and hit.raw_value > max_raw:
            return False
        if min_raw is not None and hit.raw_value < min_raw:
            return False
        return True

    filtered_hits = [h for h in hits if within_threshold(h)]
    
    # Sort by scaled value descending
    filtered_hits.sort(key=lambda h: h.scaled_value, reverse=True)
    
    return filtered_hits


def find_largest_number(pdf_path: str, **kwargs) -> Optional[NumberHit]:
    """Find the single largest number in a PDF with scaling applied."""
    hits = extract_numbers_from_pdf(pdf_path, **kwargs)
    return hits[0] if hits else None