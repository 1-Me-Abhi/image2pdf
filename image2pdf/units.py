"""Unit and page dimension helpers for image2pdf."""

import re
from typing import Tuple, Optional

# Standard PDF page sizes in points (1 pt = 1/72 inch)
# Values represent (width, height) in portrait orientation.
STANDARD_PAGE_SIZES = {
    "a0": (2384.0, 3370.0),
    "a1": (1684.0, 2384.0),
    "a2": (1191.0, 1684.0),
    "a3": (842.0, 1191.0),
    "a4": (595.28, 841.89),
    "a5": (419.53, 595.28),
    "a6": (297.64, 419.53),
    "b4": (708.66, 1000.63),
    "b5": (498.90, 708.66),
    "letter": (612.0, 792.0),
    "legal": (612.0, 1008.0),
    "tabloid": (792.0, 1224.0),
    "executive": (522.0, 756.0),
}

def parse_length(val: str, dpi: float = 72.0) -> float:
    """Parse a length string (e.g. '10mm', '0.5in', '20pt', '100px', '2cm') to points (1/72 inch).

    Defaults to points if no unit is given.
    """
    if isinstance(val, (int, float)):
        return float(val)
    
    val = val.strip().lower()
    if not val:
        return 0.0

    match = re.match(r"^([0-9]*\.?[0-9]+)\s*([a-z%]*)$", val)
    if not match:
        raise ValueError(f"Invalid length format: '{val}'")

    number = float(match.group(1))
    unit = match.group(2) or "pt"

    if unit == "pt":
        return number
    elif unit == "in" or unit == "inch" or unit == "inches":
        return number * 72.0
    elif unit == "mm":
        return (number / 25.4) * 72.0
    elif unit == "cm":
        return (number / 2.54) * 72.0
    elif unit == "px":
        # At given dpi, px to inches is px / dpi, then * 72 for pt
        return (number / dpi) * 72.0
    else:
        raise ValueError(f"Unsupported unit: '{unit}' in '{val}'. Supported units: pt, mm, cm, in, px")


def parse_page_size(size_str: Optional[str], dpi: float = 72.0) -> Optional[Tuple[float, float]]:
    """Parse page size specification to (width_pt, height_pt) or None for 'fit'/'original'.

    Supports:
    - 'fit', 'original', 'auto', None -> None (use image's native size)
    - standard names: 'a4', 'letter', 'legal', etc.
    - dimensions: '210x297mm', '8.5x11in', '595x842pt', '1200x800px'
    """
    if not size_str:
        return None

    s = size_str.strip().lower()
    if s in ("fit", "original", "auto", "none"):
        return None

    if s in STANDARD_PAGE_SIZES:
        return STANDARD_PAGE_SIZES[s]

    # Check for WxH pattern
    if "x" in s:
        parts = s.split("x")
        if len(parts) == 2:
            w_str, h_str = parts[0].strip(), parts[1].strip()
            # If unit is attached to the second part (e.g. 210x297mm), inherit unit if first has none
            unit_match = re.search(r"([a-z]+)$", h_str)
            if unit_match and not re.search(r"[a-z]+$", w_str):
                w_str += unit_match.group(1)
            w = parse_length(w_str, dpi=dpi)
            h = parse_length(h_str, dpi=dpi)
            return (w, h)

    raise ValueError(
        f"Unknown page size: '{size_str}'. Choose from {list(STANDARD_PAGE_SIZES.keys())} or specify 'WIDTHxHEIGHT' (e.g. '210x297mm', '8.5x11in', 'fit')."
    )
