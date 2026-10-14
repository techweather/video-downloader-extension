"""
Tests for where sidecar metadata files land and what they're called.

Runs yt-dlp's own filename logic (prepare_filename + the same replace_extension
call it makes for link files) against the templates dlwithit hands it, so no
network and no downloads. Regression: templates that already ended in
.description / .info.json / .url came out as "X.description.description",
"X.info.json.info.json" and "X.url.webloc".
"""

from pathlib import Path

import yt_dlp
from yt_dlp.utils import LINK_TEMPLATES, replace_extension

from core.downloader import sidecar_outtmpl

INFO = {'id': 'Designfo1956', 'title': 'Design for Dreaming', 'ext': 'mp4',
        'webpage_url': 'https://archive.org/details/Designfo1956'}


def names(tmp_path):
    media, meta = tmp_path, tmp_path / '_metadata'
    ydl = yt_dlp.YoutubeDL({'outtmpl': sidecar_outtmpl(media, meta, '%(title)s'), 'quiet': True})
    pick = lambda kind: Path(ydl.prepare_filename(INFO, kind))   # noqa: E731
    link = pick('link')
    return {
        'video': pick(''),
        'thumbnail': Path(replace_extension(str(pick('thumbnail')), 'jpg', 'mp4')),
        'description': pick('description'),
        'infojson': pick('infojson'),
        # what yt-dlp does in _write_link_file for each link type
        'url': Path(replace_extension(str(link), 'url', 'mp4', _allowed_exts=tuple(LINK_TEMPLATES))),
        'webloc': Path(replace_extension(str(link), 'webloc', 'mp4', _allowed_exts=tuple(LINK_TEMPLATES))),
    }


def test_video_stays_in_the_download_folder(tmp_path):
    assert names(tmp_path)['video'] == tmp_path / 'Design for Dreaming.mp4'


def test_metadata_goes_in_the_metadata_folder(tmp_path):
    for kind, p in names(tmp_path).items():
        if kind != 'video':
            assert p.parent == tmp_path / '_metadata', kind


def test_each_sidecar_has_one_extension(tmp_path):
    n = {k: p.name for k, p in names(tmp_path).items()}
    assert n['description'] == 'Design for Dreaming.description'
    assert n['infojson'] == 'Design for Dreaming.info.json'
    assert n['url'] == 'Design for Dreaming.url'
    assert n['webloc'] == 'Design for Dreaming.webloc'
    assert n['thumbnail'] == 'Design for Dreaming_thumbnail.jpg'


def test_only_valid_template_types():
    # A key yt-dlp doesn't know (like the old 'webloc') is silently ignored.
    from yt_dlp.utils import OUTTMPL_TYPES
    assert set(sidecar_outtmpl('a', 'b', 'c')) - {'default'} <= set(OUTTMPL_TYPES)
