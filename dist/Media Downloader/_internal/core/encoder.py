"""
Video encoding functionality for Media Downloader App
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Callable, Dict, Any


def get_bundled_ffmpeg_tools():
    """
    Get paths to bundled ffmpeg and ffprobe binaries when running from PyInstaller bundle.
    
    Returns:
        tuple: (ffmpeg_path, ffprobe_path) - both str or None if not found
    """
    try:
        if getattr(sys, 'frozen', False):
            # Running from PyInstaller bundle
            bundle_dir = Path(sys._MEIPASS)
            ffmpeg_path = bundle_dir / 'ffmpeg'
            # Note: We assume ffprobe would be bundled as well if needed
            # For now, we'll try to use system ffprobe or fallback gracefully
            ffprobe_path = bundle_dir / 'ffprobe' if (bundle_dir / 'ffprobe').exists() else None
            
            if ffmpeg_path.exists() and ffmpeg_path.is_file():
                print(f"[DEBUG] Found bundled ffmpeg at: {ffmpeg_path}")
                if ffprobe_path and ffprobe_path.exists():
                    print(f"[DEBUG] Found bundled ffprobe at: {ffprobe_path}")
                else:
                    # Try system ffprobe
                    ffprobe_path = shutil.which('ffprobe')
                    if ffprobe_path:
                        print(f"[DEBUG] Using system ffprobe at: {ffprobe_path}")
                    else:
                        print("[DEBUG] ffprobe not found - duration calculation may fail")
                
                return str(ffmpeg_path), ffprobe_path
            else:
                print(f"[DEBUG] Bundled ffmpeg not found at: {ffmpeg_path}")
        else:
            # Running from source - try system tools
            ffmpeg_path = shutil.which('ffmpeg')
            ffprobe_path = shutil.which('ffprobe')
            
            if ffmpeg_path:
                print(f"[DEBUG] Using system ffmpeg at: {ffmpeg_path}")
            if ffprobe_path:
                print(f"[DEBUG] Using system ffprobe at: {ffprobe_path}")
                
            return ffmpeg_path, ffprobe_path
            
    except Exception as e:
        print(f"[DEBUG] Error finding ffmpeg tools: {e}")
    
    print("[DEBUG] No ffmpeg tools found - encoding will fail")
    return None, None


def needs_encoding_check(video_info: Dict[str, Any]) -> bool:
    """
    Check if a video needs encoding based on codec and container information.
    
    Args:
        video_info: Dictionary containing video metadata from yt-dlp
        
    Returns:
        bool: True if video needs encoding to H.264, False otherwise
    """
    # Handle null or empty video_info
    if not video_info:
        print("[ENCODING DEBUG] Warning: video_info is None or empty - assuming no encoding needed")
        return False
    
    # Safely extract codec and format information with defaults
    vcodec = str(video_info.get('vcodec', '')).lower()
    acodec = str(video_info.get('acodec', '')).lower() 
    ext = str(video_info.get('ext', '')).lower()
    
    # Debug logging for codec detection
    print(f"[ENCODING DEBUG] Video codec: '{vcodec}', Audio codec: '{acodec}', Extension: '{ext}'")
    
    # Handle missing codec information
    if vcodec == 'none' or not vcodec:
        print("[ENCODING DEBUG] Warning: No video codec information available - assuming no encoding needed")
        return False
    
    # Check if needs encoding (VP9, VP8, AV1, or WebM container)
    needs_encoding = any([
        'vp9' in vcodec,
        'vp09' in vcodec,
        'vp8' in vcodec,
        'vp08' in vcodec,
        'av01' in vcodec,
        'av1' in vcodec,
        ext == 'webm'
    ])
    
    print(f"[ENCODING DEBUG] Needs encoding: {needs_encoding}")
    return needs_encoding


class VideoEncoder:
    """
    Handles video encoding operations, particularly encoding to H.264 format.
    """
    
    def __init__(self):
        self.active_process: Optional[subprocess.Popen] = None
        self._cancelled = False
        
        # Get ffmpeg tools paths
        self.ffmpeg_path, self.ffprobe_path = get_bundled_ffmpeg_tools()
        
        if not self.ffmpeg_path:
            raise RuntimeError("ffmpeg not found - video encoding is not available")
    
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
                self.ffmpeg_path, '-i', input_path,
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
                    # Remove original file if requested
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
        if not self.ffprobe_path:
            print("[DEBUG] ffprobe not available - cannot calculate video duration")
            return None
            
        try:
            probe_cmd = [
                self.ffprobe_path, '-v', 'error', 
                '-show_entries', 'format=duration', 
                '-of', 'json', 
                video_path
            ]
            
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
            
            if probe_result.returncode == 0:
                probe_data = json.loads(probe_result.stdout)
                return float(probe_data['format']['duration'])
        except Exception as e:
            print(f"[DEBUG] Error getting video duration: {e}")
        
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