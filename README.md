
# ConductorAI Take-Home Project: PDF Number Extractor

Find the largest number in PDF documents with intelligent scaling support.

## Problem Solved

This tool extracts and ranks numbers from PDF documents, with special handling for scaled values like "Dollars in Millions". It correctly identifies that a raw value of `30,704.1` in a table marked "Dollars in Millions" represents **$30.7 billion**.

## Results

**Largest number found in `air_force_budget.pdf`: $30,704,100,000 (≈$30.7 billion)**
- Raw value: 30,704.1 
- Scale: "Dollars in Millions" 
- Location: Total Revenue FY 2025, AFWCF Financial Summary, Page 13

## Features

- **Scale Detection**: Automatically detects phrases like "Dollars in Millions", "($M)", "(in billions)"
- **Table-Scoped Scaling**: Different tables can have different scales on the same page
- **Unit Classification**: Prevents scaling headcount/personnel numbers (people vs money)
- **Percentage Filtering**: Ignores percentage values from ranking
- **Robust Number Parsing**: Handles $, commas, decimals, negative values (parentheses), footnotes
- **Visual Debugging**: Generates annotated PDF images with bounding boxes

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd conductor-takehome

# That's it! uv run will automatically install dependencies when you run the tool
```

## Usage

### Command Line Interface

```bash
# Find the single largest number
uv run conductor-takehome air_force_budget.pdf

# Get top 5 results
uv run conductor-takehome air_force_budget.pdf --top 5

# Scan specific page range
uv run conductor-takehome air_force_budget.pdf --start-page 10 --end-page 20

# JSON output for programmatic use
uv run conductor-takehome air_force_budget.pdf --json

# Disable scaling (raw values only)
uv run conductor-takehome air_force_budget.pdf --no-scaling
```

### Python API

```python
from conductor_takehome import find_largest_number, extract_numbers_from_pdf

# Find the single largest number
result = find_largest_number("air_force_budget.pdf")
if result:
    print(f"Largest: ${result.scaled_value:,.0f}")
    print(f"Raw: {result.raw_value} ('{result.raw_text}')")
    print(f"Page: {result.page_num}")
    print(f"Scale: {result.scale_name}")

# Get all numbers, sorted by scaled value
all_numbers = extract_numbers_from_pdf("air_force_budget.pdf")
for hit in all_numbers[:10]:  # Top 10
    print(f"${hit.scaled_value:,.0f} - {hit.raw_text} (page {hit.page_num})")
```

## How It Works

1. **PDF Text Extraction**: Uses `pdfplumber` to extract words with precise bounding boxes
2. **Number Recognition**: Regex-based parsing handles currency symbols, thousands separators, decimals
3. **Scale Detection**: Searches for phrases like "Dollars in Millions" at page and table levels
4. **Table Analysis**: Finds table boundaries and applies table-specific scaling
5. **Unit Classification**: Distinguishes between monetary values and headcount/personnel numbers
6. **Smart Filtering**: Removes percentages and applies configurable thresholds
7. **Ranking**: Sorts by scaled value to find the truly largest numbers

## Architecture

```
src/conductor_takehome/
├── __init__.py          # Main API and CLI entry point
├── extractor.py         # Core number extraction and ranking logic
├── scale.py            # Scale phrase detection ("Dollars in Millions")
└── filters.py          # Pattern definitions and filtering logic
```

### Key Classes

**`NumberHit`**: Dataclass representing a found number with metadata
- `raw_value`: Original parsed number
- `scaled_value`: Number after applying scale factor
- `raw_text`: Original text token
- `page_num`: PDF page number (1-based)
- `scale_name`: Detected scale ("millions", "billions", etc.)
- `scale_phrase`: Actual phrase found ("Dollars in Millions")
- `units`: Classification ("money", "people", "unknown")
- `bbox`: Bounding box coordinates

## Configuration

The extractor supports various parameters:

- `start_page`/`end_page`: Page range to scan
- `top_n`: Number of results to return
- `apply_scaling`: Enable/disable scale detection
- `x_tolerance`/`y_tolerance`: Word extraction tolerances
- `min_scaled`/`max_scaled`: Value thresholds for filtering

## Development

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Interactive development
jupyter lab playground.ipynb
```

The `playground.ipynb` notebook contains the original development work and visual debugging tools.

## Performance

- Processes the 120-page Air Force budget PDF in ~2-3 seconds
- Memory efficient streaming approach
- Handles complex table layouts and multi-column text

## Visual Debugging

The notebook includes visual debugging features that render PDF pages with colored bounding boxes:
- **Red**: Found numbers
- **Blue**: Scale phrases  
- **Green**: Table boundaries
- **Light Gray**: All text (context)

## License

MIT License - see LICENSE file for details.