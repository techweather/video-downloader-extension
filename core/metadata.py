"""
Metadata embedding utilities using exiftool
Embeds source URLs and metadata into downloaded images and videos
"""

import subprocess
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
import logging

# Set up logging — always write to a file so we can see output from the frozen app
logger = logging.getLogger(__name__)

def _setup_file_logger():
    """Configure a file handler so metadata logs are visible in the frozen app."""
    if logger.handlers:
        return  # Already configured
    log_dir = Path.home() / 'Library' / 'Logs' / 'dlwithit'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / 'metadata.log'
    handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

_setup_file_logger()


def _exiftool_cmd():
    """
    Return the exiftool invocation as a list ready for subprocess, or None if unavailable.

    Bundled app layout (PyInstaller datas):
        Contents/Resources/exiftool_bundle/exiftool          ← Perl script
        Contents/Resources/exiftool_bundle/lib/Image/        ← Image::ExifTool

    We call  /usr/bin/perl -I<lib_dir> <script>  explicitly instead of running the
    script directly, which sidesteps the shebang + Homebrew-hardcoded-@INC problem.
    The hardcoded paths baked into the script's BEGIN block don't exist on other
    machines, so Perl falls through to our -I path and finds Image::ExifTool there.

    In development, we just delegate to whatever 'exiftool' is on PATH.
    """
    if getattr(sys, 'frozen', False):
        # --- Bundled .app: use the exiftool we shipped ---
        contents_dir = os.path.dirname(os.path.dirname(sys.executable))
        bundle = os.path.join(contents_dir, 'Resources', 'exiftool_bundle')
        script = os.path.join(bundle, 'exiftool')
        lib    = os.path.join(bundle, 'lib')
        logger.debug(f"[frozen] sys.executable={sys.executable}")
        logger.debug(f"[frozen] contents_dir={contents_dir}")
        logger.debug(f"[frozen] exiftool script={script} exists={os.path.exists(script)}")
        logger.debug(f"[frozen] lib dir={lib} exists={os.path.exists(lib)}")
        if os.path.exists(script):
            cmd = ['/usr/bin/perl', f'-I{lib}', script]
            logger.debug(f"[frozen] returning cmd={cmd}")
            return cmd
        # Fall back to a Homebrew install if someone runs the frozen app in dev
        for path in ['/opt/homebrew/bin/exiftool', '/usr/local/bin/exiftool']:
            if os.path.exists(path):
                logger.debug(f"[frozen] falling back to system exiftool at {path}")
                return [path]
        logger.warning("[frozen] exiftool not found in bundle or Homebrew — metadata will be skipped")
        return None  # Not available — metadata embedding will be skipped

    # --- Development: rely on PATH ---
    return ['exiftool']


def is_exiftool_available():
    """Check if exiftool is available."""
    cmd = _exiftool_cmd()
    if cmd is None:
        logger.warning("is_exiftool_available: _exiftool_cmd() returned None")
        return False
    try:
        result = subprocess.run(cmd + ['-ver'],
                                capture_output=True, text=True, timeout=5)
        available = result.returncode == 0
        logger.debug(f"is_exiftool_available: cmd={cmd} returncode={result.returncode} "
                     f"stdout={result.stdout.strip()!r} stderr={result.stderr.strip()!r} -> {available}")
        return available
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning(f"is_exiftool_available: exception running {cmd}: {type(e).__name__}: {e}")
        return False


def embed_image_metadata(filepath, source_url, page_title=None, download_date=None, page_url=None):
    """
    Embed metadata into image files (JPG, PNG, WEBP, etc.) using exiftool

    Args:
        filepath (str): Path to the image file
        source_url (str): Direct CDN URL of the image file
        page_title (str, optional): Title of the page/post
        download_date (str, optional): ISO format date string, defaults to now
        page_url (str, optional): URL of the web page where the image was found

    Returns:
        bool: True if metadata was successfully embedded, False otherwise
    """
    logger.debug(f"embed_image_metadata called: filepath={filepath!r} url={source_url!r} page_url={page_url!r}")
    if not is_exiftool_available():
        logger.warning("embed_image_metadata: exiftool not available, skipping")
        return False

    if not os.path.exists(filepath):
        logger.error(f"embed_image_metadata: file does not exist: {filepath}")
        return False

    # Default to current date/time if not provided
    if download_date is None:
        download_date = datetime.now().isoformat()

    try:
        # Build exiftool command with metadata tags
        cmd = _exiftool_cmd() + [
            '-overwrite_original',  # Don't create .bak files
            '-quiet',  # Suppress normal output
        ]

        # XMP:Source = direct CDN image URL; XMP:WebStatement = the page where it was found
        web_statement = page_url or source_url
        cmd.extend([
            f'-XMP:Source={source_url}',
            f'-XMP:WebStatement={web_statement}',
            f'-IPTC:Source={source_url}',  # Backup location
            f'-XMP:DateTimeOriginal={download_date}',
        ])

        # Add page URL to visible description fields so it appears in Bridge's
        # sidebar Metadata panel and Preview's IPTC tab without extra clicks.
        if page_url:
            cmd.extend([
                f'-XMP:Description=Source: {page_url}',
                f'-IPTC:Caption-Abstract=Source: {page_url}',
            ])

        # Add page title if provided and it's not a URL
        if page_title and not page_title.startswith('http'):
            cmd.extend([
                f'-XMP:Title={page_title}',
                f'-IPTC:Headline={page_title}',
            ])
        
        # Add file path as last argument
        cmd.append(filepath)
        
        # Execute exiftool command
        logger.debug(f"embed_image_metadata: running cmd={cmd}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        logger.debug(f"embed_image_metadata: returncode={result.returncode} "
                     f"stdout={result.stdout.strip()!r} stderr={result.stderr.strip()!r}")

        if result.returncode == 0:
            logger.info(f"Successfully embedded metadata into image: {Path(filepath).name}")
            return True
        else:
            logger.warning(f"exiftool failed for image {Path(filepath).name}: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"exiftool timeout while processing image: {filepath}")
        return False
    except Exception as e:
        logger.error(f"Error embedding metadata into image {filepath}: {e}", exc_info=True)
        return False


def embed_video_metadata(filepath, source_url, title=None, description=None, uploader=None):
    """
    Embed metadata into video files (MP4, MOV, WEBM, etc.) using exiftool
    
    Args:
        filepath (str): Path to the video file
        source_url (str): Source URL where the video was downloaded from
        title (str, optional): Video title
        description (str, optional): Video description
        uploader (str, optional): Video uploader/channel name
        
    Returns:
        bool: True if metadata was successfully embedded, False otherwise
    """
    logger.debug(f"embed_video_metadata called: filepath={filepath!r} url={source_url!r} title={title!r}")
    if not is_exiftool_available():
        logger.warning("embed_video_metadata: exiftool not available, skipping")
        return False

    if not os.path.exists(filepath):
        logger.error(f"embed_video_metadata: file does not exist: {filepath}")
        return False
    
    try:
        # Build exiftool command with metadata tags
        cmd = _exiftool_cmd() + [
            '-overwrite_original',  # Don't create .bak files
            '-quiet',  # Suppress normal output
        ]

        # Build comment field with source URL and description
        comment_parts = [f"Source: {source_url}"]
        if description:
            comment_parts.append(f"Description: {description}")
        comment_text = " | ".join(comment_parts)
        
        # Add metadata fields for different video formats
        cmd.extend([
            f'-Comment={comment_text}',  # Generic comment field
            f'-XMP:Source={source_url}',  # XMP source
            f'-XMP:WebStatement={source_url}',  # XMP web statement
        ])
        
        # QuickTime-specific fields for MP4/MOV
        file_ext = Path(filepath).suffix.lower()
        if file_ext in ['.mp4', '.mov', '.m4v']:
            cmd.extend([
                f'-QuickTime:Comment={comment_text}',
            ])
            
            if title:
                cmd.extend([
                    f'-QuickTime:Title={title}',
                    f'-XMP:Title={title}',
                ])
            
            if uploader:
                cmd.extend([
                    f'-QuickTime:Artist={uploader}',
                    f'-XMP:Artist={uploader}',
                ])
        
        # WebM/MKV-specific fields
        elif file_ext in ['.webm', '.mkv']:
            if title:
                cmd.append(f'-Matroska:Title={title}')
            
            if uploader:
                cmd.append(f'-Matroska:Artist={uploader}')
        
        # Add generic XMP fields for all video types
        if title:
            cmd.append(f'-XMP:Title={title}')
        if description:
            cmd.append(f'-XMP:Description={description}')
        if uploader:
            cmd.append(f'-XMP:Creator={uploader}')
        
        # Add current timestamp
        current_time = datetime.now().isoformat()
        cmd.append(f'-XMP:CreateDate={current_time}')
        
        # Add file path as last argument
        cmd.append(filepath)
        
        # Execute exiftool command
        logger.debug(f"embed_video_metadata: running cmd={cmd}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        logger.debug(f"embed_video_metadata: returncode={result.returncode} "
                     f"stdout={result.stdout.strip()!r} stderr={result.stderr.strip()!r}")

        if result.returncode == 0:
            logger.info(f"Successfully embedded metadata into video: {Path(filepath).name}")
            return True
        else:
            logger.warning(f"exiftool failed for video {Path(filepath).name}: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"exiftool timeout while processing video: {filepath}")
        return False
    except Exception as e:
        logger.error(f"Error embedding metadata into video {filepath}: {e}", exc_info=True)
        return False


def get_embedded_metadata(filepath):
    """
    Extract embedded metadata from a file using exiftool
    
    Args:
        filepath (str): Path to the media file
        
    Returns:
        dict: Dictionary of metadata tags, empty dict if failed
    """
    if not is_exiftool_available():
        return {}
    
    if not os.path.exists(filepath):
        return {}
    
    try:
        cmd = _exiftool_cmd() + [
            '-json',   # Output as JSON
            '-quiet',  # Suppress normal output
            filepath
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            import json
            metadata_list = json.loads(result.stdout)
            return metadata_list[0] if metadata_list else {}
        else:
            logger.warning(f"exiftool failed to read metadata from {filepath}")
            return {}
            
    except Exception as e:
        logger.error(f"Error reading metadata from {filepath}: {e}")
        return {}


def check_exiftool_installation():
    """
    Check exiftool installation and provide installation instructions if missing
    
    Returns:
        tuple: (is_available: bool, instructions: str)
    """
    if is_exiftool_available():
        try:
            result = subprocess.run(_exiftool_cmd() + ['-ver'],
                                    capture_output=True, text=True, timeout=5)
            version = result.stdout.strip()
            return True, f"exiftool version {version} is installed and ready"
        except Exception:
            return True, "exiftool is available"
    else:
        instructions = """
exiftool is not installed or not available in PATH.

To install exiftool:
- macOS: brew install exiftool
- Windows: Download from https://exiftool.org/ and add to PATH
- Linux: sudo apt install libimage-exiftool-perl (Ubuntu/Debian)
         or sudo yum install perl-Image-ExifTool (CentOS/RHEL)

Without exiftool, metadata embedding will be skipped.
        """.strip()
        return False, instructions


# Test functions for development/debugging
def test_image_embedding(test_image_path):
    """Test function to verify image metadata embedding works"""
    return embed_image_metadata(
        test_image_path,
        source_url="https://example.com/test-image",
        page_title="Test Image Page",
        download_date=datetime.now().isoformat()
    )


def test_video_embedding(test_video_path):
    """Test function to verify video metadata embedding works"""
    return embed_video_metadata(
        test_video_path,
        source_url="https://youtube.com/watch?v=test123",
        title="Test Video Title",
        description="This is a test video description",
        uploader="Test Channel"
    )