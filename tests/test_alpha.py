"""
Tests for see-through (alpha) video detection in core/encoder.py.

Apple's mac-mini "ports" animation ships as HEVC-with-alpha .mov and VP9-alpha
.webm. Converting either to H.264 MP4 would flatten the background, so these
files must never go through the auto "Convert to MP4" step.

Small test clips are made with ffmpeg on the fly (skipped without it). The
HEVC-with-alpha case uses the real decoder-setup bytes from Apple's file.
"""

import shutil
import subprocess

import pytest

from core.encoder import file_needs_encoding, hevc_mov_has_alpha, video_has_alpha

# The hvcC record of Apple's mac-mini ports/large_2x.mov (2026-10-17): a VPS
# declaring two layers and an alpha_channel_info SEI.
APPLE_ALPHA_HVCC = bytes.fromhex(
    '012160000000b0000000000078f000fcfdf8f800000f04a00001002640010c11ffff216000000300b0000003'
    '000003007811c0bf7808000830285200000300006520a100020031420101216000000300b00000030000030078'
    'a0026c8013659c47924488ce49249549fa1ad32923ff000100016a020202010032420901016000000300b00000'
    '03000003007848009b2004d96711e4912233924925527e86b4ca48ffc00040005b8080808040a2000200084401'
    'c0252f05324000094409480240d4bc14c927000100094e01a50410007f9080')


def box(kind, payload):
    return (8 + len(payload)).to_bytes(4, 'big') + kind + payload


def write_mov(path, hvcc, moov_last=False):
    """A skeleton QuickTime file: ftyp, mdat, and a moov whose sample entry carries hvcC."""
    ftyp = box(b'ftyp', b'qt  \x00\x00\x00\x00qt  ')
    mdat = box(b'mdat', b'\x00' * 64)
    moov = box(b'moov', box(b'trak', box(b'hvc1', b'\x00' * 78 + box(b'hvcC', hvcc))))
    path.write_bytes(ftyp + mdat + moov if moov_last else ftyp + moov + mdat)
    return path


class TestHevcAlpha:
    def test_apple_hevc_with_alpha(self, tmp_path):
        assert hevc_mov_has_alpha(write_mov(tmp_path / 'ports.mov', APPLE_ALPHA_HVCC))

    def test_index_at_the_end_of_the_file(self, tmp_path):
        assert hevc_mov_has_alpha(write_mov(tmp_path / 'ports.mov', APPLE_ALPHA_HVCC, moov_last=True))

    def test_single_layer_hevc_is_opaque(self, tmp_path):
        # Same record with the two-layer VPS made single-layer and the SEI dropped.
        record = bytearray(APPLE_ALPHA_HVCC)
        vps = record.find(bytes.fromhex('40010c11'))
        record[vps + 3] = 0x01               # vps_max_layers_minus1 = 0
        sei = record.find(bytes.fromhex('4e01a5'))
        record[sei + 2] = 0x05               # some other SEI payload type
        assert not hevc_mov_has_alpha(write_mov(tmp_path / 'opaque.mov', bytes(record)))

    def test_not_hevc_or_not_a_movie(self, tmp_path):
        (tmp_path / 'page.html').write_bytes(b'<html></html>')
        assert not hevc_mov_has_alpha(tmp_path / 'page.html')
        assert not hevc_mov_has_alpha(tmp_path / 'missing.mov')
        assert not hevc_mov_has_alpha(write_mov(tmp_path / 'truncated.mov', APPLE_ALPHA_HVCC[:24]))


def _ffmpeg_can(encoder):
    if not shutil.which('ffmpeg'):
        return False
    out = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True, text=True).stdout
    return f' {encoder} ' in out


def make_clip(path, source, *codec_args):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', source, '-t', '1',
                    *codec_args, str(path)], check=True, timeout=60)
    return str(path)


SEE_THROUGH = 'color=c=red@0.0:s=64x64:r=10,format=yuva420p'
SOLID_WITH_ALPHA = 'color=c=red:s=64x64:r=10,format=yuva420p'
SOLID = 'color=c=red:s=64x64:r=10'


@pytest.mark.skipif(not _ffmpeg_can('libvpx-vp9'), reason='needs ffmpeg with libvpx-vp9')
class TestWebm:
    def test_see_through_vp9_is_kept_as_is(self, tmp_path):
        clip = make_clip(tmp_path / 'a.webm', SEE_THROUGH, '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p')
        assert video_has_alpha(clip)
        assert not file_needs_encoding(clip)

    def test_alpha_channel_that_is_solid_still_converts(self, tmp_path):
        # Apple's opaque WebMs (MacBook Neo "display") carry an alpha channel that's 255 throughout.
        clip = make_clip(tmp_path / 'b.webm', SOLID_WITH_ALPHA, '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p')
        assert not video_has_alpha(clip)
        assert file_needs_encoding(clip)

    def test_plain_vp9_converts(self, tmp_path):
        clip = make_clip(tmp_path / 'c.webm', SOLID, '-c:v', 'libvpx-vp9')
        assert not video_has_alpha(clip)
        assert file_needs_encoding(clip)

    @pytest.mark.skipif(not _ffmpeg_can('libvpx'), reason='needs ffmpeg with libvpx')
    def test_see_through_vp8(self, tmp_path):
        clip = make_clip(tmp_path / 'd.webm', SEE_THROUGH, '-c:v', 'libvpx', '-pix_fmt', 'yuva420p',
                         '-auto-alt-ref', '0')
        assert video_has_alpha(clip)
        assert not file_needs_encoding(clip)


@pytest.mark.skipif(not _ffmpeg_can('prores_ks'), reason='needs ffmpeg with prores_ks')
def test_prores_4444_with_alpha(tmp_path):
    clip = make_clip(tmp_path / 'e.mov', SEE_THROUGH, '-c:v', 'prores_ks', '-profile:v', '4444',
                     '-pix_fmt', 'yuva444p10le')
    assert video_has_alpha(clip)


@pytest.mark.skipif(not _ffmpeg_can('libx264'), reason='needs ffmpeg with libx264')
def test_h264_has_no_alpha(tmp_path):
    clip = make_clip(tmp_path / 'f.mp4', SOLID, '-c:v', 'libx264', '-pix_fmt', 'yuv420p')
    assert not video_has_alpha(clip)
    assert not file_needs_encoding(clip)


def test_unreadable_file_has_no_alpha(tmp_path):
    (tmp_path / 'x.webm').write_bytes(b'not a video')
    assert not video_has_alpha(str(tmp_path / 'x.webm'))
