"""
Metadata embedding utilities using exiftool
Embeds source URLs and metadata into downloaded images and videos
"""

import subprocess
import os
import shutil
from pathlib import Path
from datetime import datetime
import logging

# Set up logging
logger = logging.getLogger(__name__)


def is_exiftool_available():
    """
    Check if exiftool is available on the system
    
    Returns:
        bool: True if exiftool is available, False otherwise
    """
    try:
        result = subprocess.run(['exiftool', '-ver'], 
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def embed_image_metadata(filepath, source_url, page_title=None, download_date=None):
    """
    Embed metadata into image files (JPG, PNG, WEBP, etc.) using exiftool
    
    Args:
        filepath (str): Path to the image file
        source_url (str): Source URL where the image was downloaded from
        page_title (str, optional): Title of the page/post
        download_date (str, optional): ISO format date string, defaults to now
        
    Returns:
        bool: True if metadata was successfully embedded, False otherwise
    """
    if not is_exiftool_available():
        logger.warning("exiftool not available, skipping image metadata embedding")
        return False
    
    if not os.path.exists(filepath):
        logger.error(f"Image file does not exist: {filepath}")
        return False
    
    # Default to current date/time if not provided
    if download_date is None:
        download_date = datetime.now().isoformat()
    
    try:
        # Build exiftool command with metadata tags
        cmd = [
            'exiftool',
            '-overwrite_original',  # Don't create .bak files
            '-quiet',  # Suppress normal output
        ]
        
        # Add source URL to multiple fields for compatibility
        cmd.extend([
            f'-XMP:Source={source_url}',
            f'-XMP:WebStatement={source_url}',  
            f'-IPTC:Source={source_url}',  # Backup location
            f'-XMP:DateTimeOriginal={download_date}',
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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
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
        logger.error(f"Error embedding metadata into image {filepath}: {e}")
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
    if not is_exiftool_available():
        logger.warning("exiftool not available, skipping video metadata embedding")
        return False
    
    if not os.path.exists(filepath):
        logger.error(f"Video file does not exist: {filepath}")
        return False
    
    try:
        # Build exiftool command with metadata tags
        cmd = [
            'exiftool',
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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
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
        logger.error(f"Error embedding metadata into video {filepath}: {e}")
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
        cmd = [
            'exiftool',
            '-json',  # Output as JSON
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
            result = subprocess.run(['exiftool', '-ver'], 
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