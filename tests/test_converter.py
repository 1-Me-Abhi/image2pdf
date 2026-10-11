"""Tests for image2pdf CLI and converter module."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from image2pdf.converter import (
    convert_images_to_pdf,
    ConversionOptions,
    find_images,
    natural_sort_key,
)
from image2pdf.units import parse_length, parse_page_size


class TestUnits(unittest.TestCase):
    def test_parse_length(self):
        self.assertAlmostEqual(parse_length("72pt"), 72.0)
        self.assertAlmostEqual(parse_length("1in"), 72.0)
        self.assertAlmostEqual(parse_length("25.4mm"), 72.0, places=2)
        self.assertAlmostEqual(parse_length("2.54cm"), 72.0, places=2)
        self.assertAlmostEqual(parse_length("150px", dpi=150.0), 72.0)
        self.assertAlmostEqual(parse_length("0"), 0.0)

    def test_parse_page_size(self):
        self.assertIsNone(parse_page_size("fit"))
        self.assertIsNone(parse_page_size("original"))
        self.assertIsNone(parse_page_size(None))

        # A4
        a4 = parse_page_size("a4")
        self.assertIsNotNone(a4)
        self.assertAlmostEqual(a4[0], 595.28, places=1)
        self.assertAlmostEqual(a4[1], 841.89, places=1)

        # Custom dimensions
        custom = parse_page_size("100x200mm")
        self.assertIsNotNone(custom)
        self.assertAlmostEqual(custom[0], (100 / 25.4) * 72.0, places=1)
        self.assertAlmostEqual(custom[1], (200 / 25.4) * 72.0, places=1)


class TestConverter(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _create_sample_image(self, name: str, size=(100, 100), mode="RGB", color=(255, 0, 0)) -> str:
        path = os.path.join(self.test_dir, name)
        img = Image.new(mode, size, color)
        img.save(path)
        return path

    def test_natural_sort(self):
        names = ["img10.png", "img1.png", "img2.png", "img20.png"]
        sorted_names = sorted(names, key=natural_sort_key)
        self.assertEqual(sorted_names, ["img1.png", "img2.png", "img10.png", "img20.png"])

    def test_single_image_to_pdf(self):
        img_path = self._create_sample_image("test.jpg", size=(200, 150))
        out_pdf = os.path.join(self.test_dir, "output.pdf")

        pdf_path, pages = convert_images_to_pdf([img_path], out_pdf)
        self.assertTrue(os.path.exists(pdf_path))
        self.assertEqual(pages, 1)
        self.assertGreater(os.path.getsize(pdf_path), 0)

    def test_multiple_images_to_pdf(self):
        p1 = self._create_sample_image("page1.png", size=(200, 200), color=(255, 0, 0))
        p2 = self._create_sample_image("page2.jpg", size=(300, 150), color=(0, 255, 0))
        p3 = self._create_sample_image("page10.png", size=(150, 300), color=(0, 0, 255))
        out_pdf = os.path.join(self.test_dir, "multi.pdf")

        pdf_path, pages = convert_images_to_pdf([p1, p2, p3], out_pdf)
        self.assertTrue(os.path.exists(pdf_path))
        self.assertEqual(pages, 3)

    def test_transparent_png(self):
        # Create RGBA image with transparent background
        path = os.path.join(self.test_dir, "transparent.png")
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        # Draw a red box in the middle
        for x in range(25, 75):
            for y in range(25, 75):
                img.putpixel((x, y), (255, 0, 0, 255))
        img.save(path)

        out_pdf = os.path.join(self.test_dir, "transparent.pdf")
        pdf_path, pages = convert_images_to_pdf([path], out_pdf)
        self.assertTrue(os.path.exists(pdf_path))
        self.assertEqual(pages, 1)

    def test_standard_page_size_and_margin(self):
        img_path = self._create_sample_image("scan.jpg", size=(800, 600))
        out_pdf = os.path.join(self.test_dir, "a4.pdf")

        opts = ConversionOptions(page_size="a4", margin="10mm", fit="contain")
        pdf_path, pages = convert_images_to_pdf([img_path], out_pdf, options=opts)
        self.assertTrue(os.path.exists(pdf_path))
        self.assertEqual(pages, 1)

    def test_color_modes(self):
        img_path = self._create_sample_image("color.png", size=(100, 100), color=(100, 150, 200))

        # Grayscale
        out_gray = os.path.join(self.test_dir, "gray.pdf")
        opts_gray = ConversionOptions(mode="gray")
        _, p_gray = convert_images_to_pdf([img_path], out_gray, options=opts_gray)
        self.assertEqual(p_gray, 1)
        self.assertTrue(os.path.exists(out_gray))

        # Monochrome (bw)
        out_bw = os.path.join(self.test_dir, "bw.pdf")
        opts_bw = ConversionOptions(mode="bw")
        _, p_bw = convert_images_to_pdf([img_path], out_bw, options=opts_bw)
        self.assertEqual(p_bw, 1)
        self.assertTrue(os.path.exists(out_bw))

    def test_directory_discovery_and_recursion(self):
        sub_dir = os.path.join(self.test_dir, "nested")
        os.makedirs(sub_dir)
        self._create_sample_image("img1.jpg")
        self._create_sample_image("nested/img2.jpg")

        # Non-recursive
        found = find_images([self.test_dir], recursive=False)
        self.assertEqual(len(found), 1)

        # Recursive
        found_rec = find_images([self.test_dir], recursive=True)
        self.assertEqual(len(found_rec), 2)

    def test_dry_run(self):
        img_path = self._create_sample_image("dry.jpg")
        out_pdf = os.path.join(self.test_dir, "dry.pdf")
        opts = ConversionOptions(dry_run=True)
        _, count = convert_images_to_pdf([img_path], out_pdf, options=opts)
        self.assertEqual(count, 1)
        # Should not write file in dry-run
        self.assertFalse(os.path.exists(out_pdf))


    def test_fit_and_orientation(self):
        # Landscape image on portrait page
        img_path = self._create_sample_image("landscape.jpg", size=(800, 400))

        # Fit contain on landscape
        out_land = os.path.join(self.test_dir, "landscape.pdf")
        opts = ConversionOptions(page_size="a4", orientation="landscape", fit="contain")
        _, count = convert_images_to_pdf([img_path], out_land, options=opts)
        self.assertEqual(count, 1)
        self.assertTrue(os.path.exists(out_land))

        # Fit fill on portrait
        out_port = os.path.join(self.test_dir, "portrait.pdf")
        opts_fill = ConversionOptions(page_size="letter", orientation="portrait", fit="fill")
        _, count_fill = convert_images_to_pdf([img_path], out_port, options=opts_fill)
        self.assertEqual(count_fill, 1)
        self.assertTrue(os.path.exists(out_port))

    def test_scale_and_max_dim(self):
        img_path = self._create_sample_image("large.png", size=(1000, 500))

        # Scale factor
        out_scale = os.path.join(self.test_dir, "scale.pdf")
        opts_scale = ConversionOptions(scale=0.5)
        _, c1 = convert_images_to_pdf([img_path], out_scale, options=opts_scale)
        self.assertEqual(c1, 1)
        self.assertTrue(os.path.exists(out_scale))

        # Max dimension
        out_max = os.path.join(self.test_dir, "maxdim.pdf")
        opts_max = ConversionOptions(max_dim=200)
        _, c2 = convert_images_to_pdf([img_path], out_max, options=opts_max)
        self.assertEqual(c2, 1)
        self.assertTrue(os.path.exists(out_max))

    def test_multi_frame_gif(self):
        # Create 3-frame GIF
        gif_path = os.path.join(self.test_dir, "anim.gif")
        frames = [
            Image.new("RGB", (50, 50), (255, 0, 0)),
            Image.new("RGB", (50, 50), (0, 255, 0)),
            Image.new("RGB", (50, 50), (0, 0, 255)),
        ]
        frames[0].save(gif_path, save_all=True, append_images=frames[1:], loop=0)

        out_gif = os.path.join(self.test_dir, "gif.pdf")
        opts = ConversionOptions(all_frames=True)
        _, pages = convert_images_to_pdf([gif_path], out_gif, options=opts)
        self.assertEqual(pages, 3)
        self.assertTrue(os.path.exists(out_gif))

    def test_missing_files_error(self):
        with self.assertRaises(FileNotFoundError):
            find_images(["/path/does/not/exist/image.png"])


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.img1 = os.path.join(self.test_dir, "a1.jpg")
        self.img2 = os.path.join(self.test_dir, "a2.png")
        Image.new("RGB", (50, 50), (255, 0, 0)).save(self.img1)
        Image.new("RGB", (50, 50), (0, 255, 0)).save(self.img2)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_cli_execution(self):
        out_pdf = os.path.join(self.test_dir, "cli_output.pdf")
        cmd = [
            "image2pdf",
            self.img1,
            self.img2,
            "-o", out_pdf,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, msg=f"CLI failed: {res.stderr}")
        self.assertTrue(os.path.exists(out_pdf))

    def test_cli_dry_run(self):
        cmd = [
            "image2pdf",
            self.img1,
            "--dry-run",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Dry Run", res.stdout)


if __name__ == "__main__":
    unittest.main()
