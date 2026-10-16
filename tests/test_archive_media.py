import subprocess
import tempfile
import unittest
from pathlib import Path
from pulse.archive_media import portable_image

class PublisherImageTests(unittest.TestCase):
    def test_valid_bitmap_bytes_are_preserved(self):
        body=Path('site/assets/covers/teknoloji-768.webp').read_bytes()
        self.assertEqual(portable_image(body,'image/webp'),(body,'.webp'))

    def test_avif_is_decoded_to_portable_webp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.avif'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=32x32','-frames:v','1','-c:v','libaom-av1','-still-picture','1','-cpu-used','8',str(path)],check=True,capture_output=True)
            body,suffix=portable_image(path.read_bytes(),'image/avif')
            self.assertEqual(suffix,'.webp');self.assertEqual(body[8:12],b'WEBP')

    def test_self_contained_svg_is_preserved(self):
        body=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><defs><linearGradient id="g"/></defs><path fill="url(#g)" d="M0 0h10v10Z"/></svg>'
        self.assertEqual(portable_image(body,'image/svg+xml'),(body,'.svg'))

    def test_active_external_and_entity_svg_are_blocked(self):
        for content in [b'<script/>',b'<image href="https://example.com/x.png"/>',b'<path onclick="alert(1)"/>',b'<style>@import "https://example.com/style";</style>',b'<path fill="url(file:///etc/passwd)"/>',b'<foreignObject/>']:
            with self.subTest(content=content),self.assertRaises(ValueError):
                portable_image(b'<svg xmlns="http://www.w3.org/2000/svg">'+content+b'</svg>','image/svg+xml')
        with self.assertRaises(ValueError):portable_image(b'<!DOCTYPE svg><svg/>','image/svg+xml')

    def test_fake_image_header_is_not_enough(self):
        with self.assertRaises(subprocess.CalledProcessError):portable_image(b'\x89PNG fake','image/png')
        with self.assertRaises(ValueError):portable_image(b'<html>blocked</html>','text/html')
