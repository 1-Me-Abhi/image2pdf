# image2pdf

A fast, flexible command-line tool and Python library to convert images to PDF documents.

Supports **PNG, JPG/JPEG, WEBP, BMP, TIFF, GIF** with natural filename sorting, mobile photo auto-rotation (EXIF), proper transparency rendering, customizable page layouts (A4, Letter, custom dimensions), margins, downscaling, and compression.

---

## 🚀 Quick Start

The tool is already installed and available on your PATH:

```bash
# Convert one or more images
image2pdf image1.jpg image2.png -o document.pdf

# Or use the shortcut alias
img2pdf image1.jpg image2.png -o document.pdf
```

---

## 🌟 Key Features

- **Natural Sorting**: `img1.png`, `img2.png`, `img10.png` are automatically ordered in human-expected numerical sequence instead of lexicographical order.
- **EXIF Auto-Rotation**: Smartphone photos taken at 90° or 270° angles are automatically oriented upright.
- **Proper Transparency Handling**: Transparent PNG/WEBP images are composited onto a clean background (customizable) rather than rendering black boxes.
- **Page Layout & Sizing**:
  - `fit` (default): Page dimensions match each image natively.
  - Standard paper formats: `a4`, `a3`, `a5`, `letter`, `legal`, etc.
  - Custom page dimensions: e.g. `210x297mm`, `8.5x11in`, `1200x800px`.
  - Margins: e.g. `10mm`, `0.5in`, `20pt`.
  - Fit modes: `contain` (aspect ratio preserved, letterboxed), `fill` (crops to fill), `original`.
- **Directory & Glob Support**: Convert folders with `--recursive` (`-r`) or glob patterns like `"scans/**/*.jpg"`.
- **Optimization & Color Modes**:
  - Color (`rgb`), Grayscale (`gray`), or 1-bit Monochrome (`bw`).
  - Adjustable quality (`-q 85`) and DPI (`--dpi 300`).
  - Max dimension limit (`--max-dim 1920`) or scaling (`--scale 0.5`).
- **Multi-Frame Support**: Split multi-frame GIF or multi-page TIFF images into separate PDF pages with `--all-frames`.
- **Dry-run Mode**: Preview matched images and page counts before writing to disk.

---

## 📖 CLI Usage & Examples

### Basic Conversion

```bash
# Convert multiple images in order
image2pdf page1.jpg page2.jpg page3.png -o document.pdf

# Convert an entire directory of scans
image2pdf ./scans/ -o scans.pdf

# Convert all PNG files recursively
image2pdf "assets/**/*.png" -r -o assets.pdf
```

### Page Layout & Sizing

```bash
# Standard A4 with 10mm margins
image2pdf scans/ -p a4 -m 10mm -o a4_document.pdf

# US Letter in landscape orientation
image2pdf photos/ -p letter --orientation landscape -o album.pdf

# Custom dimensions (e.g. 4x6 inch photo prints)
image2pdf ./prints/ -p 4x6in -m 5mm -o prints.pdf
```

### Compression & Size Reduction

```bash
# Black and white document (1-bit bilevel)
image2pdf ./book_pages/ --mode bw -o compressed_book.pdf

# Grayscale with 80% JPEG quality
image2pdf ./notes/ --mode gray -q 80 -o notes.pdf

# Downscale high-resolution images to max 1920px
image2pdf ./raw_photos/ --max-dim 1920 -q 85 -o gallery.pdf
```

### Sorting Options

```bash
# Sort by file modification date
image2pdf ./photos/ --sort date -o timeline.pdf

# Alphabetical sort
image2pdf ./files/ --sort name -o sorted.pdf

# Reverse order
image2pdf ./pages/ --reverse -o reversed.pdf
```

### Preview (Dry Run)

```bash
image2pdf ./scans/ --dry-run
```

---

## 🐍 Python API Usage

You can also import and use `image2pdf` directly in Python scripts:

```python
from image2pdf import convert_images_to_pdf, ConversionOptions

# Simple conversion
output_path, num_pages = convert_images_to_pdf(
    sources=["photo1.jpg", "photo2.png"],
    output_pdf="output.pdf"
)

# Advanced conversion with options
opts = ConversionOptions(
    page_size="a4",
    margin="10mm",
    fit="contain",
    orientation="auto",
    mode="rgb",
    quality=90,
    dpi=150.0,
    sort="natural",
)

output_path, num_pages = convert_images_to_pdf(
    sources=["./scans/"],
    output_pdf="scanned_document.pdf",
    options=opts,
    recursive=True
)

print(f"Created {output_path} with {num_pages} pages.")
```

---

## 🧪 Running Tests

```bash
cd /home/abhi/image2pdf
python3 -m unittest discover -s tests -v
```
