"""
Download worker and core downloading functionality for Media Downloader App
"""

import os
import requests
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, unquote

from PyQt5.QtCore import QThread, pyqtSignal
import yt_dlp

from .encoder import VideoEncoder, needs_encoding_check
from .metadata import embed_image_metadata, embed_video_metadata

class YtDlpLogger:
    """Custom logger to capture yt-dlp messages, including skip notifications."""

    def __init__(self):
        self.skipped = False
        self.skip_reason = None
        self.skipped_filename = None

    def debug(self, msg):
        # Capture "already downloaded" messages
        if 'has already been downloaded' in msg.lower():
            print(f"[DEBUG] YtDlpLogger captured skip message: {msg}")
            self.skipped = True
            self.skip_reason = msg
            # Try to extract filename from message
            # Format is typically: "[download] filename has already been downloaded"
            if msg.startswith('[download]'):
                parts = msg.split(' has already been downloaded')
                if parts:
                    self.skipped_filename = parts[0].replace('[download]', '').strip()
                    print(f"[DEBUG] YtDlpLogger extracted filename: {self.skipped_filename}")

    def warning(self, msg):
        pass

    def error(self, msg):
        pass

    def reset(self):
        """Reset state for a new download."""
        print(f"[DEBUG] YtDlpLogger.reset() called - clearing skip state (was skipped={self.skipped})")
        self.skipped = False
        self.skip_reason = None
        self.skipped_filename = None


class DownloadWorker(QThread):
    progress_update = pyqtSignal(str, int, str)  # id, percent, status
    download_complete = pyqtSignal(str, str)  # id, path
    download_error = pyqtSignal(str, str)  # id, error
    download_cancelled = pyqtSignal(str)  # id
    status_update = pyqtSignal(str, str)  # id, status
    playlist_detected = pyqtSignal(str, dict)  # download_id, playlist_data
    download_skipped = pyqtSignal(str, str, str)  # download_id, reason, filepath
    # Signal to request encoding in separate worker (download_id, filepath, keep_original, metadata_info)
    encoding_needed = pyqtSignal(str, str, bool, dict)
    
    def __init__(self, download_queue):
        super().__init__()
        self.download_queue = download_queue
        self.current_download_id = None
        self.current_download_info = None
        self.cancelled_downloads = set()
        self.active_process = None
        self.encoder = VideoEncoder()
        self.partial_files = set()  # Track partial files for cleanup
        self.has_emitted_downloading_status = False  # Track if we've sent downloading status
        self.ytdlp_logger = YtDlpLogger()  # Logger to capture skip messages
        self.final_filepath = None  # Track final filepath after postprocessing (merging)
    
    def cancel_download(self, download_id):
        """Cancel a download"""
        self.cancelled_downloads.add(download_id)
        if self.active_process and self.current_download_id == download_id:
            try:
                self.active_process.terminate()
            except:
                pass
        # Also cancel any active encoding
        if self.current_download_id == download_id:
            self.encoder.cancel_encoding()
    
    def cleanup_partial_files(self, download_id):
        """Clean up any partial files for a cancelled download"""
        print(f"[DEBUG] Starting cleanup for download {download_id}")
        print(f"[DEBUG] Tracked partial files: {list(self.partial_files)}")
        
        # Get current download info for directory scanning
        download_info = getattr(self, 'current_download_info', {})
        save_path = download_info.get('save_path', str(Path.home() / 'Downloads' / 'Media'))
        
        # Clean up tracked files
        files_to_remove = list(self.partial_files)
        self.partial_files.clear()
        cleaned_count = 0
        
        for filepath in files_to_remove:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    cleaned_count += 1
                    print(f"[DEBUG] Removed tracked file: {filepath}")
                else:
                    print(f"[DEBUG] Tracked file not found: {filepath}")
            except Exception as e:
                print(f"[DEBUG] Could not remove tracked file {filepath}: {e}")
        
        # Additional cleanup for yt-dlp fragment files
        self._cleanup_ytdlp_fragments(save_path)
        
        print(f"[DEBUG] Cleanup complete - removed {cleaned_count} tracked files")
    
    def _cleanup_ytdlp_fragments(self, base_path):
        """Clean up yt-dlp fragment files and temporary files"""
        print(f"[DEBUG] Scanning for yt-dlp fragments in: {base_path}")
        
        try:
            base_dir = Path(base_path)
            if not base_dir.exists():
                return
            
            # Patterns for yt-dlp temporary and fragment files
            patterns = [
                '*.part',           # Partial downloads
                '*.ytdl',          # yt-dlp temporary files
                '*.f[0-9]*',       # Fragment files (f1, f2, etc.)
                '*.temp',          # Temporary files
                '*.tmp',           # Temporary files
                '*_temp_*',        # Temporary files with temp in name
            ]
            
            fragment_count = 0
            
            # Look in all subdirectories (Instagram, YouTube, etc.)
            for search_dir in [base_dir] + [d for d in base_dir.iterdir() if d.is_dir()]:
                print(f"[DEBUG] Scanning directory: {search_dir}")
                
                for pattern in patterns:
                    try:
                        for file_path in search_dir.glob(pattern):
                            if file_path.is_file():
                                # Check if file was modified recently (within last 5 minutes)
                                # This helps avoid cleaning up unrelated files
                                import time
                                file_age = time.time() - file_path.stat().st_mtime
                                if file_age < 300:  # 5 minutes
                                    try:
                                        file_path.unlink()
                                        fragment_count += 1
                                        print(f"[DEBUG] Removed fragment/temp file: {file_path}")
                                    except Exception as e:
                                        print(f"[DEBUG] Could not remove fragment {file_path}: {e}")
                                else:
                                    print(f"[DEBUG] Skipping old file: {file_path} (age: {file_age:.1f}s)")
                    except Exception as e:
                        print(f"[DEBUG] Error scanning pattern {pattern}: {e}")
            
            print(f"[DEBUG] Removed {fragment_count} fragment/temp files")
            
        except Exception as e:
            print(f"[DEBUG] Error during fragment cleanup: {e}")
    
    def progress_hook(self, d):
        # Check if cancelled
        if self.current_download_id in self.cancelled_downloads:
            print(f"[DEBUG] Cancellation detected in progress hook for {self.current_download_id}")
            raise Exception("Download cancelled by user")

        # Log progress hook calls to help debug skip issues
        if d['status'] == 'finished':
            print(f"[DEBUG] Progress hook: status=finished for download_id={self.current_download_id}")

        if d['status'] == 'downloading':
            # Emit 'downloading' status on first actual progress
            if not self.has_emitted_downloading_status:
                self.status_update.emit(self.current_download_id, 'downloading')
                self.has_emitted_downloading_status = True

            percent = 0
            if d.get('total_bytes'):
                percent = int(d['downloaded_bytes'] / d['total_bytes'] * 100)
            elif d.get('total_bytes_estimate'):
                percent = int(d['downloaded_bytes'] / d['total_bytes_estimate'] * 100)

            # Detect if downloading video or audio stream
            stream_type = self._detect_stream_type(d)
            if stream_type == 'video':
                status_text = f"Downloading video... {percent}%"
            elif stream_type == 'audio':
                status_text = f"Downloading audio... {percent}%"
            else:
                status_text = f"Downloading... {percent}%"

            self.progress_update.emit(
                self.current_download_id,
                percent,
                status_text
            )
        elif d['status'] == 'finished':
            self.progress_update.emit(
                self.current_download_id,
                100,
                "Processing..."
            )

    def _detect_stream_type(self, d):
        """
        Detect if the current download is a video or audio stream.

        Args:
            d: Progress hook dictionary from yt-dlp

        Returns:
            str: 'video', 'audio', or 'unknown'
        """
        # Method 1: Check info_dict for codec information
        info_dict = d.get('info_dict', {})
        vcodec = info_dict.get('vcodec', '')
        acodec = info_dict.get('acodec', '')

        # If vcodec is 'none', it's audio-only; if acodec is 'none', it's video-only
        if vcodec == 'none' and acodec and acodec != 'none':
            return 'audio'
        if acodec == 'none' and vcodec and vcodec != 'none':
            return 'video'

        # Method 2: Check filename for format indicators
        filename = d.get('filename', '').lower()

        # Common audio-only extensions and format IDs
        audio_indicators = ['.m4a', '.mp3', '.aac', '.opus', '.ogg', '.wav', '.flac',
                          '.f140.', '.f139.', '.f141.', '.f251.', '.f250.', '.f249.']
        # Common video format IDs (no audio)
        video_indicators = ['.f137.', '.f136.', '.f135.', '.f134.', '.f133.',
                          '.f299.', '.f298.', '.f303.', '.f302.', '.f308.',
                          '.f315.', '.f313.', '.f271.', '.f313.', '.f401.',
                          '.f400.', '.f399.', '.f398.']

        for indicator in audio_indicators:
            if indicator in filename:
                return 'audio'

        for indicator in video_indicators:
            if indicator in filename:
                return 'video'

        # Method 3: Check if it's a combined format (has both video and audio)
        if vcodec and vcodec != 'none' and acodec and acodec != 'none':
            return 'unknown'  # Combined stream, use generic status

        return 'unknown'

    def postprocessor_hook(self, d):
        """
        Hook for yt-dlp postprocessor events (merging, converting, etc.)

        Args:
            d: Postprocessor hook dictionary with 'status', 'postprocessor', and 'info_dict' keys
        """
        # Check if cancelled
        if self.current_download_id in self.cancelled_downloads:
            return

        status = d.get('status')
        postprocessor = d.get('postprocessor', '')
        info_dict = d.get('info_dict', {})

        # Comprehensive debug logging
        print(f"[DEBUG] ===== POSTPROCESSOR HOOK CALLED =====")
        print(f"[DEBUG]   status: {status}")
        print(f"[DEBUG]   postprocessor: {postprocessor}")
        print(f"[DEBUG]   d keys: {list(d.keys())}")
        print(f"[DEBUG]   info_dict keys: {list(info_dict.keys())[:20]}...")  # First 20 keys
        print(f"[DEBUG]   filepath: {info_dict.get('filepath')}")
        print(f"[DEBUG]   filename: {info_dict.get('filename')}")
        print(f"[DEBUG]   _filename: {info_dict.get('_filename')}")
        print(f"[DEBUG]   ext: {info_dict.get('ext')}")
        print(f"[DEBUG]   requested_downloads: {info_dict.get('requested_downloads')}")

        if status == 'started':
            # Detect what kind of postprocessing is happening
            pp_lower = postprocessor.lower()
            if 'merger' in pp_lower or 'ffmpeg' in pp_lower:
                self.status_update.emit(self.current_download_id, 'merging')
            elif 'embed' in pp_lower:
                self.status_update.emit(self.current_download_id, 'embedding metadata...')
        elif status == 'finished':
            # Capture the final filepath after postprocessing
            # This is especially important after merging, as the output format may differ
            filepath = info_dict.get('filepath')
            if filepath:
                print(f"[DEBUG] ✓ Postprocessor finished, capturing filepath: {filepath}")
                self.final_filepath = filepath
            else:
                # Try alternative keys
                alt_filepath = info_dict.get('_filename') or info_dict.get('filename')
                if alt_filepath:
                    print(f"[DEBUG] ✓ Using alternative filepath key: {alt_filepath}")
                    self.final_filepath = alt_filepath
                else:
                    print(f"[DEBUG] ✗ No filepath found in postprocessor hook!")
    
    def download_image(self, url, download_id, save_path, organize_by_platform, referrer=None):
        """Download an image file"""
        try:
            # Create images directory if organizing by platform
            if organize_by_platform:
                image_dir = Path(save_path) / 'images'
            else:
                image_dir = Path(save_path)
            image_dir.mkdir(parents=True, exist_ok=True)
            
            # Get filename from URL
            parsed = urlparse(url)
            filename = os.path.basename(unquote(parsed.path))
            
            # Fallback filename if needed
            if not filename or '.' not in filename:
                ext = 'jpg'  # Default extension
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'image_{timestamp}.{ext}'
            
            filepath = image_dir / filename
            
            # Handle duplicates
            counter = 1
            while filepath.exists():
                name, ext = filename.rsplit('.', 1)
                filepath = image_dir / f"{name}_{counter}.{ext}"
                counter += 1
            
            # Track this file for cleanup if cancelled
            self.partial_files.add(str(filepath))
            
            # Set up headers to mimic browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
            }
            
            # Add referrer if provided
            if referrer:
                headers['Referer'] = referrer
                # Also try origin for some sites
                origin = urlparse(referrer)
                headers['Origin'] = f"{origin.scheme}://{origin.netloc}"
            
            # Download with progress
            response = requests.get(url, stream=True, headers=headers, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    # Check for cancellation
                    if download_id in self.cancelled_downloads:
                        f.close()
                        raise Exception("Download cancelled by user")
                        
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            percent = int(downloaded / total_size * 100)
                            self.progress_update.emit(
                                download_id,
                                percent,
                                f"Downloading... {percent}%"
                            )
            
            # Remove from partial files once complete
            self.partial_files.discard(str(filepath))
            return str(filepath)
            
        except requests.exceptions.HTTPError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")
    
    def encode_to_h264(self, input_path, download_id):
        """Encode video to H.264 using the encoder module"""
        def progress_callback(percent, status):
            """Callback to emit progress updates"""
            self.progress_update.emit(download_id, percent, status)
        
        keep_original = self.current_download_info.get('keep_original', False)
        print(f"[DEBUG] Encoding with keep_original={keep_original} for file: {input_path}")
        return self.encoder.encode_to_h264(input_path, keep_original, progress_callback)
    
    def extract_vimeo_id(self, url, error_message=None):
        """Extract Vimeo video ID from URL, error message, or page HTML"""
        print(f"[DEBUG] Extracting Vimeo ID from URL: {url}")
        
        # Pattern 1: Direct Vimeo URL patterns
        vimeo_patterns = [
            r'vimeo\.com/(?:video/)?(\d+)',
            r'player\.vimeo\.com/video/(\d+)',
            r'vimeo\.com/channels/[^/]+/(\d+)',
            r'vimeo\.com/groups/[^/]+/videos/(\d+)',
        ]
        
        print(f"[DEBUG] Trying {len(vimeo_patterns)} URL patterns on: {url}")
        for i, pattern in enumerate(vimeo_patterns):
            print(f"[DEBUG] Pattern {i+1}: {pattern}")
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                print(f"[DEBUG] ✓ Found Vimeo ID from URL pattern {i+1}: {video_id}")
                return video_id
        print(f"[DEBUG] ✗ No matches in URL patterns")
        
        # Pattern 2: Check error message for embedded IDs
        if error_message:
            print(f"[DEBUG] Checking error message for Vimeo ID")
            print(f"[DEBUG] Error message: {error_message[:200]}...")
            error_patterns = [
                r'\[vimeo\]\s*(\d+)',  # Matches '[vimeo] 1108703340' format
                r'video/(\d+)',
                r'vimeo\.com/(\d+)',
                r'id["\']?\s*:\s*["\']?(\d+)["\']?',
            ]
            
            for i, pattern in enumerate(error_patterns):
                print(f"[DEBUG] Error pattern {i+1}: {pattern}")
                match = re.search(pattern, error_message)
                if match:
                    video_id = match.group(1)
                    print(f"[DEBUG] ✓ Found Vimeo ID from error pattern {i+1}: {video_id}")
                    return video_id
            print(f"[DEBUG] ✗ No matches in error patterns")
        else:
            print(f"[DEBUG] No error message provided for pattern matching")
        
        # Pattern 3: Fetch page HTML and extract ID
        try:
            referrer = self.current_download_info.get('referrer')
            if referrer:
                # Validate and fix URL scheme
                if referrer.startswith('www.'):
                    referrer = 'https://' + referrer
                elif not referrer.startswith(('http://', 'https://')):
                    referrer = 'https://' + referrer
                
                print(f"[DEBUG] Fetching page HTML from referrer: {referrer}")
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                }
                response = requests.get(referrer, headers=headers, timeout=10)
                print(f"[DEBUG] HTTP response status: {response.status_code}")
                html_content = response.text
                print(f"[DEBUG] Page content length: {len(html_content)} characters")
                print(f"[DEBUG] Page content sample: {html_content[:300]}...")
                
                # Look for Vimeo IDs in HTML
                html_patterns = [
                    r'"video_id"\s*:\s*"?(\d+)"?',
                    r'"id"\s*:\s*(\d+)',
                    r'vimeo\.com/(?:video/)?(\d+)',
                    r'player\.vimeo\.com/video/(\d+)',
                    r'data-vimeo-id["\']?\s*=\s*["\']?(\d+)["\']?',
                    r'vimeo_video_id["\']?\s*:\s*["\']?(\d+)["\']?',
                ]
                
                print(f"[DEBUG] Searching HTML with {len(html_patterns)} patterns")
                for i, pattern in enumerate(html_patterns):
                    print(f"[DEBUG] HTML pattern {i+1}: {pattern}")
                    match = re.search(pattern, html_content, re.IGNORECASE)
                    if match:
                        video_id = match.group(1)
                        print(f"[DEBUG] ✓ Found Vimeo ID from HTML pattern {i+1}: {video_id}")
                        # Show context around the match
                        match_start = max(0, match.start() - 50)
                        match_end = min(len(html_content), match.end() + 50)
                        context = html_content[match_start:match_end]
                        print(f"[DEBUG] Match context: ...{context}...")
                        return video_id
                print(f"[DEBUG] ✗ No matches in HTML patterns")
            else:
                print(f"[DEBUG] No referrer URL available for HTML fetching")
        except Exception as e:
            print(f"[DEBUG] ✗ Failed to fetch page HTML: {e}")
            import traceback
            print(f"[DEBUG] HTML fetch traceback: {traceback.format_exc()}")
        
        print(f"[DEBUG] ✗ No Vimeo ID found through any method")
        return None
    
    def is_vimeo_embed_error(self, error_message, url):
        """Check if error indicates a failed Vimeo embed that might work with direct URL"""
        error_lower = error_message.lower()
        
        # Check for Vimeo-related errors
        vimeo_indicators = [
            'vimeo' in error_lower,
            'player.vimeo.com' in error_lower,
            any(pattern in url.lower() for pattern in ['vimeo.com', 'player.vimeo.com'])
        ]
        
        # Check for access-related errors
        access_errors = [
            '401' in error_message,
            '403' in error_message,
            'unauthorized' in error_lower,
            'forbidden' in error_lower,
            'private' in error_lower,
            'embed' in error_lower and 'restricted' in error_lower,
            'not available' in error_lower and 'embed' in error_lower,
        ]
        
        has_vimeo = any(vimeo_indicators)
        has_access_error = any(access_errors)
        
        print(f"[DEBUG] Vimeo embed error check - Vimeo: {has_vimeo}, Access error: {has_access_error}")
        return has_vimeo and has_access_error
    
    def embed_video_metadata_if_requested(self, filepath, metadata_option, info, source_url):
        """
        Embed metadata into video file if embedded metadata is requested
        
        Args:
            filepath (str): Path to the video file
            metadata_option (str): Metadata option ('embedded', 'sidecar', 'none')
            info (dict): yt-dlp info dictionary with video metadata
            source_url (str): Original source URL
            
        Returns:
            bool: True if embedding was attempted (regardless of success)
        """
        if metadata_option != 'embedded':
            return False
            
        if not info:
            print(f"[DEBUG] No video info available for metadata embedding")
            return False
            
        # Extract metadata from yt-dlp info
        title = info.get('title', 'Downloaded Video')
        description = info.get('description', '')
        uploader = info.get('uploader') or info.get('channel') or info.get('uploader_id')
        webpage_url = info.get('webpage_url', source_url)
        
        # Truncate description if too long (metadata fields have limits)
        if description and len(description) > 500:
            description = description[:497] + "..."
            
        print(f"[DEBUG] Embedding metadata into video: {Path(filepath).name}")
        print(f"[DEBUG] Title: {title}")
        print(f"[DEBUG] Uploader: {uploader}")
        print(f"[DEBUG] Source: {webpage_url}")
        
        # Embed metadata into video
        embed_success = embed_video_metadata(
            filepath=filepath,
            source_url=webpage_url,
            title=title,
            description=description,
            uploader=uploader
        )
        
        if embed_success:
            print(f"[DEBUG] ✓ Successfully embedded metadata into video: {Path(filepath).name}")
        else:
            print(f"[DEBUG] ✗ Failed to embed metadata into video: {Path(filepath).name}")
            
        return True
    
    def run(self):
        while True:
            download = self.download_queue.get()
            if download is None:
                break
            
            print(f"[DEBUG] ===== NEW DOWNLOAD FROM QUEUE =====")
            print(f"[DEBUG] Download ID: {download['id']}")
            print(f"[DEBUG] Type: {download.get('type')}")
            print(f"[DEBUG] URL: {download.get('url', '')[:80]}...")

            self.current_download_id = download['id']
            self.current_download_info = download  # Store for encoding options
            self.has_emitted_downloading_status = False  # Reset for new download
            self.final_filepath = None  # Reset for new download
            
            # Check if already cancelled
            if self.current_download_id in self.cancelled_downloads:
                self.cleanup_partial_files(self.current_download_id)
                self.download_cancelled.emit(self.current_download_id)
                self.cancelled_downloads.remove(self.current_download_id)
                continue
                
            try:
                # Get the save path and settings for this download
                save_path = download.get('save_path', str(Path.home() / 'Downloads' / 'Media'))
                organize_by_platform = download.get('organize_by_platform', True)
                metadata_option = download.get('metadata_option', 'none')
                
                if download['type'] == 'image':
                    # Download image with referrer
                    self.status_update.emit(self.current_download_id, 'downloading')
                    referrer = download.get('referrer')
                    filepath = self.download_image(download['url'], download['id'], save_path, organize_by_platform, referrer)
                    
                    # Embed metadata if requested
                    if metadata_option == 'embedded' and self.current_download_id not in self.cancelled_downloads:
                        self.status_update.emit(self.current_download_id, 'adding metadata...')
                        page_title = download.get('title')
                        # Only pass title if it's not a URL
                        if page_title and page_title.startswith('http'):
                            page_title = None
                        embed_success = embed_image_metadata(
                            filepath=filepath,
                            source_url=download['url'],
                            page_title=page_title
                        )
                        if embed_success:
                            print(f"[DEBUG] Successfully embedded metadata into image: {Path(filepath).name}")
                        else:
                            print(f"[DEBUG] Failed to embed metadata into image: {Path(filepath).name}")
                    
                    if self.current_download_id not in self.cancelled_downloads:
                        self.download_complete.emit(download['id'], filepath)
                elif download['type'] == 'direct-video':
                    # Download video directly (like images but for video)
                    self.status_update.emit(self.current_download_id, 'downloading')
                    referrer = download.get('referrer')
                    title = download.get('title', 'video')
                    save_path = download.get('save_path', str(Path.home() / 'Downloads' / 'Media'))
                    organize_by_platform = download.get('organize_by_platform', True)
                    
                    # Create videos directory if organizing
                    if organize_by_platform:
                        video_dir = Path(save_path) / 'web-videos'
                    else:
                        video_dir = Path(save_path)
                    video_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Generate filename
                    parsed = urlparse(download['url'])
                    ext = os.path.splitext(parsed.path)[1] or '.mp4'
                    filename = f"{title}{ext}"
                    
                    filepath = video_dir / filename
                    
                    # Handle duplicates
                    counter = 1
                    while filepath.exists():
                        filepath = video_dir / f"{title}_{counter}{ext}"
                        counter += 1
                    
                    # Track this file for cleanup if cancelled
                    self.partial_files.add(str(filepath))
                    
                    # Download with requests
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                        'Accept': 'video/*,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Cache-Control': 'no-cache',
                    }
                    
                    if referrer:
                        headers['Referer'] = referrer
                        origin = urlparse(referrer)
                        headers['Origin'] = f"{origin.scheme}://{origin.netloc}"
                    
                    response = requests.get(download['url'], stream=True, headers=headers, timeout=30)
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if self.current_download_id in self.cancelled_downloads:
                                f.close()
                                raise Exception("Download cancelled by user")
                                
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                if total_size > 0:
                                    percent = int(downloaded / total_size * 100)
                                    self.progress_update.emit(
                                        download['id'],
                                        percent,
                                        f"Downloading... {percent}%"
                                    )
                    
                    # Remove from partial files once complete
                    self.partial_files.discard(str(filepath))
                    if self.current_download_id not in self.cancelled_downloads:
                        # Check if direct-video file needs encoding
                        print(f"[DEBUG] Direct-video download complete: {filepath}")
                        print(f"[DEBUG] Download type: direct-video")
                        print(f"[DEBUG] encode_vp9 setting: {download.get('encode_vp9', True)}")
                        
                        needs_encoding = needs_encoding_check(str(filepath))
                        encode_setting = download.get('encode_vp9', True)
                        
                        print(f"[DEBUG] Direct-video encoding decision: needs_encoding={needs_encoding}, encode_vp9={encode_setting}")
                        
                        if needs_encoding and encode_setting:
                            print(f"[DEBUG] ✓ Queuing encoding for direct-video: {filepath}")
                            # Emit encoding_needed signal - EncodingWorker will handle the actual encoding
                            # For direct-video, no yt-dlp info is available
                            metadata_info = {
                                'metadata_option': metadata_option,
                                'info': None,
                                'source_url': download['url']
                            }
                            keep_original = download.get('keep_original', False)
                            self.encoding_needed.emit(self.current_download_id, str(filepath), keep_original, metadata_info)
                            # Don't emit download_complete - EncodingWorker will emit encoding_complete when done
                        else:
                            print(f"[DEBUG] ✗ Skipping encoding for direct-video: needs_encoding={needs_encoding}, encode_vp9={encode_setting}")
                            self.download_complete.emit(download['id'], str(filepath))
                else:
                    # Download video with yt-dlp
                    print(f"[DEBUG] yt-dlp attempting URL: {download['url']}")
                    print(f"[DEBUG] referrer: {download.get('referrer')}")
                    
                    # Skip playlist detection if this video came from a previous playlist selection
                    if download.get('skip_playlist_detection'):
                        print(f"[DEBUG] Skipping playlist detection - already processed")
                    else:
                        # Check if extension already detected multiple videos
                        detected_videos = download.get('detectedVideos')
                        if detected_videos and len(detected_videos) >= 2:
                            print(f"[DEBUG] Extension detected {len(detected_videos)} videos, using those instead of yt-dlp extraction")
                            
                            # Format detected videos for video selector (same format as playlist entries)
                            videos = []
                            for video_data in detected_videos:
                                videos.append({
                                    'url': video_data.get('url'),
                                    'title': video_data.get('title', f"{video_data.get('platform', 'Video')} {video_data.get('id', '')}"),
                                    'thumbnail': None,  # Extension doesn't provide thumbnails yet
                                    'duration': None,
                                    'uploader': None,
                                    'original_title': video_data.get('title', f"{video_data.get('platform', 'Video')} {video_data.get('id', '')}")
                                })
                            
                            # Create playlist data structure
                            playlist_data = {
                                'videos': videos,
                                'pageTitle': f"Multiple Videos ({len(videos)} found)",
                                'pageUrl': download['url'],
                                'source': urlparse(download['url']).hostname or 'unknown'
                            }
                            
                            print(f"[DEBUG] Emitting playlist_detected signal with {len(videos)} extension-detected videos")
                            self.playlist_detected.emit(download['id'], playlist_data)
                            
                            # Continue to next item in queue
                            continue
                    
                    quality = download.get('quality', 'best')

                    # Set format based on quality.
                    # Prefer non-AD (Audio Description) tracks: yt-dlp marks AD tracks
                    # with a "-desc" language suffix (e.g. "en-desc"). We filter these out
                    # first, then fall back to any audio if no regular track is available.
                    if quality == 'bestaudio':
                        format_str = 'bestaudio[language!$=-desc]/bestaudio/best'
                    elif quality == 'best':
                        format_str = 'bestvideo+(bestaudio[language!$=-desc]/bestaudio)/best'
                    elif quality == 'worst':
                        format_str = 'worstvideo+worstaudio/worst'
                    else:
                        # Specific resolution (numeric)
                        format_str = f'bestvideo[height<={quality}]+(bestaudio[language!$=-desc]/bestaudio)/best[height<={quality}]'
                    
                    # Reset logger for this download
                    self.ytdlp_logger.reset()

                    # Base yt-dlp options
                    ydl_opts = {
                        'format': format_str,
                        'progress_hooks': [self.progress_hook],
                        'postprocessor_hooks': [self.postprocessor_hook],
                        'logger': self.ytdlp_logger,  # Custom logger to capture skip messages
                        'quiet': True,
                        'no_warnings': True,
                        'overwrites': False,
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        }
                    }
                    
                    # Add referrer headers if available
                    referrer = download.get('referrer')
                    if referrer:
                        ydl_opts['http_headers']['Referer'] = referrer
                        print(f"[DEBUG] Added Referer header: {referrer}")
                    else:
                        print(f"[DEBUG] No referrer provided")
                    
                    # Use browser cookies for Instagram to avoid rate limiting
                    if 'instagram.com' in download['url']:
                        ydl_opts['cookiesfrombrowser'] = ('firefox',)
                        print(f"[DEBUG] Using Firefox cookies for Instagram")
                    
                    # Add playlist_items if this is a specific item from a carousel
                    playlist_index = download.get('playlist_index')
                    if playlist_index is not None:
                        ydl_opts['playlist_items'] = str(playlist_index)
                        print(f"[DEBUG] Added playlist_items={playlist_index} for carousel item from {download['url']}")
                        print(f"[DEBUG] ydl_opts keys now include: {list(ydl_opts.keys())}")
                    
                    # Add metadata options if enabled (sidecar files)
                    if metadata_option == 'sidecar':
                        metadata_dir = Path(save_path) / '_metadata'
                        metadata_dir.mkdir(parents=True, exist_ok=True)
                        
                        ydl_opts.update({
                            'writethumbnail': True,
                            'writedescription': True,
                            'writeinfojson': True,
                            'writelink': True,
                            'writewebloc': True,
                            'writesubtitles': False,  # Disabled - often causes errors
                            'writeautomaticsub': False,  # Disabled - often causes errors
                            'ignoreerrors': True,  # Continue even if some metadata fails
                            'skip_download': False,  # Ensure video still downloads
                        })
                    
                    # First, get video info to check formats and extract metadata
                    self.status_update.emit(self.current_download_id, 'Preparing...')
                    try:
                        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                            info = ydl.extract_info(download['url'], download=False)
                    except (yt_dlp.DownloadError, yt_dlp.utils.ExtractorError) as extract_error:
                        # Check if this is a Vimeo embed error that we can retry
                        error_str = str(extract_error)
                        print(f"[DEBUG] Info extraction failed with error: {error_str[:500]}...")
                        
                        if self.is_vimeo_embed_error(error_str, download['url']):
                            print(f"[DEBUG] ✓ Detected Vimeo embed error during info extraction, attempting fallback")
                            print(f"[DEBUG] Original URL: {download['url']}")
                            print(f"[DEBUG] Error type: {type(extract_error).__name__}")
                            
                            # Extract Vimeo ID and retry with direct URL
                            vimeo_id = self.extract_vimeo_id(download['url'], error_str)
                            if vimeo_id:
                                fallback_url = f"https://vimeo.com/{vimeo_id}"
                                print(f"[DEBUG] ✓ Extracted Vimeo ID: {vimeo_id}")
                                print(f"[DEBUG] Retrying info extraction with direct Vimeo URL: {fallback_url}")
                                
                                try:
                                    # Update status to show retry
                                    self.status_update.emit(self.current_download_id, 'Retrying with direct URL...')
                                    
                                    # Create fallback ydl_opts preserving original path configuration for info extraction
                                    import copy
                                    fallback_ydl_opts = ydl_opts.copy()
                                    # Override to only extract info, not download
                                    fallback_ydl_opts['quiet'] = True
                                    
                                    # Explicitly copy path-related dictionaries to prevent override
                                    if 'outtmpl' in ydl_opts:
                                        fallback_ydl_opts['outtmpl'] = copy.deepcopy(ydl_opts['outtmpl'])
                                    if 'paths' in ydl_opts:
                                        fallback_ydl_opts['paths'] = copy.deepcopy(ydl_opts['paths'])
                                    
                                    with yt_dlp.YoutubeDL(fallback_ydl_opts) as ydl:
                                        info = ydl.extract_info(fallback_url, download=False)
                                    
                                    print(f"[DEBUG] ✓ Vimeo info extraction fallback successful!")
                                    # Store the original URL before changing it
                                    if '_original_url' not in download:
                                        download['_original_url'] = download['url']
                                    
                                    # Update the download URL to use the direct URL for the actual download
                                    download['url'] = fallback_url
                                    
                                    # Mark that we used a Vimeo fallback - path configuration will happen normally
                                    download['_used_vimeo_fallback'] = True
                                    print(f"[DEBUG] Marked as using Vimeo fallback - normal path config will apply")
                                except Exception as fallback_error:
                                    print(f"[DEBUG] ✗ Vimeo info extraction fallback also failed: {fallback_error}")
                                    print(f"[DEBUG] Fallback error type: {type(fallback_error).__name__}")
                                    raise extract_error  # Re-raise original error
                            else:
                                print(f"[DEBUG] ✗ Could not extract Vimeo ID for fallback")
                                raise extract_error  # Re-raise original error
                        else:
                            print(f"[DEBUG] Not a Vimeo embed error during info extraction, re-raising original error")
                            raise extract_error  # Re-raise original error
                    
                    # Check if video needs encoding
                    needs_encoding = needs_encoding_check(info)
                    print(f"[DEBUG] yt-dlp video encoding check complete: needs_encoding={needs_encoding}")
                    
                    # For Instagram, try multiple ways to get username
                    instagram_username = None
                    # Check if this was originally an Instagram URL (even if it's been changed to a Vimeo fallback)
                    original_url = download.get('_original_url', download['url'])
                    is_instagram = 'instagram.com' in original_url
                    print(f"[DEBUG] Checking Instagram: original_url={original_url}, current_url={download['url']}, is_instagram={is_instagram}")
                    
                    if is_instagram:
                        # Try various fields where username might be stored
                        instagram_username = (info.get('uploader') or 
                                            info.get('uploader_id') or 
                                            info.get('channel') or 
                                            info.get('channel_id') or
                                            info.get('creator'))
                        
                        # If it's a playlist, check the first entry for additional username info
                        if not instagram_username and info.get('_type') == 'playlist' and info.get('entries'):
                            first_entry = info['entries'][0] if info['entries'] else None
                            if first_entry:
                                instagram_username = (first_entry.get('uploader') or 
                                                    first_entry.get('uploader_id') or
                                                    first_entry.get('channel') or
                                                    first_entry.get('creator'))
                        
                        # Set path based on organization preference (for both single videos and playlists)
                        if organize_by_platform:
                            extractor_path = str(Path(save_path) / 'Instagram')
                        else:
                            extractor_path = save_path
                            
                        if instagram_username:
                            base_filename = f'{instagram_username}_%(title).100s_%(id)s'
                        else:
                            base_filename = '%(title).100s_%(id)s'
                        
                        # Configure paths and output templates (for both single videos and playlists)
                        if metadata_option == 'sidecar':
                            # Use platform-specific metadata path (in the same folder as videos)
                            metadata_path = str(Path(extractor_path) / '_metadata')
                            Path(metadata_path).mkdir(parents=True, exist_ok=True)
                            
                            # Set different output templates for video and metadata
                            ydl_opts['outtmpl'] = {
                                'default': str(Path(extractor_path) / f'{base_filename}.%(ext)s'),
                                'thumbnail': str(Path(metadata_path) / f'{base_filename}_thumbnail.%(ext)s'),
                                'description': str(Path(metadata_path) / f'{base_filename}.description'),
                                'infojson': str(Path(metadata_path) / f'{base_filename}.info.json'),
                                'link': str(Path(metadata_path) / f'{base_filename}.url'),
                                'webloc': str(Path(metadata_path) / f'{base_filename}.webloc'),
                                'subtitle': str(Path(metadata_path) / f'{base_filename}.%(ext)s'),
                            }
                        else:
                            ydl_opts['outtmpl'] = f'{base_filename}.%(ext)s'
                            ydl_opts['paths'] = {'home': extractor_path}
                    else:
                        # For all non-Instagram videos (including Vimeo fallbacks), ensure path configuration
                        print(f"[DEBUG] Setting up paths for non-Instagram video")
                        # For other platforms, determine folder based on extractor
                        extractor = info.get('extractor', 'Videos')
                        if 'youtube' in extractor.lower():
                            folder = 'YouTube'
                        elif 'vimeo' in extractor.lower():
                            folder = 'Vimeo'
                        else:
                            folder = extractor
                        
                        if organize_by_platform:
                            extractor_path = str(Path(save_path) / folder)
                        else:
                            extractor_path = save_path
                        
                        base_filename = '%(title).100s'
                        
                        # Configure paths and output templates
                        if metadata_option == 'sidecar':
                            # Use platform-specific metadata path (in the same folder as videos)
                            metadata_path = str(Path(extractor_path) / '_metadata')
                            Path(metadata_path).mkdir(parents=True, exist_ok=True)
                            
                            # Set different output templates for video and metadata
                            ydl_opts['outtmpl'] = {
                                'default': str(Path(extractor_path) / f'{base_filename}.%(ext)s'),
                                'thumbnail': str(Path(metadata_path) / f'{base_filename}_thumbnail.%(ext)s'),
                                'description': str(Path(metadata_path) / f'{base_filename}.description'),
                                'infojson': str(Path(metadata_path) / f'{base_filename}.info.json'),
                                'link': str(Path(metadata_path) / f'{base_filename}.url'),
                                'webloc': str(Path(metadata_path) / f'{base_filename}.webloc'),
                                'subtitle': str(Path(metadata_path) / f'{base_filename}.%(ext)s'),
                            }
                        else:
                            ydl_opts['outtmpl'] = f'{base_filename}.%(ext)s'
                            ydl_opts['paths'] = {'home': extractor_path}
                        
                        # Debug: Show if we used a Vimeo fallback
                        if download.get('_used_vimeo_fallback'):
                            print(f"[DEBUG] This download used Vimeo fallback - paths should be configured normally")
                            print(f"[DEBUG] Current extractor_path: {extractor_path}")
                            print(f"[DEBUG] Current ydl_opts paths: {ydl_opts.get('paths', 'NOT SET')}")
                        
                        # Extract thumbnail URL
                        thumbnail_url = info.get('thumbnail') or info.get('thumbnails', [{}])[0].get('url') if info.get('thumbnails') else None
                        if thumbnail_url:
                            # Emit thumbnail URL to update the UI
                            self.status_update.emit(self.current_download_id, f'thumbnail:{thumbnail_url}')
                        
                        print(f"[DEBUG] Video info - needs encoding: {needs_encoding}")
                    
                    # Download the video
                    try:
                        # Debug: Log actual paths being used for download
                        print(f"[DEBUG] About to download with URL: {download['url']}")
                        print(f"[DEBUG] Final ydl_opts keys: {list(ydl_opts.keys())}")
                        if 'playlist_items' in ydl_opts:
                            print(f"[DEBUG] Final playlist_items: {ydl_opts['playlist_items']}")
                        print(f"[DEBUG] Final http_headers: {ydl_opts.get('http_headers', {})}")
                        if 'outtmpl' in ydl_opts:
                            print(f"[DEBUG] Final outtmpl: {ydl_opts['outtmpl']}")
                        if 'paths' in ydl_opts:
                            print(f"[DEBUG] Final paths: {ydl_opts['paths']}")
                        else:
                            print(f"[DEBUG] No 'paths' key in ydl_opts!")
                        
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            # First, extract info without downloading to check if it's a playlist
                            print(f"[DEBUG] Extracting info for URL: {download['url']}")
                            info = ydl.extract_info(download['url'], download=False)
                            
                            # Check if this is a playlist with multiple entries (unless skipping detection)
                            if download.get('skip_playlist_detection'):
                                print(f"[DEBUG] Skipping yt-dlp playlist detection - already processed")
                            elif info.get('_type') == 'playlist' and len(info.get('entries', [])) > 1:
                                print(f"[DEBUG] Playlist detected with {len(info['entries'])} entries")
                                
                                # Add 1-based index to each entry for playlist_items support
                                for i, entry in enumerate(info.get('entries', [])):
                                    if entry:  # Some entries might be None for unavailable videos
                                        entry['playlist_index'] = i + 1  # yt-dlp uses 1-based indexing
                                        print(f"[DEBUG] Entry {i+1}: id={entry.get('id')}, playlist_index={entry.get('playlist_index')}")
                                
                                # Format playlist entries for video selector
                                videos = []
                                for playlist_idx, entry in enumerate(info.get('entries', []), start=1):
                                    if entry:  # Some entries might be None for unavailable videos
                                        # For Instagram, prioritize webpage_url to avoid CDN URLs causing long filenames
                                        # For Vimeo, prioritize url (embed URL with ?h= hash for private videos)
                                        if entry.get('ie_key') == 'Instagram' or 'instagram.com' in str(entry.get('webpage_url', '')):
                                            entry_url = (entry.get('webpage_url') or 
                                                       entry.get('url') or 
                                                       entry.get('original_url'))
                                        else:
                                            entry_url = (entry.get('url') or 
                                                       entry.get('webpage_url') or 
                                                       entry.get('original_url'))
                                        
                                        # Clean smuggled data but preserve query parameters like ?h=
                                        if entry_url and '#__youtubedl_smuggle=' in entry_url:
                                            entry_url = entry_url.split('#__youtubedl_smuggle=')[0]
                                            print(f"[DEBUG] Cleaned smuggled URL (preserved query params): {entry_url}")
                                        
                                        # Fix malformed URLs with double question marks
                                        if entry_url and '?' in entry_url:
                                            parts = entry_url.split('?')
                                            if len(parts) > 2:
                                                # Keep first ?, replace subsequent ? with &
                                                entry_url = parts[0] + '?' + '&'.join(parts[1:])
                                                print(f"[DEBUG] Fixed double question mark URL: {entry_url}")
                                        
                                        if not entry_url:
                                            # Fallback: construct URL based on platform
                                            if entry.get('ie_key') == 'Vimeo':
                                                entry_url = f"https://vimeo.com/{entry.get('id', '')}"
                                            elif entry.get('ie_key') == 'Youtube':
                                                entry_url = f"https://www.youtube.com/watch?v={entry.get('id', '')}"
                                            elif entry.get('ie_key') == 'Instagram':
                                                # For Instagram, we need the post URL format
                                                entry_url = f"https://instagram.com/p/{entry.get('id', '')}"
                                            else:
                                                entry_url = entry.get('id', 'Unknown')
                                        
                                        videos.append({
                                            'url': entry_url,
                                            'title': entry.get('title', f"Video {len(videos) + 1}"),
                                            'thumbnail': entry.get('thumbnail'),
                                            'duration': entry.get('duration'),
                                            'uploader': entry.get('uploader'),
                                            'original_title': entry.get('title', f"Video {len(videos) + 1}"),
                                            'playlist_index': entry.get('playlist_index')
                                        })
                                
                                # Create playlist data structure similar to video-list from extension
                                playlist_data = {
                                    'videos': videos,
                                    'pageTitle': info.get('title', f"Playlist ({len(videos)} videos)"),
                                    'pageUrl': download['url'],
                                    'source': urlparse(download['url']).hostname or 'unknown'
                                }
                                
                                print(f"[DEBUG] Emitting playlist_detected signal with {len(videos)} videos")
                                self.playlist_detected.emit(download['id'], playlist_data)
                                
                                # Don't proceed with this download - let user select videos
                                # Continue to next item in queue
                                continue
                            
                            # Single video or not a playlist - proceed with download
                            print(f"[DEBUG] Single video detected, proceeding with download")
                            info = ydl.extract_info(download['url'], download=True)
                    except Exception as ytdl_error:
                        # Check if this is a Vimeo embed error that we can retry
                        error_str = str(ytdl_error)
                        print(f"[DEBUG] yt-dlp failed with error: {error_str[:500]}...")
                        
                        if self.is_vimeo_embed_error(error_str, download['url']):
                            print(f"[DEBUG] ✓ Detected Vimeo embed error, attempting fallback")
                            print(f"[DEBUG] Original URL: {download['url']}")
                            print(f"[DEBUG] Error type: {type(ytdl_error).__name__}")
                            
                            # Extract Vimeo ID and retry with direct URL
                            vimeo_id = self.extract_vimeo_id(download['url'], error_str)
                            if vimeo_id:
                                fallback_url = f"https://vimeo.com/{vimeo_id}"
                                print(f"[DEBUG] ✓ Extracted Vimeo ID: {vimeo_id}")
                                print(f"[DEBUG] Retrying with direct Vimeo URL: {fallback_url}")
                                
                                try:
                                    # Update status to show retry
                                    self.status_update.emit(self.current_download_id, 'Retrying with direct URL...')
                                    
                                    # Create fallback ydl_opts preserving all original settings
                                    import copy
                                    fallback_ydl_opts = ydl_opts.copy()
                                    print(f"[DEBUG] Using shallow copy of ydl_opts for fallback download")
                                    print(f"[DEBUG] Fallback ydl_opts keys: {list(fallback_ydl_opts.keys())}")
                                    
                                    # Explicitly copy path-related dictionaries to prevent override
                                    if 'outtmpl' in ydl_opts:
                                        fallback_ydl_opts['outtmpl'] = copy.deepcopy(ydl_opts['outtmpl'])
                                        print(f"[DEBUG] Copied original outtmpl: {fallback_ydl_opts['outtmpl']}")
                                    
                                    if 'paths' in ydl_opts:
                                        fallback_ydl_opts['paths'] = copy.deepcopy(ydl_opts['paths'])
                                        print(f"[DEBUG] Copied original paths: {fallback_ydl_opts['paths']}")
                                    
                                    # Also try to override any extractor-specific templates
                                    if isinstance(original_outtmpl, dict):
                                        print(f"[DEBUG] Original outtmpl is dict with keys: {list(original_outtmpl.keys())}")
                                        # Force the default template to use our custom format
                                        if 'default' in original_outtmpl:
                                            print(f"[DEBUG] Using custom default template: {original_outtmpl['default']}")
                                    elif isinstance(original_outtmpl, str):
                                        print(f"[DEBUG] Original outtmpl is string: {original_outtmpl}")
                                    
                                    with yt_dlp.YoutubeDL(fallback_ydl_opts) as ydl:
                                        info = ydl.extract_info(fallback_url, download=True)
                                    
                                    print(f"[DEBUG] ✓ Vimeo fallback successful!")
                                except Exception as fallback_error:
                                    print(f"[DEBUG] ✗ Vimeo fallback also failed: {fallback_error}")
                                    print(f"[DEBUG] Fallback error type: {type(fallback_error).__name__}")
                                    raise ytdl_error  # Re-raise original error
                            else:
                                print(f"[DEBUG] ✗ Could not extract Vimeo ID for fallback")
                                raise ytdl_error  # Re-raise original error
                        else:
                            print(f"[DEBUG] Not a Vimeo embed error, re-raising original error")
                            raise ytdl_error  # Re-raise original error
                    
                    # Track any files created by yt-dlp for cleanup
                    if info:
                        if info.get('_type') == 'playlist':
                            entries = info.get('entries', [])
                            for entry in entries:
                                if entry:
                                    filename = ydl.prepare_filename(entry)
                                    self.partial_files.add(filename)
                                    print(f"[DEBUG] Tracking playlist file: {filename}")
                                    # Also add common variations and fragment files
                                    base = filename.rsplit('.', 1)[0]
                                    for ext in ['.mp4', '.mkv', '.webm', '.part', '.ytdl']:
                                        self.partial_files.add(base + ext)
                                    # Add fragment patterns
                                    for i in range(10):  # Track first 10 potential fragments
                                        self.partial_files.add(f"{base}.f{i}")
                        else:
                            filename = ydl.prepare_filename(info)
                            self.partial_files.add(filename)
                            print(f"[DEBUG] Tracking single file: {filename}")
                            # Also add common variations and fragment files
                            base = filename.rsplit('.', 1)[0]
                            for ext in ['.mp4', '.mkv', '.webm', '.part', '.ytdl']:
                                self.partial_files.add(base + ext)
                            # Add fragment patterns
                            for i in range(10):  # Track first 10 potential fragments
                                self.partial_files.add(f"{base}.f{i}")
                        
                        # Check if this is a playlist/carousel (multiple files)
                        if '_type' in info and info['_type'] == 'playlist':
                            # Handle playlist/carousel downloads
                            entries = info.get('entries', [])
                            downloaded_files = []
                            
                            for entry in entries:
                                if entry:
                                    filename = ydl.prepare_filename(entry)
                                    possible_files = [
                                        filename,
                                        filename.rsplit('.', 1)[0] + '.mp4',
                                        filename.rsplit('.', 1)[0] + '.mkv',
                                        filename.rsplit('.', 1)[0] + '.webm',
                                    ]
                                    
                                    for path in possible_files:
                                        if os.path.exists(path):
                                            downloaded_files.append(path)
                                            break
                            
                            # For Instagram carousels with sidecar metadata, move stray metadata files
                            if metadata_option == 'sidecar' and 'instagram.com' in download['url']:
                                metadata_path = Path(save_path) / '_metadata'
                                
                                # Look for stray metadata files in the video folder
                                if organize_by_platform:
                                    video_folder = Path(save_path) / 'Instagram'
                                else:
                                    video_folder = Path(save_path)
                                
                                # Move any metadata files that ended up in the wrong place
                                for pattern in ['*.info.json', '*.description', '*.webloc', '*.url']:
                                    for metadata_file in video_folder.glob(pattern):
                                        try:
                                            dest = metadata_path / metadata_file.name
                                            if not dest.exists():
                                                metadata_file.rename(dest)
                                                print(f"Moved metadata file to: {dest}")
                                        except Exception as e:
                                            print(f"Could not move metadata file {metadata_file}: {e}")
                            
                            if downloaded_files:
                                # Remove downloaded files from partial files list
                                for file in downloaded_files:
                                    self.partial_files.discard(file)
                                # For multiple files, use the first one as reference
                                final_path = downloaded_files[0]
                                # Check if ALL files were skipped (playlist skip detection)
                                if self.ytdlp_logger.skipped:
                                    print(f"[DEBUG] ===== PLAYLIST SKIP DETECTED =====")
                                    print(f"[DEBUG] Download ID: {self.current_download_id}")
                                    print(f"[DEBUG] Files found: {len(downloaded_files)}")
                                    skip_reason = f"Files already exist ({len(downloaded_files)} files)"
                                    self.download_skipped.emit(self.current_download_id, skip_reason, final_path)
                                    continue

                                # Check encoding and metadata for playlist/carousel files
                                encode_setting = download.get('encode_vp9', True)
                                any_encoding_queued = False

                                print(f"[DEBUG] ===== PLAYLIST POST-PROCESSING =====")
                                print(f"[DEBUG] Download ID: {self.current_download_id}")
                                print(f"[DEBUG] Files: {len(downloaded_files)}")
                                print(f"[DEBUG] needs_encoding={needs_encoding}, encode_vp9={encode_setting}")
                                print(f"[DEBUG] metadata_option={download.get('metadata_option')}")

                                for file_path in downloaded_files:
                                    if needs_encoding and encode_setting:
                                        print(f"[DEBUG] ✓ Queuing encoding for playlist file: {file_path}")
                                        metadata_info = {
                                            'metadata_option': download.get('metadata_option'),
                                            'info': info,
                                            'source_url': download.get('url')
                                        }
                                        keep_original = download.get('keep_original', False)
                                        self.encoding_needed.emit(self.current_download_id, file_path, keep_original, metadata_info)
                                        any_encoding_queued = True
                                    else:
                                        # Embed metadata directly (no encoding needed)
                                        self.embed_video_metadata_if_requested(
                                            file_path, download.get('metadata_option'), info, download.get('url'))

                                if not any_encoding_queued:
                                    print(f"[DEBUG] ===== EMITTING DOWNLOAD_COMPLETE (PLAYLIST) =====")
                                    print(f"[DEBUG] Download ID: {self.current_download_id}")
                                    print(f"[DEBUG] Files: {len(downloaded_files)}")
                                    self.download_complete.emit(
                                        self.current_download_id,
                                        f"{final_path}|MULTI|{len(downloaded_files)} files"
                                    )
                            else:
                                detailed_error = f"""Download Error: No files found after playlist download

Download Details:
- URL: {download.get('url', 'Unknown')}
- Type: {download.get('type', 'Unknown')}
- Save Path: {download.get('save_path', 'Unknown')}
- Quality: {download.get('quality', 'Unknown')}

Possible Causes:
- Invalid URL or unavailable content
- Network connectivity issues
- Platform restrictions (private/deleted content)
- yt-dlp configuration issues"""
                                self.download_error.emit(self.current_download_id, detailed_error)
                        else:
                            # Single file download (original logic)
                            print(f"[DEBUG] ===== FILE CHECKING AFTER DOWNLOAD =====")
                            print(f"[DEBUG]   self.final_filepath: {self.final_filepath}")
                            print(f"[DEBUG]   info.get('filepath'): {info.get('filepath')}")
                            print(f"[DEBUG]   info.get('_filename'): {info.get('_filename')}")
                            print(f"[DEBUG]   info.get('ext'): {info.get('ext')}")

                            # List files in the save directory to see what actually exists
                            import glob
                            if organize_by_platform:
                                extractor = info.get('extractor', 'Videos')
                                if 'youtube' in extractor.lower():
                                    check_dir = str(Path(save_path) / 'YouTube')
                                elif 'vimeo' in extractor.lower():
                                    check_dir = str(Path(save_path) / 'Vimeo')
                                else:
                                    check_dir = str(Path(save_path) / extractor)
                            else:
                                check_dir = save_path

                            if os.path.exists(check_dir):
                                files_in_dir = glob.glob(os.path.join(check_dir, '*'))
                                print(f"[DEBUG]   Files in {check_dir}:")
                                for f in files_in_dir[-10:]:  # Last 10 files
                                    print(f"[DEBUG]     - {os.path.basename(f)}")
                            else:
                                print(f"[DEBUG]   Directory does not exist: {check_dir}")

                            # First check if postprocessor captured the final filepath (after merging)
                            if self.final_filepath and os.path.exists(self.final_filepath):
                                final_path = self.final_filepath
                                print(f"[DEBUG] ✓ Using postprocessor filepath: {final_path}")
                            else:
                                if self.final_filepath:
                                    print(f"[DEBUG] ✗ Postprocessor filepath doesn't exist: {self.final_filepath}")
                                else:
                                    print(f"[DEBUG] ✗ No postprocessor filepath captured")

                                # Fallback to prepare_filename and check various extensions
                                filename = ydl.prepare_filename(info)
                                print(f"[DEBUG] prepare_filename returned: {filename}")

                                # Handle various extensions (merging may change extension)
                                possible_files = [
                                    filename,
                                    filename.rsplit('.', 1)[0] + '.mp4',
                                    filename.rsplit('.', 1)[0] + '.mkv',
                                    filename.rsplit('.', 1)[0] + '.webm',
                                    filename.rsplit('.', 1)[0] + '.m4a',  # Audio-only
                                ]

                                final_path = None
                                for path in possible_files:
                                    print(f"[DEBUG] Checking for file: {path}")
                                    if os.path.exists(path):
                                        final_path = path
                                        print(f"[DEBUG] ✓ Found file: {path}")
                                        break

                                if not final_path:
                                    print(f"[DEBUG] ✗ No file found in any checked path!")
                            
                            if final_path and self.current_download_id not in self.cancelled_downloads:
                                # Remove from partial files once we have final path
                                self.partial_files.discard(final_path)

                                # Check if file was skipped (already exists)
                                if self.ytdlp_logger.skipped:
                                    print(f"[DEBUG] ===== SKIP DETECTED =====")
                                    print(f"[DEBUG] Download ID: {self.current_download_id}")
                                    print(f"[DEBUG] Download URL: {download.get('url', 'Unknown')}")
                                    print(f"[DEBUG] File path: {final_path}")
                                    print(f"[DEBUG] Logger skip_reason: {self.ytdlp_logger.skip_reason}")
                                    print(f"[DEBUG] Logger skipped_filename: {self.ytdlp_logger.skipped_filename}")
                                    skip_reason = f"File already exists: {os.path.basename(final_path)}"
                                    print(f"[DEBUG] Emitting download_skipped signal for ID: {self.current_download_id}")
                                    self.download_skipped.emit(self.current_download_id, skip_reason, final_path)
                                    print(f"[DEBUG] Signal emitted, now calling continue...")
                                    continue  # Move to next download in queue

                                # Check if we need to encode
                                # NOTE: If we reach here, skip was NOT detected (continue would have skipped this)
                                print(f"[DEBUG] ===== PROCEEDING TO ENCODE/COMPLETE (skip was False) =====")
                                print(f"[DEBUG] Download ID: {self.current_download_id}")
                                print(f"[DEBUG] yt-dlp single video download complete: {final_path}")
                                print(f"[DEBUG] Download type: yt-dlp single video")
                                print(f"[DEBUG] encode_vp9 setting: {download.get('encode_vp9', True)}")
                                
                                encode_setting = download.get('encode_vp9', True)
                                print(f"[DEBUG] yt-dlp encoding decision: needs_encoding={needs_encoding}, encode_vp9={encode_setting}")
                                
                                if needs_encoding and encode_setting:
                                    print(f"[DEBUG] ✓ Queuing encoding for yt-dlp video: {final_path}")
                                    # Emit encoding_needed signal - EncodingWorker will handle the actual encoding
                                    metadata_info = {
                                        'metadata_option': download.get('metadata_option'),
                                        'info': info,
                                        'source_url': download.get('url')
                                    }
                                    keep_original = download.get('keep_original', False)
                                    self.encoding_needed.emit(self.current_download_id, final_path, keep_original, metadata_info)
                                    # Don't emit download_complete - EncodingWorker will emit encoding_complete when done
                                else:
                                    print(f"[DEBUG] ✗ Skipping encoding for yt-dlp video: needs_encoding={needs_encoding}, encode_vp9={encode_setting}")
                                    # Embed metadata if requested
                                    self.embed_video_metadata_if_requested(final_path, download.get('metadata_option'), info, download.get('url'))
                                    print(f"[DEBUG] ===== EMITTING DOWNLOAD_COMPLETE =====")
                                    print(f"[DEBUG] Download ID: {self.current_download_id}")
                                    print(f"[DEBUG] Path: {final_path}")
                                    print(f"[DEBUG] Logger skipped state: {self.ytdlp_logger.skipped}")
                                    self.download_complete.emit(self.current_download_id, final_path)
                            else:
                                if self.current_download_id in self.cancelled_downloads:
                                    # This will be handled in the exception handler
                                    pass
                                else:
                                    detailed_error = f"""Download Error: File not found after download

Download Details:
- URL: {download.get('url', 'Unknown')}
- Type: {download.get('type', 'Unknown')}
- Expected Path: {filename if 'filename' in locals() else 'Unknown'}
- Save Directory: {download.get('save_path', 'Unknown')}

Possible Causes:
- Download completed but file was moved or deleted
- Permission issues preventing file creation
- Insufficient disk space during download
- Network interruption during final write
- Anti-virus software quarantined the file"""
                                    self.download_error.emit(self.current_download_id, detailed_error)
                            
            except Exception as e:
                print(f"[DEBUG] Exception in download loop for {self.current_download_id}: {str(e)}")
                
                if self.current_download_id in self.cancelled_downloads:
                    print(f"[DEBUG] Handling cancellation in exception handler for {self.current_download_id}")
                    # Clean up partial files and emit cancellation signal
                    self.cleanup_partial_files(self.current_download_id)
                    self.download_cancelled.emit(self.current_download_id)
                elif "Download cancelled by user" in str(e):
                    print(f"[DEBUG] Detected cancellation via exception message for {self.current_download_id}")
                    # This might be a cancellation that wasn't caught properly
                    self.cancelled_downloads.add(self.current_download_id)
                    self.cleanup_partial_files(self.current_download_id)
                    self.download_cancelled.emit(self.current_download_id)
                else:
                    # Create detailed error message
                    import traceback
                    detailed_error = f"""Exception Type: {type(e).__name__}
Error Message: {str(e)}

Download Details:
- URL: {download.get('url', 'Unknown')}
- Type: {download.get('type', 'Unknown')}
- Save Path: {download.get('save_path', 'Unknown')}

Stack Trace:
{traceback.format_exc()}"""
                    
                    self.download_error.emit(self.current_download_id, detailed_error)
                    
            # Clean up cancelled flag
            if self.current_download_id in self.cancelled_downloads:
                self.cancelled_downloads.remove(self.current_download_id)