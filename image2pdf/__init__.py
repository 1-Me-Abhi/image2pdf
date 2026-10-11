"""image2pdf - Fast, flexible CLI and library to convert images to PDF."""

__version__ = "1.0.0"

from .converter import (
    convert_images_to_pdf,
    ConversionOptions,
    find_images,
    SUPPORTED_EXTENSIONS,
)
from .units import (
    parse_length,
    parse_page_size,
    STANDARD_PAGE_SIZES,
)

__all__ = [
    "convert_images_to_pdf",
    "ConversionOptions",
    "find_images",
    "parse_length",
    "parse_page_size",
    "SUPPORTED_EXTENSIONS",
    "STANDARD_PAGE_SIZES",
]
