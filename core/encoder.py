"""
Video encoding functionality for Media Downloader App
"""

import os
import json
import subprocess
from pathlib import Path
from queue import Queue
from typing import Optional, Callable, Dict, Any

from PyQt5.QtCore import QThread, pyqtSignal

from .metadata import embed_video_metadata


def needs_encoding_check(video_info_or_path) -> bool:
    """
    Check if a video needs encoding based on codec and container information or file extension.
    
    Args:
        video_info_or_path: Dictionary containing video metadata from yt-dlp, or string file path
        
    Returns:
        bool: True if video needs encoding to H.264, False otherwise
    """
    # Handle string path input (for direct-video downloads)
    if isinstance(video_info_or_path, str):
        filepath = video_info_or_path.lower()
        needs_encoding = filepath.endswith('.webm')
        return needs_encoding
    
    # Handle dictionary input (for yt-dlp downloads)
    video_info = video_info_or_path
    vcodec = str(video_info.get('vcodec', '')).lower()
    acodec = str(video_info.get('acodec', '')).lower()
    ext = str(video_info.get('ext', '')).lower()
    
    
    # Check individual conditions
    conditions = [
        ('vp9 in vcodec', 'vp9' in vcodec),
        ('vp09 in vcodec', 'vp09' in vcodec),
        ('vp8 in vcodec', 'vp8' in vcodec),
        ('vp08 in vcodec', 'vp08' in vcodec),
        ('av01 in vcodec', 'av01' in vcodec),
        ('av1 in vcodec', 'av1' in vcodec),
        ('ext == webm', ext == 'webm')
    ]
    
    needs_encoding = False
    matching_conditions = []
    for condition_name, condition_result in conditions:
        if condition_result:
            matching_conditions.append(condition_name)
            needs_encoding = True
    
    return needs_encoding


class VideoEncoder:
    """
    Handles video encoding operations, particularly encoding to H.264 format.
    """
    
    def __init__(self):
        self.active_process: Optional[subprocess.Popen] = None
        self._cancelled = False
    
    def cancel_encoding(self):
        """Cancel the current encoding operation"""
        self._cancelled = True
        if self.active_process:
            try:
                self.active_process.terminate()
            except:
                pass
    
    def encode_to_h264(
        self, 
        input_path: str, 
        keep_original: bool = False,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Optional[str]:
        """
        Encode video to H.264 format.
        
        Args:
            input_path: Path to the input video file
            keep_original: Whether to keep the original file after encoding
            progress_callback: Optional callback function that receives (percent, status) updates
            
        Returns:
            str: Path to encoded file if successful, None if failed or cancelled
        """
        try:
            output_path = input_path.rsplit('.', 1)[0] + '_h264.mp4'
            self._cancelled = False
            
            # Get video duration first for progress calculation
            duration = self._get_video_duration(input_path)
            
            # FFmpeg command for encoding
            cmd = [
                'ffmpeg', '-i', input_path,
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                '-c:a', 'aac', '-b:a', '128k',
                '-progress', 'pipe:1',
                '-nostats',
                '-y',  # Overwrite output
                output_path
            ]
            
            # Start encoding process
            self.active_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True
            )
            
            # Parse ffmpeg progress output
            for line in self.active_process.stdout:
                if self._cancelled:
                    self.active_process.terminate()
                    self.active_process.wait()
                    # Clean up partial file
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    return None
                
                # Parse progress information
                if line.startswith('out_time_us='):
                    try:
                        out_us = int(line.split('=')[1])
                        out_seconds = out_us / 1000000
                        
                        if duration and duration > 0 and progress_callback:
                            percent = min(int((out_seconds / duration) * 100), 100)
                            progress_callback(percent, f"Encoding... {percent}%")
                    except:
                        pass
            
            # Wait for process to complete
            self.active_process.wait()
            
            if self.active_process.returncode == 0:
                # Encoding successful
                if not keep_original:
                    os.remove(input_path)
                return output_path
            else:
                # Encoding failed
                return None
                
        except Exception as e:
            print(f"Encoding error: {e}")
            return None
        finally:
            self.active_process = None
    
    def _get_video_duration(self, video_path: str) -> Optional[float]:
        """
        Get video duration using ffprobe.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            float: Duration in seconds, or None if unable to determine
        """
        try:
            probe_cmd = [
                'ffprobe', '-v', 'error', 
                '-show_entries', 'format=duration', 
                '-of', 'json', 
                video_path
            ]
            
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
            
            if probe_result.returncode == 0:
                probe_data = json.loads(probe_result.stdout)
                return float(probe_data['format']['duration'])
        except:
            pass
        
        return None


# Convenience function for simple encoding operations
def encode_video_to_h264(
    input_path: str,
    keep_original: bool = False,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> Optional[str]:
    """
    Convenience function to encode a video to H.264.

    Args:
        input_path: Path to input video file
        keep_original: Whether to keep the original file
        progress_callback: Optional progress callback function

    Returns:
        str: Path to encoded file if successful, None otherwise
    """
    encoder = VideoEncoder()
    return encoder.encode_to_h264(input_path, keep_original, progress_callback)


class EncodingWorker(QThread):
    """
    Worker thread for encoding videos in parallel with downloads.
    Processes encoding jobs from a queue while downloads continue.
    """
    # Signals for UI updates
    encoding_started = pyqtSignal(str)  # download_id
    encoding_progress = pyqtSignal(str, int, str)  # download_id, percent, status
    encoding_complete = pyqtSignal(str, str)  # download_id, final_path
    encoding_error = pyqtSignal(str, str)  # download_id, error_message
    encoding_cancelled = pyqtSignal(str)  # download_id

    def __init__(self):
        super().__init__()
        self.encoding_queue = Queue()
        self.encoder = VideoEncoder()
        self.cancelled_jobs = set()
        self.current_job_id = None

    def add_job(self, download_id: str, input_path: str, keep_original: bool = False,
                metadata_info: Optional[Dict[str, Any]] = None):
        """
        Add an encoding job to the queue.

        Args:
            download_id: ID of the download this encoding is for
            input_path: Path to the video file to encode
            keep_original: Whether to keep the original file after encoding
            metadata_info: Optional dict with metadata_option, info (yt-dlp), and source_url
        """
        job = {
            'download_id': download_id,
            'input_path': input_path,
            'keep_original': keep_original,
            'metadata_info': metadata_info or {}
        }
        self.encoding_queue.put(job)

    def cancel_job(self, download_id: str):
        """Cancel an encoding job (either queued or in progress)"""
        self.cancelled_jobs.add(download_id)
        if self.current_job_id == download_id:
            self.encoder.cancel_encoding()

    def run(self):
        """Main encoding loop - processes jobs from the queue"""
        while True:
            job = self.encoding_queue.get()
            if job is None:
                break  # Shutdown signal

            download_id = job['download_id']
            input_path = job['input_path']
            keep_original = job['keep_original']
            metadata_info = job.get('metadata_info', {})


            # Check if cancelled before starting
            if download_id in self.cancelled_jobs:
                self.cancelled_jobs.discard(download_id)
                self.encoding_cancelled.emit(download_id)
                continue

            self.current_job_id = download_id
            self.encoding_started.emit(download_id)

            # Progress callback for this job
            def progress_callback(percent, status):
                if download_id not in self.cancelled_jobs:
                    self.encoding_progress.emit(download_id, percent, status)

            # Perform encoding
            try:
                encoded_path = self.encoder.encode_to_h264(
                    input_path, keep_original, progress_callback
                )

                if download_id in self.cancelled_jobs:
                    self.cancelled_jobs.discard(download_id)
                    # If cancelled, use original file if it exists
                    if os.path.exists(input_path):
                        self.encoding_complete.emit(download_id, input_path)
                    else:
                        self.encoding_cancelled.emit(download_id)
                elif encoded_path:
                    # Embed metadata if requested
                    self._embed_metadata_if_requested(encoded_path, metadata_info)
                    self.encoding_complete.emit(download_id, encoded_path)
                else:
                    # Encoding failed - use original file as fallback
                    if os.path.exists(input_path):
                        self._embed_metadata_if_requested(input_path, metadata_info)
                        self.encoding_complete.emit(download_id, input_path)
                    else:
                        self.encoding_error.emit(download_id, "Encoding failed and original file not found")

            except Exception as e:
                # On error, try to use original file
                if os.path.exists(input_path):
                    self.encoding_complete.emit(download_id, input_path)
                else:
                    self.encoding_error.emit(download_id, str(e))

            self.current_job_id = None

    def _embed_metadata_if_requested(self, filepath: str, metadata_info: Dict[str, Any]):
        """
        Embed metadata into video file if embedded metadata is requested.

        Args:
            filepath: Path to the video file
            metadata_info: Dict with metadata_option, info (yt-dlp), and source_url
        """
        metadata_option = metadata_info.get('metadata_option')
        if metadata_option != 'embedded':
            return

        info = metadata_info.get('info')
        source_url = metadata_info.get('source_url', '')

        if not info:
            return

        # Extract metadata from yt-dlp info
        title = info.get('title', 'Downloaded Video')
        description = info.get('description', '')
        uploader = info.get('uploader') or info.get('channel') or info.get('uploader_id')
        # Prefer our source_url (page URL from referrer) over yt-dlp's webpage_url
        # (which for generic/HLS downloads is the CDN URL, not the artist's page)
        webpage_url = source_url or info.get('webpage_url', '')

        # Use title override if provided (for HLS/generic where yt-dlp title is useless)
        title_override = metadata_info.get('title_override')
        if title_override:
            title = title_override

        # Truncate description if too long
        if description and len(description) > 500:
            description = description[:497] + "..."


        try:
            embed_success = embed_video_metadata(
                filepath=filepath,
                source_url=webpage_url,
                title=title,
                description=description,
                uploader=uploader
            )

        except Exception:
            pass

    def stop(self):
        """Stop the encoding worker"""
        self.encoder.cancel_encoding()
        self.encoding_queue.put(None)  # Shutdown signal

    def queue_size(self):
        """Return the number of jobs in the queue"""
        return self.encoding_queue.qsize()