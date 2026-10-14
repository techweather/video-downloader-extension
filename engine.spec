# -*- mode: python ; coding: utf-8 -*-
#
# Headless dlwithit engine (engine_main.py) for the native Mac app.
#
#   .venv/bin/pyinstaller --noconfirm engine.spec
#
# Produces dist/dlwithit-engine/ (the dlwithit-engine executable plus _internal/),
# which a Release build of mac/dlwithit.xcodeproj copies into
# dlwithit.app/Contents/Resources/engine/. No Qt: the window is SwiftUI now.
# The Qt app keeps its own recipe in dlwithit.spec.

import sys
import shutil
import subprocess
import pathlib
from pathlib import Path

project_dir = Path(SPECPATH)
sys.path.append(str(project_dir))

binaries = []
for tool in ('ffmpeg', 'ffprobe', 'deno'):
    path = shutil.which(tool)
    if path:
        print(f"Found {tool} at: {path}")
        # Lands in _internal/ (sys._MEIPASS); core/encoder.py and engine_main.py look there.
        binaries.append((path, '.'))
    else:
        print(f"Warning: {tool} not found — the engine build will lack it.")

datas = [('version.py', '.')]
# exiftool for embedded metadata — same files the Qt app bundles (see dlwithit.spec).
exiftool = Path('/opt/homebrew/opt/exiftool')
if exiftool.exists():
    datas += [
        (str(exiftool / 'bin/exiftool'), 'exiftool_bundle'),
        (str(exiftool / 'libexec/lib/perl5/Image'), 'exiftool_bundle/lib/Image'),
        (str(exiftool / 'libexec/lib/perl5/File'), 'exiftool_bundle/lib/File'),
    ]
else:
    print("Warning: exiftool not found — 'Embedded in file' metadata will be skipped.")

a = Analysis(
    ['engine_main.py'],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'flask', 'flask_cors', 'werkzeug', 'jinja2', 'markupsafe', 'itsdangerous', 'click',
        'yt_dlp', 'yt_dlp.extractor', 'yt_dlp.downloader', 'yt_dlp.postprocessor',
        'requests', 'certifi', 'charset_normalizer', 'idna', 'urllib3', 'websockets',
        'config.settings', 'api.flask_server',
        'core.engine', 'core.downloader', 'core.encoder', 'core.library', 'core.routing',
        'core.media_list', 'core.url_router', 'core.metadata', 'core.error_reporter',
        'core.updater', 'core.app_updater', 'core.events',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # The window is native now; keep Qt and the Qt UI out of the engine.
        'PyQt5', 'ui', 'objc', 'AppKit', 'Foundation',
        'tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 'cv2',
        'pygame', 'django', 'tornado', 'unittest', 'doctest', 'pdb', 'profile', 'cProfile',
        'pytest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='dlwithit-engine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='dlwithit-engine',
)

# Same fix the Qt build applies: Homebrew dylibs are stamped minos 15.0; lower to 14.0.
_fix_script = pathlib.Path(SPECPATH) / 'scripts' / 'fix_deployment_target.sh'
_out = str(pathlib.Path(DISTPATH) / 'dlwithit-engine')
if _fix_script.exists():
    print('\n[post-build] Patching deployment target → 14.0 …')
    subprocess.run(['bash', str(_fix_script), _out, '14.0'], check=True)
