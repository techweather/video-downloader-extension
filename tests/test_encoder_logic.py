"""
Tests for pure logic functions in core/encoder.py and core/downloader.py.

No actual file downloads or ffprobe calls — uses byte patterns and mocks.
"""

import pytest
import tempfile
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.downloader import _detect_image_extension
from core.encoder import file_needs_encoding


# --- Image magic-byte detection ---

class TestDetectImageExtension:
    def _write_temp(self, header_bytes, suffix='.bin'):
        f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        f.write(header_bytes + b'\x00' * 20)
        f.close()
        return f.name

    def test_jpeg_detected(self):
        path = self._write_temp(b'\xff\xd8\xff\xe0' + b'\x00' * 8)
        assert _detect_image_extension(path) == 'jpg'
        os.unlink(path)

    def test_png_detected(self):
        path = self._write_temp(b'\x89PNG\r\n\x1a\n' + b'\x00' * 4)
        assert _detect_image_extension(path) == 'png'
        os.unlink(path)

    def test_webp_detected(self):
        # RIFF....WEBP
        header = b'RIFF' + b'\x00' * 4 + b'WEBP'
        path = self._write_temp(header)
        assert _detect_image_extension(path) == 'webp'
        os.unlink(path)

    def test_gif_detected(self):
        path = self._write_temp(b'GIF89a' + b'\x00' * 6)
        assert _detect_image_extension(path) == 'gif'
        os.unlink(path)

    def test_unknown_format_returns_none(self):
        path = self._write_temp(b'\x00\x01\x02\x03' * 3)
        assert _detect_image_extension(path) is None
        os.unlink(path)

    def test_missing_file_returns_none(self):
        assert _detect_image_extension('/nonexistent/path/image.jpg') is None


# --- file_needs_encoding codec logic ---

class TestFileNeedsEncoding:
    def _mock_codec(self, codec_name):
        """Patch detect_video_codec to return a specific codec string."""
        return patch('core.encoder.detect_video_codec', return_value=codec_name)

    def test_vp9_needs_encoding(self):
        with self._mock_codec('vp9'):
            assert file_needs_encoding('fake.webm') is True

    def test_vp8_needs_encoding(self):
        with self._mock_codec('vp8'):
            assert file_needs_encoding('fake.webm') is True

    def test_av1_needs_encoding(self):
        with self._mock_codec('av01'):
            assert file_needs_encoding('fake.webm') is True

    def test_vp09_alias_needs_encoding(self):
        with self._mock_codec('vp09'):
            assert file_needs_encoding('fake.webm') is True

    def test_h264_no_encoding_needed(self):
        with self._mock_codec('h264'):
            assert file_needs_encoding('fake.mp4') is False

    def test_hevc_no_encoding_needed(self):
        with self._mock_codec('hevc'):
            assert file_needs_encoding('fake.mp4') is False

    def test_none_codec_no_encoding(self):
        # ffprobe failed — don't try to encode unknown files
        with self._mock_codec(None):
            assert file_needs_encoding('fake.mp4') is False

    def test_empty_codec_no_encoding(self):
        with self._mock_codec(''):
            assert file_needs_encoding('fake.mp4') is False
