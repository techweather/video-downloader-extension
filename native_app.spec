# -*- mode: python ; coding: utf-8 -*-

import sys
import shutil
from pathlib import Path

# Get the base directory of the project
project_dir = Path(SPECPATH)
sys.path.append(str(project_dir))

# Find ffmpeg tools
def find_ffmpeg_tools():
    """Find ffmpeg and ffprobe binaries on the system"""
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

# Define paths
app_name = 'Media Downloader'
script_path = project_dir / 'native_app.py'

# Collect all Python files in the project
def collect_project_files():
    """Collect all Python files in the project structure"""
    project_files = []
    
    # Main modules
    modules = ['config', 'core', 'ui', 'api']
    
    for module in modules:
        module_path = project_dir / module
        if module_path.exists():
            for py_file in module_path.rglob('*.py'):
                if '__pycache__' not in str(py_file):
                    rel_path = py_file.relative_to(project_dir)
                    project_files.append(str(rel_path))
    
    return project_files

project_files = collect_project_files()

# Analysis configuration
a = Analysis(
    [str(script_path)],
    pathex=[str(project_dir)],
    binaries=(
        # Include ffmpeg tools for video processing if found
        [(ffmpeg_binary, '.')] if ffmpeg_binary else []
    ) + (
        [(ffprobe_binary, '.')] if ffprobe_binary else []
    ),
    datas=[
        # Include project Python files as data
        *[(str(project_dir / f), str(Path(f).parent)) for f in project_files],
    ],
    hiddenimports=[
        # Core PyQt5 modules
        'PyQt5.QtCore',
        'PyQt5.QtGui', 
        'PyQt5.QtWidgets',
        'PyQt5.sip',
        
        # Flask and web server
        'flask',
        'flask_cors',
        'werkzeug',
        'jinja2',
        'markupsafe',
        'itsdangerous',
        'click',
        
        # yt-dlp and dependencies  
        'yt_dlp',
        'yt_dlp.extractor',
        'yt_dlp.downloader',
        'yt_dlp.postprocessor',
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
        'ssl',
        
        # HTTP requests
        'requests',
        'requests.auth',
        'requests.cookies',
        'requests.models',
        'requests.sessions',
        'requests.adapters',
        
        # Standard library modules that might be needed
        'asyncio',
        'asyncio.events',
        'asyncio.protocols',
        'asyncio.transports',
        'json',
        'threading',
        'queue',
        'subprocess',
        'pathlib',
        'datetime',
        'urllib.parse',
        'base64',
        're',
        
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
        # Exclude unused modules to reduce size
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
        'multiprocessing',
        'unittest',
        'doctest',
        'pdb',
        'profile',
        'cProfile',
        'pstats',
        'trace',
        'encodings.utf_32',
        'encodings.utf_32_be',
        'encodings.utf_32_le',
        'encodings.utf_16',
        'encodings.utf_16_be', 
        'encodings.utf_16_le',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Remove duplicate entries
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# One-directory executable configuration
exe_onedir = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Media Downloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    icon=None,  # Add icon path here if available
)

# Collect all files for one-directory distribution
coll = COLLECT(
    exe_onedir,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Media Downloader',
)

# One-file executable configuration (alternative)
exe_onefile = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Media Downloader (Portable)',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    icon=None,  # Add icon path here if available
)

# macOS app bundle configuration
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Media Downloader.app',
        icon=None,  # Add .icns file path here
        bundle_identifier='com.mediadownloader.app',
        version='1.0.0',
        info_plist={
            'CFBundleName': 'Media Downloader',
            'CFBundleDisplayName': 'Media Downloader',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleExecutable': 'Media Downloader',
            'CFBundleIdentifier': 'com.mediadownloader.app',
            'NSHighResolutionCapable': True,
            'LSUIElement': False,  # Set to True to hide from dock
            'NSRequiresAquaSystemAppearance': False,  # Support dark mode
            'LSMultipleInstancesProhibited': True,
            'NSAppleScriptEnabled': False,
            'CFBundleDocumentTypes': [],
            'NSHumanReadableCopyright': '© 2024 Media Downloader',
        }
    )