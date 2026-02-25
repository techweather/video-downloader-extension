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

from .encoder import VideoEncoder, file_needs_encoding, get_ffmpeg_dir
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
            self.skipped = True
            self.skip_reason = msg
            # Try to extract filename from message
            # Format is typically: "[download] filename has already been downloaded"
            if msg.startswith('[download]'):
                parts = msg.split(' has already been downloaded')
                if parts:
                    self.skipped_filename = parts[0].replace('[download]', '').strip()

    def warning(self, msg):
        pass

    def error(self, msg):
        pass

    def reset(self):
        """Reset state for a new download."""
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
        
        # Get current download info for directory scanning
        download_info = getattr(self, 'current_download_info', {})
        save_path = download_info.get('save_path', str(Path.home() / 'Downloads' / 'dlwithit'))
        
        # Clean up tracked files
        files_to_remove = list(self.partial_files)
        self.partial_files.clear()
        cleaned_count = 0
        
        for filepath in files_to_remove:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    cleaned_count += 1
                else:
                    pass
            except Exception as e:
                pass
        
        # Additional cleanup for yt-dlp fragment files
        self._cleanup_ytdlp_fragments(save_path)
        
    
    def _cleanup_ytdlp_fragments(self, base_path):
        """Clean up yt-dlp fragment files and temporary files"""
        
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
                                    except Exception:
                                        pass
                                else:
                                    pass
                    except Exception:
                        pass

        except Exception:
            pass
    
    def progress_hook(self, d):
        # Check if cancelled
        if self.current_download_id in self.cancelled_downloads:
            raise Exception("Download cancelled by user")

        # Log progress hook calls to help debug skip issues
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
                self.final_filepath = filepath
            else:
                # Try alternative keys
                alt_filepath = info_dict.get('_filename') or info_dict.get('filename')
                if alt_filepath:
                    self.final_filepath = alt_filepath

    
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

            # Strategy: Start with minimal headers (matches thumbnail behavior which works),
            # then escalate to browser-like headers with Referer if the simple request fails.
            # CDNs like Sanity respond with 'Vary: Origin' and reject requests that include
            # an Origin header from an unrecognized domain, but accept requests with no Origin at all.

            header_strategies = [
                # Strategy 1: Minimal headers (matches working thumbnail fetch)
                {
                    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                },
                # Strategy 2: Add User-Agent (some servers require it)
                {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                },
                # Strategy 3: Add Referer (no Origin) for hotlink-protected servers
                {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                    'Referer': referrer or '',
                },
            ]

            # Remove strategy 3 if no referrer available
            if not referrer:
                header_strategies = header_strategies[:2]


            response = None
            for i, headers in enumerate(header_strategies):
                response = requests.get(url, stream=True, headers=headers, timeout=30)

                if response.status_code != 403:
                    break


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
        return self.encoder.encode_to_h264(input_path, keep_original, progress_callback)
    
    def extract_vimeo_id(self, url, error_message=None):
        """Extract Vimeo video ID from URL, error message, or page HTML"""
        
        # Pattern 1: Direct Vimeo URL patterns
        vimeo_patterns = [
            r'vimeo\.com/(?:video/)?(\d+)',
            r'player\.vimeo\.com/video/(\d+)',
            r'vimeo\.com/channels/[^/]+/(\d+)',
            r'vimeo\.com/groups/[^/]+/videos/(\d+)',
        ]
        
        for i, pattern in enumerate(vimeo_patterns):
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                return video_id
        
        # Pattern 2: Check error message for embedded IDs
        if error_message:
            error_patterns = [
                r'\[vimeo\]\s*(\d+)',  # Matches '[vimeo] 1108703340' format
                r'video/(\d+)',
                r'vimeo\.com/(\d+)',
                r'id["\']?\s*:\s*["\']?(\d+)["\']?',
            ]
            
            for i, pattern in enumerate(error_patterns):
                match = re.search(pattern, error_message)
                if match:
                    video_id = match.group(1)
                    return video_id

        # Pattern 3: Fetch page HTML and extract ID
        try:
            referrer = self.current_download_info.get('referrer')
            if referrer:
                # Validate and fix URL scheme
                if referrer.startswith('www.'):
                    referrer = 'https://' + referrer
                elif not referrer.startswith(('http://', 'https://')):
                    referrer = 'https://' + referrer
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                }
                response = requests.get(referrer, headers=headers, timeout=10)
                html_content = response.text
                
                # Look for Vimeo IDs in HTML
                html_patterns = [
                    r'"video_id"\s*:\s*"?(\d+)"?',
                    r'"id"\s*:\s*(\d+)',
                    r'vimeo\.com/(?:video/)?(\d+)',
                    r'player\.vimeo\.com/video/(\d+)',
                    r'data-vimeo-id["\']?\s*=\s*["\']?(\d+)["\']?',
                    r'vimeo_video_id["\']?\s*:\s*["\']?(\d+)["\']?',
                ]
                
                for i, pattern in enumerate(html_patterns):
                    match = re.search(pattern, html_content, re.IGNORECASE)
                    if match:
                        video_id = match.group(1)
                        # Show context around the match
                        match_start = max(0, match.start() - 50)
                        match_end = min(len(html_content), match.end() + 50)
                        context = html_content[match_start:match_end]
                        return video_id
        except Exception:
            pass

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
        
        return has_vimeo and has_access_error
    
    def embed_video_metadata_if_requested(self, filepath, metadata_option, info, source_url):
        """
        Embed metadata into video file if embedded metadata is requested

        Args:
            filepath (str): Path to the video file
            metadata_option (str): Metadata option ('embedded', 'sidecar', 'none')
            info (dict): yt-dlp info dictionary with video metadata
            source_url (str): Original source URL (prefer page URL over CDN URL)

        Returns:
            bool: True if embedding was attempted (regardless of success)
        """
        if metadata_option != 'embedded':
            return False

        if not info:
            return False

        # Extract metadata from info dict
        title = info.get('title', 'Downloaded Video')
        description = info.get('description', '')
        uploader = info.get('uploader') or info.get('channel') or info.get('uploader_id')
        # Prefer our source_url (which comes from referrer/page URL) over yt-dlp's webpage_url
        # (which for generic/HLS downloads is the CDN URL, not the artist's page)
        webpage_url = source_url or info.get('webpage_url', '')

        # For generic/HLS downloads, yt-dlp returns useless titles like "playlist".
        # Use our download title from the current_download_info if available.
        if title.lower() in ('playlist', 'master', 'index', 'video', 'downloaded video'):
            our_title = self.current_download_info.get('title') if self.current_download_info else None
            if our_title:
                title = our_title
        
        # Truncate description if too long (metadata fields have limits)
        if description and len(description) > 500:
            description = description[:497] + "..."
            
        
        # Embed metadata into video
        embed_success = embed_video_metadata(
            filepath=filepath,
            source_url=webpage_url,
            title=title,
            description=description,
            uploader=uploader
        )
        
        return True
    
    def run(self):
        while True:
            download = self.download_queue.get()
            if download is None:
                break
            

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
                save_path = download.get('save_path', str(Path.home() / 'Downloads' / 'dlwithit'))
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
                    if self.current_download_id not in self.cancelled_downloads:
                        self.download_complete.emit(download['id'], filepath)
                elif download['type'] == 'direct-video':
                    # Download video directly (like images but for video)
                    self.status_update.emit(self.current_download_id, 'downloading')
                    referrer = download.get('referrer')
                    title = download.get('title', 'video')
                    save_path = download.get('save_path', str(Path.home() / 'Downloads' / 'dlwithit'))
                    organize_by_platform = download.get('organize_by_platform', True)
                    
                    # Create videos directory if organizing
                    if organize_by_platform:
                        video_dir = Path(save_path) / 'web-videos'
                    else:
                        video_dir = Path(save_path)
                    video_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Generate filename - sanitize title for filesystem safety
                    parsed = urlparse(download['url'])
                    ext = os.path.splitext(parsed.path)[1] or '.mp4'
                    safe_title = re.sub(r'[<>:"/\\|?*]', '-', title).strip().rstrip('.')
                    if not safe_title:
                        safe_title = 'video'
                    filename = f"{safe_title}{ext}"
                    
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
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
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
                        
                        needs_encoding = file_needs_encoding(str(filepath))
                        encode_setting = download.get('encode_vp9', True)
                        
                        
                        # Use referrer (page URL) as source for metadata — more useful than CDN URL
                        source_url = referrer or download['url']

                        if needs_encoding and encode_setting:
                            # Emit encoding_needed signal - EncodingWorker will handle the actual encoding
                            # Build info dict with what we have for direct-video downloads
                            direct_video_info = {
                                'title': title,
                                'webpage_url': source_url,
                            }
                            metadata_info = {
                                'metadata_option': metadata_option,
                                'info': direct_video_info,
                                'source_url': source_url
                            }
                            keep_original = download.get('keep_original', False)
                            self.encoding_needed.emit(self.current_download_id, str(filepath), keep_original, metadata_info)
                            # Don't emit download_complete - EncodingWorker will emit encoding_complete when done
                        else:
                            # Embed metadata if requested
                            direct_video_info = {
                                'title': title,
                                'webpage_url': source_url,
                            }
                            self.embed_video_metadata_if_requested(
                                str(filepath), metadata_option, direct_video_info, source_url)
                            self.download_complete.emit(download['id'], str(filepath))
                else:
                    # Download video with yt-dlp
                    
                    # Skip playlist detection if this video came from a previous playlist selection
                    if not download.get('skip_playlist_detection'):
                        # Check if extension already detected multiple videos
                        detected_videos = download.get('detectedVideos')
                        if detected_videos and len(detected_videos) >= 2:
                            
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
                            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
                        },
                        # Fix for Squarespace HLS: ffmpeg rejects segment URLs without file
                        # extensions (e.g. .../mpegts-h264-1920:1080). -extension_picky 0 disables
                        # the strict extension check on HLS segments.
                        'external_downloader_args': {
                            'ffmpeg_i': ['-allowed_extensions', 'ALL', '-extension_picky', '0']
                        }
                    }

                    # When running as a bundled .app, PATH doesn't include Homebrew so yt-dlp
                    # can't find ffmpeg on its own. Point it explicitly to the bundled binary.
                    ffmpeg_dir = get_ffmpeg_dir()
                    if ffmpeg_dir:
                        ydl_opts['ffmpeg_location'] = ffmpeg_dir
                    
                    # Add referrer headers if available
                    referrer = download.get('referrer')
                    if referrer:
                        ydl_opts['http_headers']['Referer'] = referrer

                    # For metadata: prefer referrer (page URL) over CDN URL
                    metadata_source_url = referrer or download['url']
                    
                    # Use browser cookies for Instagram to avoid rate limiting
                    if 'instagram.com' in download['url']:
                        ydl_opts['cookiesfrombrowser'] = ('firefox',)
                    
                    # Add playlist_items if this is a specific item from a carousel
                    playlist_index = download.get('playlist_index')
                    if playlist_index is not None:
                        ydl_opts['playlist_items'] = str(playlist_index)
                    
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
                        
                        if self.is_vimeo_embed_error(error_str, download['url']):
                            
                            # Extract Vimeo ID and retry with direct URL
                            vimeo_id = self.extract_vimeo_id(download['url'], error_str)
                            if vimeo_id:
                                fallback_url = f"https://vimeo.com/{vimeo_id}"
                                
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
                                    
                                    # Store the original URL before changing it
                                    if '_original_url' not in download:
                                        download['_original_url'] = download['url']
                                    
                                    # Update the download URL to use the direct URL for the actual download
                                    download['url'] = fallback_url
                                    
                                    # Mark that we used a Vimeo fallback - path configuration will happen normally
                                    download['_used_vimeo_fallback'] = True
                                except Exception as fallback_error:
                                    raise extract_error  # Re-raise original error
                            else:
                                raise extract_error  # Re-raise original error
                        else:
                            raise extract_error  # Re-raise original error
                    
                    # Check if yt-dlp's title is useless (generic/HLS sources)
                    ytdlp_title_is_useless = (
                        info.get('extractor', '').lower() == 'generic' and
                        info.get('title', '').lower() in ('playlist', 'master', 'index', 'video', '')
                    )
                    
                    # For Instagram, try multiple ways to get username
                    instagram_username = None
                    # Check if this was originally an Instagram URL (even if it's been changed to a Vimeo fallback)
                    original_url = download.get('_original_url', download['url'])
                    is_instagram = 'instagram.com' in original_url
                    
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
                        # For other platforms, determine folder based on extractor
                        extractor = info.get('extractor', 'Videos')
                        if 'youtube' in extractor.lower():
                            folder = 'YouTube'
                        elif 'vimeo' in extractor.lower():
                            folder = 'Vimeo'
                        elif extractor.lower() == 'generic':
                            folder = 'web-videos'
                        else:
                            folder = extractor

                        if organize_by_platform:
                            extractor_path = str(Path(save_path) / folder)
                        else:
                            extractor_path = save_path

                        # Use our title for HLS/generic URLs where yt-dlp returns useless
                        # names like "playlist" or "master". For known platforms (YouTube, Vimeo),
                        # yt-dlp extracts good titles so we keep %(title)s.
                        our_title = download.get('title')

                        if our_title and ytdlp_title_is_useless:
                            safe_title = re.sub(r'[<>:"/\\|?*]', '-', our_title).strip().rstrip('.')
                            base_filename = safe_title or '%(title).100s'
                        else:
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
                        
                        # Extract thumbnail URL
                        thumbnail_url = info.get('thumbnail') or info.get('thumbnails', [{}])[0].get('url') if info.get('thumbnails') else None
                        if thumbnail_url:
                            # Emit thumbnail URL to update the UI
                            self.status_update.emit(self.current_download_id, f'thumbnail:{thumbnail_url}')
                        
                    
                    # Download the video
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            # First, extract info without downloading to check if it's a playlist
                            info = ydl.extract_info(download['url'], download=False)
                            
                            # Check if this is a playlist with multiple entries (unless skipping detection)
                            if download.get('skip_playlist_detection'):
                                pass
                            elif info.get('_type') == 'playlist' and len(info.get('entries', [])) > 1:
                                
                                # Add 1-based index to each entry for playlist_items support
                                for i, entry in enumerate(info.get('entries', [])):
                                    if entry:  # Some entries might be None for unavailable videos
                                        entry['playlist_index'] = i + 1  # yt-dlp uses 1-based indexing
                                
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
                                        
                                        # Fix malformed URLs with double question marks
                                        if entry_url and '?' in entry_url:
                                            parts = entry_url.split('?')
                                            if len(parts) > 2:
                                                # Keep first ?, replace subsequent ? with &
                                                entry_url = parts[0] + '?' + '&'.join(parts[1:])
                                        
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
                                
                                self.playlist_detected.emit(download['id'], playlist_data)
                                
                                # Don't proceed with this download - let user select videos
                                # Continue to next item in queue
                                continue
                            
                            # Single video or not a playlist - proceed with download
                            info = ydl.extract_info(download['url'], download=True)
                    except Exception as ytdl_error:
                        # Check if this is a Vimeo embed error that we can retry
                        error_str = str(ytdl_error)
                        
                        if self.is_vimeo_embed_error(error_str, download['url']):
                            
                            # Extract Vimeo ID and retry with direct URL
                            vimeo_id = self.extract_vimeo_id(download['url'], error_str)
                            if vimeo_id:
                                fallback_url = f"https://vimeo.com/{vimeo_id}"
                                
                                try:
                                    # Update status to show retry
                                    self.status_update.emit(self.current_download_id, 'Retrying with direct URL...')
                                    
                                    # Create fallback ydl_opts preserving all original settings
                                    import copy
                                    fallback_ydl_opts = ydl_opts.copy()
                                    
                                    # Explicitly copy path-related dictionaries to prevent override
                                    if 'outtmpl' in ydl_opts:
                                        fallback_ydl_opts['outtmpl'] = copy.deepcopy(ydl_opts['outtmpl'])
                                    
                                    if 'paths' in ydl_opts:
                                        fallback_ydl_opts['paths'] = copy.deepcopy(ydl_opts['paths'])
                                    
                                    # Also try to override any extractor-specific templates
                                    with yt_dlp.YoutubeDL(fallback_ydl_opts) as ydl:
                                        info = ydl.extract_info(fallback_url, download=True)
                                    
                                except Exception as fallback_error:
                                    raise ytdl_error  # Re-raise original error
                            else:
                                raise ytdl_error  # Re-raise original error
                        else:
                            raise ytdl_error  # Re-raise original error
                    
                    # Track any files created by yt-dlp for cleanup
                    if info:
                        if info.get('_type') == 'playlist':
                            entries = info.get('entries', [])
                            for entry in entries:
                                if entry:
                                    filename = ydl.prepare_filename(entry)
                                    self.partial_files.add(filename)
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
                                    skip_reason = f"Files already exist ({len(downloaded_files)} files)"
                                    self.download_skipped.emit(self.current_download_id, skip_reason, final_path)
                                    continue

                                # Check encoding and metadata for playlist/carousel files
                                encode_setting = download.get('encode_vp9', True)
                                any_encoding_queued = False


                                for file_path in downloaded_files:
                                    if needs_encoding and encode_setting:
                                        metadata_info = {
                                            'metadata_option': download.get('metadata_option'),
                                            'info': info,
                                            'source_url': metadata_source_url,
                                            'title_override': download.get('title') if ytdlp_title_is_useless else None
                                        }
                                        keep_original = download.get('keep_original', False)
                                        self.encoding_needed.emit(self.current_download_id, file_path, keep_original, metadata_info)
                                        any_encoding_queued = True
                                    else:
                                        # Embed metadata directly (no encoding needed)
                                        self.embed_video_metadata_if_requested(
                                            file_path, download.get('metadata_option'), info, metadata_source_url)

                                if not any_encoding_queued:
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

                            # First check if postprocessor captured the final filepath (after merging)
                            if self.final_filepath and os.path.exists(self.final_filepath):
                                final_path = self.final_filepath
                            else:
                                # Fallback to prepare_filename and check various extensions
                                filename = ydl.prepare_filename(info)

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
                                    if os.path.exists(path):
                                        final_path = path
                                        break

                            if final_path and self.current_download_id not in self.cancelled_downloads:
                                # Remove from partial files once we have final path
                                self.partial_files.discard(final_path)

                                # Check if file was skipped (already exists)
                                if self.ytdlp_logger.skipped:
                                    skip_reason = f"File already exists: {os.path.basename(final_path)}"
                                    self.download_skipped.emit(self.current_download_id, skip_reason, final_path)
                                    continue  # Move to next download in queue

                                # Check if we need to encode
                                # NOTE: If we reach here, skip was NOT detected (continue would have skipped this)
                                
                                encode_setting = download.get('encode_vp9', True)

                                if encode_setting and file_needs_encoding(final_path):
                                    # Emit encoding_needed signal - EncodingWorker will handle the actual encoding
                                    metadata_info = {
                                        'metadata_option': download.get('metadata_option'),
                                        'info': info,
                                        'source_url': metadata_source_url,
                                        'title_override': download.get('title') if ytdlp_title_is_useless else None
                                    }
                                    keep_original = download.get('keep_original', False)
                                    self.encoding_needed.emit(self.current_download_id, final_path, keep_original, metadata_info)
                                    # Don't emit download_complete - EncodingWorker will emit encoding_complete when done
                                else:
                                    # Embed metadata if requested
                                    self.embed_video_metadata_if_requested(final_path, download.get('metadata_option'), info, metadata_source_url)
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
                
                if self.current_download_id in self.cancelled_downloads:
                    # Clean up partial files and emit cancellation signal
                    self.cleanup_partial_files(self.current_download_id)
                    self.download_cancelled.emit(self.current_download_id)
                elif "Download cancelled by user" in str(e):
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