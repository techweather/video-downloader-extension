"""
Download worker and core downloading functionality for Media Downloader App
"""

import os
import sys
import requests
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, unquote

from PyQt5.QtCore import QThread, pyqtSignal
import yt_dlp

from .encoder import VideoEncoder, needs_encoding_check


def get_bundled_ffmpeg_path():
    """
    Get the path to bundled ffmpeg binary when running from PyInstaller bundle.
    
    Returns:
        str or None: Path to ffmpeg binary if found, None otherwise
    """
    try:
        if getattr(sys, 'frozen', False):
            # Running from PyInstaller bundle
            bundle_dir = Path(sys._MEIPASS)
            ffmpeg_path = bundle_dir / 'ffmpeg'
            
            if ffmpeg_path.exists() and ffmpeg_path.is_file():
                print(f"[DEBUG] Found bundled ffmpeg at: {ffmpeg_path}")
                return str(ffmpeg_path)
            else:
                print(f"[DEBUG] Bundled ffmpeg not found at: {ffmpeg_path}")
        else:
            # Running from source - try system ffmpeg
            import shutil
            system_ffmpeg = shutil.which('ffmpeg')
            if system_ffmpeg:
                print(f"[DEBUG] Using system ffmpeg at: {system_ffmpeg}")
                return system_ffmpeg
            
        print("[DEBUG] No ffmpeg found - some video processing may fail")
        return None
        
    except Exception as e:
        print(f"[DEBUG] Error finding ffmpeg: {e}")
        return None

class DownloadWorker(QThread):
    progress_update = pyqtSignal(str, int, str)  # id, percent, status
    download_complete = pyqtSignal(str, str)  # id, path
    download_error = pyqtSignal(str, str)  # id, error
    download_cancelled = pyqtSignal(str)  # id
    status_update = pyqtSignal(str, str)  # id, status
    
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
            
            self.progress_update.emit(
                self.current_download_id,
                percent,
                f"Downloading... {percent}%"
            )
        elif d['status'] == 'finished':
            self.progress_update.emit(
                self.current_download_id,
                100,
                "Processing..."
            )
    
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
        print(f"[ENCODING DEBUG] Starting H.264 encoding for {download_id}: input={input_path}")
        
        def progress_callback(percent, status):
            """Callback to emit progress updates"""
            self.progress_update.emit(download_id, percent, status)
        
        keep_original = self.current_download_info.get('keep_original', False)
        print(f"[ENCODING DEBUG] Encoding parameters: keep_original={keep_original}")
        
        result = self.encoder.encode_to_h264(input_path, keep_original, progress_callback)
        print(f"[ENCODING DEBUG] Encoding completed for {download_id}: result={result}")
        return result
    
    def extract_vimeo_id(self, url, error_message=None):
        """Extract Vimeo video ID from URL, error message, or page HTML"""
        print(f"[VIMEO DEBUG] *** FUNCTION ENTRY: extract_vimeo_id called in PyInstaller bundle ***")
        print(f"[VIMEO DEBUG] Python executable: {sys.executable}")
        print(f"[VIMEO DEBUG] Running from frozen bundle: {getattr(sys, 'frozen', False)}")
        print(f"[VIMEO DEBUG] === STARTING VIMEO ID EXTRACTION ===")
        print(f"[VIMEO DEBUG] Target URL: {url}")
        print(f"[VIMEO DEBUG] Has error message: {error_message is not None}")
        if error_message:
            print(f"[VIMEO DEBUG] Error message preview: {str(error_message)[:200]}...")
        
        # Pattern 1: Direct Vimeo URL patterns
        vimeo_patterns = [
            r'vimeo\.com/(?:video/)?(\d+)',
            r'player\.vimeo\.com/video/(\d+)',
            r'vimeo\.com/channels/[^/]+/(\d+)',
            r'vimeo\.com/groups/[^/]+/videos/(\d+)',
        ]
        
        print(f"[VIMEO DEBUG] Testing {len(vimeo_patterns)} URL patterns...")
        for i, pattern in enumerate(vimeo_patterns):
            print(f"[VIMEO DEBUG] Pattern {i+1}: '{pattern}' against '{url}'")
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                print(f"[VIMEO DEBUG] ✅ SUCCESS! URL pattern {i+1} matched, extracted ID: {video_id}")
                return video_id
            else:
                print(f"[VIMEO DEBUG] ❌ Pattern {i+1} no match")
        
        print(f"[VIMEO DEBUG] No URL patterns matched")
        
        # Pattern 2: Check error message for embedded IDs
        if error_message:
            print(f"[VIMEO DEBUG] Analyzing error message for Vimeo ID...")
            error_patterns = [
                r'\[vimeo\]\s*(\d+)',  # Matches '[vimeo] 1108703340' format
                r'video/(\d+)',
                r'vimeo\.com/(\d+)',
                r'id["\']?\s*:\s*["\']?(\d+)["\']?',
            ]
            
            for i, pattern in enumerate(error_patterns):
                print(f"[VIMEO DEBUG] Error pattern {i+1}: '{pattern}'")
                match = re.search(pattern, str(error_message), re.IGNORECASE)
                if match:
                    video_id = match.group(1)
                    print(f"[VIMEO DEBUG] ✅ SUCCESS! Error pattern {i+1} matched, extracted ID: {video_id}")
                    return video_id
                else:
                    print(f"[VIMEO DEBUG] ❌ Error pattern {i+1} no match")
            print(f"[VIMEO DEBUG] No error message patterns matched")
        else:
            print(f"[VIMEO DEBUG] No error message provided for analysis")
        
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
        print(f"[VIMEO DEBUG] *** FUNCTION ENTRY: is_vimeo_embed_error called in PyInstaller bundle ***")
        print(f"[VIMEO DEBUG] Python executable: {sys.executable}")
        print(f"[VIMEO DEBUG] Running from frozen bundle: {getattr(sys, 'frozen', False)}")
        print(f"[VIMEO DEBUG] === ANALYZING ERROR FOR VIMEO EMBED DETECTION ===")
        print(f"[VIMEO DEBUG] URL: {url}")
        print(f"[VIMEO DEBUG] Error message (first 300 chars): {str(error_message)[:300]}...")
        
        error_lower = str(error_message).lower()
        
        # Check for Vimeo-related errors
        vimeo_indicator_checks = [
            ('vimeo in error', 'vimeo' in error_lower),
            ('player.vimeo.com in error', 'player.vimeo.com' in error_lower),
            ('vimeo domain in URL', any(pattern in url.lower() for pattern in ['vimeo.com', 'player.vimeo.com']))
        ]
        
        matching_vimeo_indicators = [name for name, condition in vimeo_indicator_checks if condition]
        print(f"[VIMEO DEBUG] Vimeo indicators found: {matching_vimeo_indicators}")
        
        # Check for access-related errors
        access_error_checks = [
            ('401 status', '401' in str(error_message)),
            ('403 status', '403' in str(error_message)),
            ('unauthorized', 'unauthorized' in error_lower),
            ('forbidden', 'forbidden' in error_lower),
            ('private', 'private' in error_lower),
            ('embed restricted', 'embed' in error_lower and 'restricted' in error_lower),
            ('not available embed', 'not available' in error_lower and 'embed' in error_lower),
        ]
        
        matching_access_errors = [name for name, condition in access_error_checks if condition]
        print(f"[VIMEO DEBUG] Access error patterns found: {matching_access_errors}")
        
        has_vimeo = len(matching_vimeo_indicators) > 0
        has_access_error = len(matching_access_errors) > 0
        
        result = has_vimeo and has_access_error
        print(f"[VIMEO DEBUG] Final decision: has_vimeo={has_vimeo}, has_access_error={has_access_error}, is_vimeo_embed_error={result}")
        
        return result
    
    def run(self):
        # Verify Vimeo functions are accessible in bundled app
        print(f"[VIMEO DEBUG] *** STARTUP VERIFICATION ***")
        print(f"[VIMEO DEBUG] Running from frozen bundle: {getattr(sys, 'frozen', False)}")
        print(f"[VIMEO DEBUG] extract_vimeo_id method exists: {hasattr(self, 'extract_vimeo_id')}")
        print(f"[VIMEO DEBUG] is_vimeo_embed_error method exists: {hasattr(self, 'is_vimeo_embed_error')}")
        
        while True:
            download = self.download_queue.get()
            if download is None:
                break
                
            self.current_download_id = download['id']
            self.current_download_info = download  # Store for encoding options
            self.has_emitted_downloading_status = False  # Reset for new download
            
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
                save_metadata = download.get('save_metadata', False)
                
                if download['type'] == 'image':
                    # Download image with referrer
                    self.status_update.emit(self.current_download_id, 'downloading')
                    referrer = download.get('referrer')
                    filepath = self.download_image(download['url'], download['id'], save_path, organize_by_platform, referrer)
                    
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
                        self.download_complete.emit(download['id'], str(filepath))
                else:
                    # Download video with yt-dlp
                    quality = download.get('quality', 'best')
                    
                    # Set format based on quality
                    if quality == 'bestaudio':
                        format_str = 'bestaudio/best'
                    elif quality == 'best':
                        format_str = 'bestvideo+bestaudio/best'
                    else:
                        # Specific resolution
                        format_str = f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]'
                    
                    # Base yt-dlp options
                    ydl_opts = {
                        'format': format_str,
                        'progress_hooks': [self.progress_hook],
                        'quiet': True,
                        'no_warnings': True,
                        'overwrites': False,
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        }
                    }
                    
                    # Set ffmpeg path for bundled applications
                    ffmpeg_path = get_bundled_ffmpeg_path()
                    if ffmpeg_path:
                        print(f"[DEBUG] Setting yt-dlp ffmpeg_location to: {ffmpeg_path}")
                        ydl_opts['ffmpeg_location'] = ffmpeg_path
                        
                        # Also try to set ffprobe location if available
                        import shutil
                        if getattr(sys, 'frozen', False):
                            # Running from PyInstaller bundle - check for bundled ffprobe
                            bundle_dir = Path(sys._MEIPASS)
                            ffprobe_path = bundle_dir / 'ffprobe'
                            if ffprobe_path.exists():
                                print(f"[DEBUG] Found bundled ffprobe at: {ffprobe_path}")
                        else:
                            # Running from source - try system ffprobe
                            ffprobe_path = shutil.which('ffprobe')
                            if ffprobe_path:
                                print(f"[DEBUG] Found system ffprobe at: {ffprobe_path}")
                        
                        # Additional ffmpeg-related options for yt-dlp
                        ydl_opts.update({
                            'prefer_ffmpeg': True,  # Prefer ffmpeg over other tools
                            'postprocessor_args': {
                                'ffmpeg': ['-movflags', 'faststart']  # Optimize for streaming
                            }
                        })
                        print(f"[DEBUG] Enhanced yt-dlp with prefer_ffmpeg and post-processor args")
                        
                        # Also set environment variable as fallback
                        ffmpeg_dir = str(Path(ffmpeg_path).parent)
                        current_path = os.environ.get('PATH', '')
                        if ffmpeg_dir not in current_path:
                            os.environ['PATH'] = ffmpeg_dir + os.pathsep + current_path
                            print(f"[DEBUG] Added ffmpeg directory to PATH: {ffmpeg_dir}")
                    else:
                        print("[DEBUG] No ffmpeg found - yt-dlp will use system PATH or fail")
                    
                    # Add referrer headers if available
                    referrer = download.get('referrer')
                    if referrer:
                        print(f"[VIMEO DEBUG] Adding referrer header: {referrer}")
                        ydl_opts['http_headers']['Referer'] = referrer
                    else:
                        print(f"[VIMEO DEBUG] No referrer provided for this download")
                    
                    # Debug: Print final ydl_opts for ffmpeg-related settings
                    ffmpeg_settings = {k: v for k, v in ydl_opts.items() if 'ffmpeg' in k.lower()}
                    if ffmpeg_settings:
                        print(f"[DEBUG] yt-dlp ffmpeg settings: {ffmpeg_settings}")
                    
                    prefer_ffmpeg = ydl_opts.get('prefer_ffmpeg', False)
                    print(f"[DEBUG] yt-dlp prefer_ffmpeg: {prefer_ffmpeg}")
                    
                    # Add metadata options if enabled
                    if save_metadata:
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
                        # Use full ydl_opts for info extraction to ensure ffmpeg is available
                        info_ydl_opts = ydl_opts.copy()
                        info_ydl_opts['quiet'] = True
                        print(f"[DEBUG] Creating YoutubeDL instance for info extraction with ffmpeg_location: {info_ydl_opts.get('ffmpeg_location', 'Not set')}")
                        
                        with yt_dlp.YoutubeDL(info_ydl_opts) as ydl:
                            # Verify ffmpeg path is accessible for info extraction
                            ffmpeg_loc = info_ydl_opts.get('ffmpeg_location')
                            if ffmpeg_loc and os.path.exists(ffmpeg_loc):
                                print(f"[DEBUG] yt-dlp info extraction: ffmpeg path verified: {ffmpeg_loc}")
                                try:
                                    # Quick test to see if ffmpeg responds
                                    import subprocess
                                    result = subprocess.run([ffmpeg_loc, '-version'], 
                                                          capture_output=True, text=True, timeout=5)
                                    if result.returncode == 0:
                                        print(f"[DEBUG] ffmpeg responds correctly for info extraction")
                                    else:
                                        print(f"[DEBUG] ffmpeg version check failed for info extraction: {result.returncode}")
                                except Exception as e:
                                    print(f"[DEBUG] ffmpeg test failed for info extraction: {e}")
                            else:
                                print(f"[DEBUG] ffmpeg_location not set for info extraction: {ffmpeg_loc}")
                                
                            info = ydl.extract_info(download['url'], download=False)
                    except (yt_dlp.DownloadError, yt_dlp.utils.ExtractorError) as extract_error:
                        # Check if this is a Vimeo embed error that we can retry
                        error_str = str(extract_error)
                        print(f"[DEBUG] Info extraction failed with error: {error_str[:500]}...")
                        
                        print(f"[VIMEO DEBUG] *** ABOUT TO CALL is_vimeo_embed_error from info extraction error handler ***")
                        if self.is_vimeo_embed_error(error_str, download['url']):
                            print(f"[VIMEO DEBUG] ✅ DETECTED: Vimeo embed error during info extraction, attempting fallback")
                            print(f"[VIMEO DEBUG] Original URL: {download['url']}")
                            print(f"[VIMEO DEBUG] Error type: {type(extract_error).__name__}")
                            print(f"[VIMEO DEBUG] Current referrer: {download.get('referrer', 'None')}")
                            
                            # Extract Vimeo ID and retry with direct URL
                            print(f"[VIMEO DEBUG] *** ABOUT TO CALL extract_vimeo_id from info extraction fallback ***")
                            vimeo_id = self.extract_vimeo_id(download['url'], error_str)
                            if vimeo_id:
                                fallback_url = f"https://vimeo.com/{vimeo_id}"
                                print(f"[VIMEO DEBUG] ✅ SUCCESS: Extracted Vimeo ID: {vimeo_id}")
                                print(f"[VIMEO DEBUG] Generated fallback URL: {fallback_url}")
                                print(f"[VIMEO DEBUG] Will preserve referrer: {download.get('referrer', 'None')}")
                                
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
                                    
                                    print(f"[VIMEO DEBUG] ✅ SUCCESS: Vimeo info extraction fallback completed!")
                                    print(f"[VIMEO DEBUG] Info extraction successful with direct URL")
                                    
                                    # Store the original URL before changing it
                                    if '_original_url' not in download:
                                        download['_original_url'] = download['url']
                                        print(f"[VIMEO DEBUG] Stored original URL: {download['_original_url']}")
                                    
                                    # Update the download URL to use the direct URL for the actual download
                                    download['url'] = fallback_url
                                    print(f"[VIMEO DEBUG] Updated download URL to: {download['url']}")
                                    
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
                    except Exception as general_error:
                        print(f"[ERROR] Unexpected error during info extraction: {general_error}")
                        self.download_error.emit(self.current_download_id, f"Info extraction failed: {str(general_error)}")
                        continue
                    
                    # Validate info extraction result before proceeding
                    if not info:
                        print(f"[ERROR] Info extraction returned None or empty result for URL: {download['url']}")
                        self.download_error.emit(self.current_download_id, "Failed to extract video information")
                        continue
                    
                    # Check if video needs encoding with safe error handling
                    try:
                        needs_encoding = needs_encoding_check(info)
                        print(f"[ENCODING DEBUG] Download {self.current_download_id}: needs_encoding={needs_encoding}, encode_vp9 setting={download.get('encode_vp9', True)}")
                    except Exception as encoding_check_error:
                        print(f"[ERROR] Error checking encoding requirements: {encoding_check_error}")
                        # Default to no encoding needed if check fails
                        needs_encoding = False
                        print(f"[ENCODING DEBUG] Defaulting to needs_encoding=False due to check error")
                    
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
                        if save_metadata:
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
                        if save_metadata:
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
                        if 'outtmpl' in ydl_opts:
                            print(f"[DEBUG] Final outtmpl: {ydl_opts['outtmpl']}")
                        if 'paths' in ydl_opts:
                            print(f"[DEBUG] Final paths: {ydl_opts['paths']}")
                        else:
                            print(f"[DEBUG] No 'paths' key in ydl_opts!")
                        
                        print(f"[DEBUG] Starting download with ffmpeg_location: {ydl_opts.get('ffmpeg_location', 'Not set')}")
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(download['url'], download=True)
                    except Exception as ytdl_error:
                        # Check if this is a Vimeo embed error that we can retry
                        error_str = str(ytdl_error)
                        print(f"[DEBUG] yt-dlp failed with error: {error_str[:500]}...")
                        
                        print(f"[VIMEO DEBUG] *** ABOUT TO CALL is_vimeo_embed_error from download error handler ***")
                        if self.is_vimeo_embed_error(error_str, download['url']):
                            print(f"[VIMEO DEBUG] ✅ DETECTED: Vimeo embed error during download, attempting fallback")
                            print(f"[VIMEO DEBUG] Original URL: {download['url']}")
                            print(f"[VIMEO DEBUG] Error type: {type(ytdl_error).__name__}")
                            print(f"[VIMEO DEBUG] Current referrer: {download.get('referrer', 'None')}")
                            
                            # Extract Vimeo ID and retry with direct URL
                            print(f"[VIMEO DEBUG] *** ABOUT TO CALL extract_vimeo_id from download fallback ***")
                            vimeo_id = self.extract_vimeo_id(download['url'], error_str)
                            if vimeo_id:
                                fallback_url = f"https://vimeo.com/{vimeo_id}"
                                print(f"[VIMEO DEBUG] ✅ SUCCESS: Extracted Vimeo ID: {vimeo_id}")
                                print(f"[VIMEO DEBUG] Generated fallback URL: {fallback_url}")
                                print(f"[VIMEO DEBUG] Will preserve referrer in fallback: {download.get('referrer', 'None')}")
                                
                                try:
                                    # Update status to show retry
                                    self.status_update.emit(self.current_download_id, 'Retrying with direct URL...')
                                    
                                    # Create fallback ydl_opts preserving all original settings
                                    import copy
                                    fallback_ydl_opts = ydl_opts.copy()
                                    print(f"[DEBUG] Using shallow copy of ydl_opts for fallback download")
                                    print(f"[DEBUG] Fallback ydl_opts keys: {list(fallback_ydl_opts.keys())}")
                                    print(f"[DEBUG] Fallback download with ffmpeg_location: {fallback_ydl_opts.get('ffmpeg_location', 'Not set')}")
                                    
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
                                    
                                    print(f"[VIMEO DEBUG] ✅ SUCCESS: Vimeo download fallback completed successfully!")
                                except Exception as fallback_error:
                                    print(f"[VIMEO DEBUG] ❌ FAILED: Vimeo download fallback also failed: {fallback_error}")
                                    print(f"[VIMEO DEBUG] Fallback error type: {type(fallback_error).__name__}")
                                    raise ytdl_error  # Re-raise original error
                            else:
                                print(f"[VIMEO DEBUG] ❌ FAILED: Could not extract Vimeo ID for download fallback")
                                raise ytdl_error  # Re-raise original error
                        else:
                            print(f"[DEBUG] Not a Vimeo embed error, re-raising original error")
                            raise ytdl_error  # Re-raise original error
                    
                    # Validate download extraction result before proceeding
                    if not info:
                        print(f"[ERROR] Download extraction returned None or empty result for URL: {download['url']}")
                        self.download_error.emit(self.current_download_id, "Failed to extract download information")
                        continue
                    
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
                            
                            # For Instagram carousels with metadata enabled, move stray metadata files
                            if save_metadata and 'instagram.com' in download['url']:
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
                            filename = ydl.prepare_filename(info)
                            
                            # Handle various extensions
                            possible_files = [
                                filename,
                                filename.rsplit('.', 1)[0] + '.mp4',
                                filename.rsplit('.', 1)[0] + '.mkv',
                                filename.rsplit('.', 1)[0] + '.webm',
                            ]
                            
                            final_path = None
                            for path in possible_files:
                                if os.path.exists(path):
                                    final_path = path
                                    break
                            
                            if final_path and self.current_download_id not in self.cancelled_downloads:
                                # Remove from partial files once we have final path
                                self.partial_files.discard(final_path)
                                
                                # Check if we need to encode
                                print(f"[ENCODING DEBUG] Making encoding decision for {self.current_download_id}: needs_encoding={needs_encoding}, encode_vp9={download.get('encode_vp9', True)}, file={final_path}")
                                if needs_encoding and download.get('encode_vp9', True):
                                    print(f"[ENCODING DEBUG] Starting encoding for {self.current_download_id}")
                                    self.status_update.emit(self.current_download_id, 'encoding')
                                    # Track encoding files for cleanup
                                    encoded_file = final_path.rsplit('.', 1)[0] + '_h264.mp4'
                                    self.partial_files.add(encoded_file)
                                    
                                    encoded_path = self.encode_to_h264(final_path, self.current_download_id)
                                    if encoded_path and self.current_download_id not in self.cancelled_downloads:
                                        self.partial_files.discard(encoded_path)
                                        self.download_complete.emit(self.current_download_id, encoded_path)
                                    elif self.current_download_id in self.cancelled_downloads:
                                        # Encoding was cancelled - use original file as successful result
                                        print(f"[DEBUG] Encoding cancelled for {self.current_download_id}, using original file: {final_path}")
                                        if os.path.exists(final_path):
                                            self.download_complete.emit(self.current_download_id, final_path)
                                        else:
                                            self.download_error.emit(self.current_download_id, "Original file not found after encoding cancellation")
                                    else:
                                        # Encoding failed but not cancelled - check if original file exists
                                        print(f"[DEBUG] Encoding failed for {self.current_download_id}, checking original file: {final_path}")
                                        if os.path.exists(final_path):
                                            print(f"[DEBUG] Using original file as fallback: {final_path}")
                                            self.download_complete.emit(self.current_download_id, final_path)
                                        else:
                                            detailed_error = f"""Download Error: Encoding failed and original file not found

Download Details:
- URL: {download.get('url', 'Unknown')}
- Type: {download.get('type', 'Unknown')} 
- Original File: {final_path if 'final_path' in locals() else 'Unknown'}
- Encode Settings: VP9 to H.264

Possible Causes:
- FFmpeg not installed or not in PATH
- Insufficient disk space
- File corruption during encoding
- Original file was deleted or moved
- Encoding process interrupted"""
                                            self.download_error.emit(self.current_download_id, detailed_error)
                                else:
                                    print(f"[ENCODING DEBUG] Skipping encoding for {self.current_download_id} - using original file: {final_path}")
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