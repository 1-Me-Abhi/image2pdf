"""Core image conversion engine for image2pdf."""

import glob
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Callable

from PIL import Image, ImageOps

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

from .units import parse_page_size, parse_length

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif",
    ".gif", ".ppm", ".pnm", ".pgm", ".jfif", ".ico", ".heic",
    ".heif", ".avif"
}


def natural_sort_key(s: str) -> list:
    """Sort strings containing numbers in human natural order (e.g. img1, img2, img10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]


@dataclass
class ConversionOptions:
    """Options configuring image to PDF conversion."""
    page_size: Optional[str] = None  # None / 'fit' / 'a4' / 'letter' / '210x297mm'
    orientation: str = "auto"        # 'auto', 'portrait', 'landscape'
    fit: str = "contain"             # 'contain', 'fill', 'original'
    margin: str = "0pt"              # '0', '10mm', '0.5in', etc.
    bg_color: str = "white"          # 'white', 'black', or '#RRGGBB'
    mode: str = "rgb"                # 'rgb', 'grayscale' ('gray'), 'bw' (1-bit)
    quality: int = 90                # JPEG quality (1-100)
    optimize: bool = True            # Optimize PDF size
    dpi: float = 150.0               # DPI resolution for rendering & PDF metadata
    max_dim: Optional[int] = None    # Max width or height in pixels
    scale: Optional[float] = None    # Scale factor (e.g. 0.5)
    all_frames: bool = False         # Process all frames of multi-frame images (GIF, TIFF)
    sort: str = "natural"            # 'natural', 'name', 'date', 'none'
    reverse_sort: bool = False       # Reverse sorting order
    dry_run: bool = False            # Preview only, don't write output


def parse_color(color_str: str) -> Tuple[int, int, int]:
    """Parse color name or hex string into RGB tuple."""
    color_str = color_str.strip().lower()
    color_map = {
        "white": (255, 255, 255),
        "black": (0, 0, 0),
        "gray": (128, 128, 128),
        "grey": (128, 128, 128),
        "transparent": (255, 255, 255),
    }
    if color_str in color_map:
        return color_map[color_str]

    if color_str.startswith("#"):
        hex_val = color_str.lstrip("#")
        if len(hex_val) == 3:
            hex_val = "".join([c * 2 for c in hex_val])
        if len(hex_val) == 6:
            return (
                int(hex_val[0:2], 16),
                int(hex_val[2:4], 16),
                int(hex_val[4:6], 16),
            )

    try:
        from PIL import ImageColor
        return ImageColor.getrgb(color_str)
    except Exception:
        raise ValueError(f"Invalid background color: '{color_str}'")


def find_images(
    sources: List[str],
    recursive: bool = False,
    sort_mode: str = "natural",
    reverse: bool = False,
) -> List[str]:
    """Resolve and expand file paths, directories, and glob patterns into a sorted list of image file paths."""
    resolved_paths: List[str] = []

    for src in sources:
        # Check if direct file
        if os.path.isfile(src):
            resolved_paths.append(os.path.abspath(src))
            continue

        # Check if directory
        if os.path.isdir(src):
            pattern = "**/*" if recursive else "*"
            for p in Path(src).glob(pattern):
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS and not p.name.startswith("."):
                    resolved_paths.append(str(p.resolve()))
            continue

        # Check if glob pattern
        globbed = glob.glob(src, recursive=recursive)
        if globbed:
            for g in globbed:
                if os.path.isfile(g) and Path(g).suffix.lower() in SUPPORTED_EXTENSIONS and not Path(g).name.startswith("."):
                    resolved_paths.append(os.path.abspath(g))
            continue

        # If not found
        if src.startswith("-"):
            raise ValueError(f"Unrecognized option '{src}'. Did you mean '-o' for output?")
        raise FileNotFoundError(f"Input path or pattern not found: '{src}'")

    # Remove duplicates preserving order
    seen = set()
    unique_paths = []
    for p in resolved_paths:
        if p not in seen:
            seen.add(p)
            unique_paths.append(p)

    # Sort
    if sort_mode == "natural":
        unique_paths.sort(key=lambda x: natural_sort_key(os.path.basename(x)), reverse=reverse)
    elif sort_mode == "name":
        unique_paths.sort(key=lambda x: os.path.basename(x).lower(), reverse=reverse)
    elif sort_mode == "date":
        unique_paths.sort(key=lambda x: os.path.getmtime(x), reverse=reverse)
    elif sort_mode == "none":
        if reverse:
            unique_paths.reverse()

    return unique_paths


def process_single_image(
    img: Image.Image,
    options: ConversionOptions,
    bg_rgb: Tuple[int, int, int],
) -> Image.Image:
    """Preprocess image: Exif auto-rotate, alpha flattening, scaling, and color mode conversion."""
    # 1. Correct orientation via EXIF
    img = ImageOps.exif_transpose(img)

    # 2. Flatten transparency over bg_color
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img_rgba = img.convert("RGBA")
        background = Image.new("RGBA", img_rgba.size, (*bg_rgb, 255))
        background.paste(img_rgba, (0, 0), img_rgba)
        img = background.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # 3. Scaling / Resize if requested
    w, h = img.size
    if options.scale and options.scale > 0 and options.scale != 1.0:
        new_w = max(1, int(round(w * options.scale)))
        new_h = max(1, int(round(h * options.scale)))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    elif options.max_dim and options.max_dim > 0:
        max_side = max(w, h)
        if max_side > options.max_dim:
            factor = options.max_dim / float(max_side)
            new_w = max(1, int(round(w * factor)))
            new_h = max(1, int(round(h * factor)))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # 4. Color mode
    mode = options.mode.lower()
    if mode in ("gray", "grayscale", "l"):
        img = img.convert("L")
    elif mode in ("bw", "1"):
        img = img.convert("L").point(lambda x: 255 if x > 128 else 0, mode="1")
    else:
        # Default RGB
        if img.mode != "RGB":
            img = img.convert("RGB")

    return img


def render_to_page(
    img: Image.Image,
    options: ConversionOptions,
    bg_rgb: Tuple[int, int, int],
) -> Image.Image:
    """Fit image onto target page size or return original sized image if page_size is 'fit'."""
    parsed_page = parse_page_size(options.page_size, dpi=options.dpi)

    if parsed_page is None:
        # Native image dimensions: return image directly
        return img

    page_w_pt, page_h_pt = parsed_page
    img_w, img_h = img.size

    # Orientation handling
    orient = options.orientation.lower()
    if orient == "auto":
        is_img_landscape = img_w > img_h
        is_page_landscape = page_w_pt > page_h_pt
        if is_img_landscape != is_page_landscape:
            page_w_pt, page_h_pt = page_h_pt, page_w_pt
    elif orient == "landscape":
        if page_w_pt < page_h_pt:
            page_w_pt, page_h_pt = page_h_pt, page_w_pt
    elif orient == "portrait":
        if page_w_pt > page_h_pt:
            page_w_pt, page_h_pt = page_h_pt, page_w_pt

    # Parse margin
    margin_pt = parse_length(options.margin, dpi=options.dpi)
    margin_px = int(round(margin_pt * (options.dpi / 72.0)))

    # Convert page dimensions from pt to target pixel dimensions at given DPI
    page_w_px = max(1, int(round(page_w_pt * (options.dpi / 72.0))))
    page_h_px = max(1, int(round(page_h_pt * (options.dpi / 72.0))))

    # Available printable area
    avail_w = max(1, page_w_px - 2 * margin_px)
    avail_h = max(1, page_h_px - 2 * margin_px)

    fit_mode = options.fit.lower()

    if fit_mode == "contain":
        scale_factor = min(avail_w / img_w, avail_h / img_h)
        scaled_w = max(1, int(round(img_w * scale_factor)))
        scaled_h = max(1, int(round(img_h * scale_factor)))
        img_resized = img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
        offset_x = margin_px + (avail_w - scaled_w) // 2
        offset_y = margin_px + (avail_h - scaled_h) // 2

    elif fit_mode == "fill":
        # Scale to fill entire available area (cropping excess)
        scale_factor = max(avail_w / img_w, avail_h / img_h)
        scaled_w = max(1, int(round(img_w * scale_factor)))
        scaled_h = max(1, int(round(img_h * scale_factor)))
        img_resized = img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
        crop_x = (scaled_w - avail_w) // 2
        crop_y = (scaled_h - avail_h) // 2
        img_resized = img_resized.crop((crop_x, crop_y, crop_x + avail_w, crop_y + avail_h))
        offset_x = margin_px
        offset_y = margin_px

    elif fit_mode == "original":
        # Keep original image size, center it
        img_resized = img
        offset_x = margin_px + (avail_w - img_resized.width) // 2
        offset_y = margin_px + (avail_h - img_resized.height) // 2

    else:
        raise ValueError(f"Unknown fit mode: '{options.fit}'. Choose from 'contain', 'fill', 'original'.")

    # Create canvas
    canvas_mode = img.mode
    bg_fill = 255 if canvas_mode in ("L", "1") else bg_rgb
    canvas = Image.new(canvas_mode, (page_w_px, page_h_px), bg_fill)
    canvas.paste(img_resized, (offset_x, offset_y))
    return canvas


def convert_images_to_pdf(
    sources: List[str],
    output_pdf: str,
    options: Optional[ConversionOptions] = None,
    recursive: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Tuple[str, int]:
    """Convert input images to a single PDF document.

    Returns:
        Tuple of (output_pdf_path, total_pages_written)
    """
    if options is None:
        options = ConversionOptions()

    image_paths = find_images(
        sources=sources,
        recursive=recursive,
        sort_mode=options.sort,
        reverse=options.reverse_sort,
    )

    if not image_paths:
        raise ValueError("No matching images found to convert.")

    bg_rgb = parse_color(options.bg_color)
    processed_pages: List[Image.Image] = []

    total_files = len(image_paths)

    for idx, path in enumerate(image_paths, start=1):
        if progress_callback:
            progress_callback(idx, total_files, path)

        with Image.open(path) as img:
            if options.all_frames and getattr(img, "n_frames", 1) > 1:
                for frame_idx in range(img.n_frames):
                    img.seek(frame_idx)
                    frame = img.copy()
                    processed = process_single_image(frame, options, bg_rgb)
                    page = render_to_page(processed, options, bg_rgb)
                    processed_pages.append(page)
            else:
                processed = process_single_image(img, options, bg_rgb)
                page = render_to_page(processed, options, bg_rgb)
                processed_pages.append(page)

    if options.dry_run:
        # Don't save, just return count
        for p in processed_pages:
            p.close()
        return output_pdf, len(processed_pages)

    out_path = Path(output_pdf).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    first_page = processed_pages[0]
    remaining_pages = processed_pages[1:] if len(processed_pages) > 1 else []

    # Pillow PDF save options
    save_kwargs = {
        "format": "PDF",
        "resolution": float(options.dpi),
        "save_all": True,
        "append_images": remaining_pages,
        "optimize": options.optimize,
    }
    # Quality is only applicable for JPEG-compressed images (RGB, L), not 1-bit bilevel images
    if first_page.mode != "1":
        save_kwargs["quality"] = options.quality

    try:
        first_page.save(str(out_path), **save_kwargs)
    finally:
        for p in processed_pages:
            try:
                p.close()
            except Exception:
                pass

    return str(out_path), len(processed_pages)
