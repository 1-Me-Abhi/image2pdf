"""Command Line Interface for image2pdf."""

import argparse
import os
import sys
import time
from pathlib import Path

from . import __version__
from .converter import (
    convert_images_to_pdf,
    ConversionOptions,
    find_images,
    SUPPORTED_EXTENSIONS,
)
from .units import STANDARD_PAGE_SIZES


def format_size(bytes_num: int) -> str:
    """Format bytes into human readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}" if unit != "B" else f"{bytes_num} B"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} TB"


def build_parser() -> argparse.ArgumentParser:
    description = (
        "image2pdf - Convert images to a single high-quality PDF document.\n"
        "Supports PNG, JPG, WEBP, BMP, TIFF, GIF with smart sorting, auto-orientation,\n"
        "transparency handling, custom page layouts, and optimization."
    )

    epilog = """Examples:
  # Convert multiple images in natural order to output.pdf
  image2pdf photo1.jpg photo2.png photo10.jpg -o my_doc.pdf

  # Convert an entire folder of scans to A4 PDF with 10mm margins
  image2pdf ./scans/ -p a4 -m 10mm -o document.pdf

  # Convert all webp/png files recursively matching glob
  image2pdf "images/**/*.png" -r -o bundle.pdf

  # Convert to black & white (1-bit) with maximum compression
  image2pdf pages/ --mode bw --quality 80 -o compressed_book.pdf

  # Preview images that would be included without writing file
  image2pdf ./photos/ --dry-run
"""

    parser = argparse.ArgumentParser(
        prog="image2pdf",
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "inputs",
        nargs="*",
        help="Input image files, directories, or glob patterns.",
    )

    parser.add_argument(
        "-o", "-0", "--output",
        default=None,
        help="Path for output PDF file. Defaults to 'output.pdf' or '<input_name>.pdf'.",
    )

    page_group = parser.add_argument_group("Page Layout Options")
    page_group.add_argument(
        "-p", "--page-size",
        default="fit",
        help="Page format: 'fit' (default: match image size), standard paper size "
             f"({', '.join(list(STANDARD_PAGE_SIZES.keys())[:6])}, letter, legal), "
             "or custom dimension 'WIDTHxHEIGHT' (e.g. '210x297mm', '8.5x11in', '1200x800px').",
    )
    page_group.add_argument(
        "--orientation",
        choices=["auto", "portrait", "landscape"],
        default="auto",
        help="Page orientation when a fixed page size is used (default: auto).",
    )
    page_group.add_argument(
        "--fit",
        choices=["contain", "fill", "original"],
        default="contain",
        help="How to scale image inside page margins: contain (letterbox), fill (crop), original (default: contain).",
    )
    page_group.add_argument(
        "-m", "--margin",
        default="0pt",
        help="Page margin (e.g. '10mm', '0.5in', '20pt', default: 0pt).",
    )
    page_group.add_argument(
        "--bg-color",
        default="white",
        help="Background color for margins and transparent images (e.g. 'white', 'black', '#f0f0f0', default: white).",
    )

    img_group = parser.add_argument_group("Image & Optimization Options")
    img_group.add_argument(
        "--mode",
        choices=["rgb", "grayscale", "gray", "bw"],
        default="rgb",
        help="Color mode: rgb (full color), grayscale (gray), bw (1-bit monochrome).",
    )
    img_group.add_argument(
        "-q", "--quality",
        type=int,
        default=90,
        help="JPEG quality level from 1 to 100 (default: 90).",
    )
    img_group.add_argument(
        "--dpi",
        type=float,
        default=150.0,
        help="Target rendering DPI for fixed pages and PDF metadata (default: 150.0).",
    )
    img_group.add_argument(
        "--max-dim",
        type=int,
        default=None,
        help="Maximum width or height in pixels (downscales larger images preserving aspect ratio).",
    )
    img_group.add_argument(
        "--scale",
        type=float,
        default=None,
        help="Scale factor for images (e.g. 0.5 to halve image dimensions).",
    )
    img_group.add_argument(
        "--no-optimize",
        action="store_false",
        dest="optimize",
        default=True,
        help="Disable PDF file size optimization.",
    )
    img_group.add_argument(
        "--all-frames",
        action="store_true",
        help="Include all frames for animated GIFs or multi-page TIFFs as separate PDF pages.",
    )

    sort_group = parser.add_argument_group("Discovery & Sorting Options")
    sort_group.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Recursively scan subdirectories for images.",
    )
    sort_group.add_argument(
        "--sort",
        choices=["natural", "name", "date", "none"],
        default="natural",
        help="Sort order for images: natural (1,2,10), name (alphabetical), date (modified time), none (default: natural).",
    )
    sort_group.add_argument(
        "--reverse",
        action="store_true",
        help="Reverse the sort order.",
    )

    misc_group = parser.add_argument_group("Other Options")
    misc_group.add_argument(
        "--dry-run",
        action="store_true",
        help="List resolved images and count pages without generating the PDF.",
    )
    misc_group.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable detailed progress and debug output.",
    )
    misc_group.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress normal console output.",
    )
    misc_group.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    is_tty = sys.stdout.isatty() and not args.quiet
    use_color = is_tty and os.environ.get("NO_COLOR") is None

    # Helper styling
    def green(text: str) -> str:
        return f"\033[32m{text}\033[0m" if use_color else text

    def cyan(text: str) -> str:
        return f"\033[36m{text}\033[0m" if use_color else text

    def yellow(text: str) -> str:
        return f"\033[33m{text}\033[0m" if use_color else text

    def red(text: str) -> str:
        return f"\033[31m{text}\033[0m" if use_color else text

    def bold(text: str) -> str:
        return f"\033[1m{text}\033[0m" if use_color else text

    if not args.inputs:
        sys.stderr.write(
            f"{red('Error:')} No input files or folders provided.\n\n"
            f"{bold('Quick Examples:')}\n"
            f"  {cyan('img2pdf *.jpg -o photos.pdf')}          (Convert all JPGs in current folder)\n"
            f"  {cyan('img2pdf . -o downloads.pdf')}           (Convert all images in current folder)\n"
            f"  {cyan('img2pdf IMG_1230.jpg -o document.pdf')}  (Convert specific image)\n\n"
            f"Run {bold('img2pdf --help')} to see all available options.\n"
        )
        return 1

    # Determine default output name if none provided
    output_pdf = args.output
    if not output_pdf:
        if len(args.inputs) == 1:
            first_input = args.inputs[0].rstrip("/\\")
            if os.path.isdir(first_input):
                output_pdf = f"{os.path.basename(first_input)}.pdf"
            else:
                stem = Path(first_input).stem
                output_pdf = f"{stem}.pdf"
        else:
            output_pdf = "output.pdf"

    # Validate output extension
    if not output_pdf.lower().endswith(".pdf"):
        output_pdf += ".pdf"

    options = ConversionOptions(
        page_size=args.page_size,
        orientation=args.orientation,
        fit=args.fit,
        margin=args.margin,
        bg_color=args.bg_color,
        mode=args.mode,
        quality=args.quality,
        optimize=args.optimize,
        dpi=args.dpi,
        max_dim=args.max_dim,
        scale=args.scale,
        all_frames=args.all_frames,
        sort=args.sort,
        reverse_sort=args.reverse,
        dry_run=args.dry_run,
    )

    try:
        # Pre-check images found
        image_paths = find_images(
            sources=args.inputs,
            recursive=args.recursive,
            sort_mode=options.sort,
            reverse=options.reverse_sort,
        )
    except Exception as e:
        sys.stderr.write(f"{red('Error:')} {e}\n")
        return 1

    if not image_paths:
        sys.stderr.write(f"{red('Error:')} No matching images found. Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}\n")
        return 1

    if args.dry_run:
        print(bold(cyan(f"Dry Run: Found {len(image_paths)} image(s) to convert:")))
        for i, p in enumerate(image_paths, start=1):
            file_sz = format_size(os.path.getsize(p))
            print(f"  [{i:3d}] {p} ({file_sz})")
        print(f"\nTarget output: {bold(output_pdf)}")
        print(f"Page size: {options.page_size} | Fit: {options.fit} | Margin: {options.margin} | Mode: {options.mode}")
        return 0

    if not args.quiet:
        print(bold(cyan(f"image2pdf v{__version__}")) + f" - Converting {bold(str(len(image_paths)))} image(s) to PDF...")

    start_time = time.time()

    def on_progress(idx: int, total: int, file_path: str):
        if args.verbose and not args.quiet:
            filename = os.path.basename(file_path)
            print(f"  [{idx}/{total}] Processing {filename}...")
        elif not args.quiet and sys.stdout.isatty():
            percent = int((idx / total) * 100)
            bar_len = 25
            filled = int(bar_len * idx // total)
            bar = "=" * filled + "-" * (bar_len - filled)
            sys.stdout.write(f"\r  [{bar}] {percent}% ({idx}/{total})")
            sys.stdout.flush()

    try:
        out_file, total_pages = convert_images_to_pdf(
            sources=args.inputs,
            output_pdf=output_pdf,
            options=options,
            recursive=args.recursive,
            progress_callback=on_progress,
        )
    except Exception as e:
        if not args.quiet and sys.stdout.isatty():
            sys.stdout.write("\n")
        sys.stderr.write(f"{red('Conversion Failed:')} {e}\n")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    elapsed = time.time() - start_time

    if not args.quiet:
        if sys.stdout.isatty():
            sys.stdout.write("\n")
        out_sz = format_size(os.path.getsize(out_file))
        print(green(bold("✓ Successfully created PDF:")) + f" {bold(out_file)}")
        print(f"  Pages: {bold(str(total_pages))} | Size: {out_sz} | Time: {elapsed:.2f}s")

    return 0


if __name__ == "__main__":
    sys.exit(main())
