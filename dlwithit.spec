# -*- mode: python ; coding: utf-8 -*-

import sys
import shutil
from pathlib import Path

project_dir = Path(SPECPATH)
sys.path.append(str(project_dir))


def find_ffmpeg_tools():
    """Find ffmpeg and ffprobe binaries on the system."""
    ffmpeg_path = shutil.which('ffmpeg')
    ffprobe_path = shutil.which('ffprobe')
    if ffmpeg_path:
        print(f"Found ffmpeg at: {ffmpeg_path}")
    else:
        print("Warning: ffmpeg not found on system!")
    if ffprobe_path:
        print(f"Found ffprobe at: {ffprobe_path}")
    else:
        print("Warning: ffprobe not found on system!")
    return ffmpeg_path, ffprobe_path


ffmpeg_binary, ffprobe_binary = find_ffmpeg_tools()

binaries = []
if ffmpeg_binary:
    binaries.append((ffmpeg_binary, '.'))
if ffprobe_binary:
    binaries.append((ffprobe_binary, '.'))

a = Analysis(
    ['native_app.py'],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=[
        # Non-Python assets bundled into the app
        ('assets', 'assets'),
        ('extension_minimal', 'extension_minimal'),
        ('version.py', '.'),
        # exiftool (Perl script + pure-Perl modules it depends on).
        # All land in Contents/Resources/exiftool_bundle/ so we can call:
        #   /usr/bin/perl -I<exiftool_bundle>/lib exiftool_bundle/exiftool
        # The hardcoded Homebrew paths baked into the script's BEGIN block
        # simply won't exist on other machines, so Perl falls through to the
        # -I path we provide.
        # Image/ is the main ExifTool module (pure Perl, 19 MB).
        # File/ provides File::RandomAccess, required by Image/ExifTool.pm.
        # The arch-specific darwin-thread-multi-2level folder (Brotli compression)
        # is skipped — Image::ExifTool and File::RandomAccess are 100% pure Perl.
        ('/opt/homebrew/Cellar/exiftool/13.44_1/bin/exiftool', 'exiftool_bundle'),
        ('/opt/homebrew/Cellar/exiftool/13.44_1/libexec/lib/perl5/Image', 'exiftool_bundle/lib/Image'),
        ('/opt/homebrew/Cellar/exiftool/13.44_1/libexec/lib/perl5/File', 'exiftool_bundle/lib/File'),
    ],
    hiddenimports=[
        # PyQt5
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.sip',

        # Flask / web server
        'flask',
        'flask_cors',
        'werkzeug',
        'jinja2',
        'markupsafe',
        'itsdangerous',
        'click',

        # yt-dlp
        'yt_dlp',
        'yt_dlp.extractor',
        'yt_dlp.downloader',
        'yt_dlp.postprocessor',

        # HTTP / networking
        'requests',
        'requests.auth',
        'requests.cookies',
        'requests.models',
        'requests.sessions',
        'requests.adapters',
        'urllib3',
        'urllib3.util',
        'urllib3.util.ssl_',
        'urllib3.util.timeout',
        'urllib3.util.retry',
        'urllib3.poolmanager',
        'urllib3.connectionpool',
        'certifi',
        'charset_normalizer',
        'idna',
        'websockets',

        # Project modules
        'config.settings',
        'core.downloader',
        'core.encoder',
        'ui.main_window',
        'ui.components.download_item',
        'ui.components.video_selector',
        'api.flask_server',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'pygame',
        'django',
        'tornado',
        'unittest',
        'doctest',
        'pdb',
        'profile',
        'cProfile',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='dlwithit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX + macOS dylibs = unreliable; skip it
    console=False,      # No terminal window (windowed app)
    disable_windowed_traceback=False,
    icon='assets/dlwithit.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='dlwithit',
)

app = BUNDLE(
    coll,
    name='dlwithit.app',
    icon='assets/dlwithit.icns',
    bundle_identifier='com.dlwithit.app',
    version='1.0.0',
    info_plist={
        'CFBundleName': 'dlwithit',
        'CFBundleDisplayName': 'dlwithit',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleExecutable': 'dlwithit',
        'CFBundleIdentifier': 'com.dlwithit.app',
        'NSHighResolutionCapable': True,
        'LSUIElement': False,           # Show in Dock; set True to hide
        'NSRequiresAquaSystemAppearance': False,  # Support dark mode
        'LSMultipleInstancesProhibited': True,
        'NSHumanReadableCopyright': '© 2025 dlwithit',
        'CFBundleURLTypes': [{
            'CFBundleURLName': 'com.dlwithit.app',
            'CFBundleURLSchemes': ['dlwithit'],
        }],
    },
)

# ── Post-build: lower minos from 15.0 → 14.0 ────────────────────────────────
# Homebrew Python 3.13 and ffmpeg dylibs are compiled with minos=15.0.
# The fix_deployment_target.sh script patches every .so/.dylib in the bundle
# using vtool and re-signs with an ad-hoc signature, allowing the app to run
# on macOS 14 (Sonoma) without actually using any macOS-15-only APIs.
import subprocess, pathlib
_fix_script = pathlib.Path(SPECPATH) / 'scripts' / 'fix_deployment_target.sh'
_app_path = str(pathlib.Path(DISTPATH) / 'dlwithit.app')
if _fix_script.exists():
    print(f'\n[post-build] Patching deployment target → 14.0 …')
    subprocess.run(['bash', str(_fix_script), _app_path, '14.0'], check=True)
