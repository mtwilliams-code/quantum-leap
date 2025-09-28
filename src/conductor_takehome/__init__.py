"""
ConductorAI Take-Home Project: PDF Number Extractor

Find the largest number in PDF documents with intelligent scaling support.
Handles scale phrases like "Dollars in Millions" to correctly scale values.
"""

from __future__ import annotations

import argparse
import json
from typing import Optional

from .extractor import extract_numbers_from_pdf, find_largest_number, NumberHit

__version__ = "0.1.0"
__all__ = ["extract_numbers_from_pdf", "find_largest_number", "NumberHit", "main"]


def main(pdf_path: Optional[str] = None) -> None:
    """
    Main entry point for the PDF number extractor.
    
    Args:
        pdf_path: Path to PDF file. If None, will parse from command line.
    """
    if pdf_path is None:
        parser = argparse.ArgumentParser(
            prog="conductor-takehome",
            description="Find the largest number in a PDF document with intelligent scaling"
        )
        parser.add_argument("pdf", help="Path to PDF file")
        parser.add_argument(
            "--top", type=int, default=1,
            help="Show top N results (default: 1 for just the largest)"
        )
        parser.add_argument(
            "--start-page", type=int, default=1,
            help="First page to scan (1-based, default: 1)"
        )
        parser.add_argument(
            "--end-page", type=int, default=None,
            help="Last page to scan (1-based, default: all pages)"
        )
        parser.add_argument(
            "--json", action="store_true",
            help="Output results as JSON"
        )
        parser.add_argument(
            "--no-scaling", action="store_true",
            help="Disable scale phrase detection (e.g., 'Dollars in Millions')"
        )
        parser.add_argument(
            "--min-scaled", type=float, default=None,
            help="Minimum scaled value to include in results"
        )
        parser.add_argument(
            "--max-scaled", type=float, default=None,
            help="Maximum scaled value to include in results"
        )
        
        args = parser.parse_args()
        pdf_path_arg = args.pdf
    else:
        # Direct function call - use defaults
        class Args:
            top = 1
            start_page = 1
            end_page = None
            json = False
            no_scaling = False
            min_scaled = None
            max_scaled = None
        args = Args()
        pdf_path_arg = pdf_path

    # Extract numbers with scaling
    hits = extract_numbers_from_pdf(
        pdf_path_arg,
        start_page=args.start_page,
        end_page=args.end_page,
        min_scaled=args.min_scaled,
        max_scaled=args.max_scaled,
    )
    
    if not hits:
        print("No numbers found in the PDF", file=__import__("sys").stderr)
        return
    
    # Get top N results
    top_hits = hits[:args.top] if args.top > 0 else hits
    
    if args.json:
        # JSON output
        results = []
        for i, hit in enumerate(top_hits, 1):
            results.append({
                "rank": i,
                "scaled_value": hit.scaled_value,
                "raw_value": hit.raw_value,
                "raw_text": hit.raw_text,
                "page": hit.page_num,
                "units": hit.units,
                "scale_name": hit.scale_name,
                "scale_phrase": hit.scale_phrase,
                "bbox": hit.bbox,
            })
        print(json.dumps(results, indent=2))
    else:
        # Human-readable output
        if args.top == 1:
            hit = top_hits[0]
            print(f"Largest number: ${hit.scaled_value:,.0f}")
            print(f"  Raw value: {hit.raw_value} ('{hit.raw_text}')")
            print(f"  Page: {hit.page_num}")
            if hit.scale_name:
                print(f"  Scale: {hit.scale_name} ({hit.scale_phrase})")
            else:
                print("  Scale: none")
            print(f"  Units: {hit.units}")
        else:
            print(f"Top {len(top_hits)} numbers found:")
            for i, hit in enumerate(top_hits, 1):
                scale_info = f" (scale: {hit.scale_name})" if hit.scale_name else ""
                print(f"  #{i}: ${hit.scaled_value:,.0f} - '{hit.raw_text}' on page {hit.page_num}{scale_info}")


if __name__ == "__main__":
    main()