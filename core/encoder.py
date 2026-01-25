"""
Video encoding functionality for Media Downloader App
"""

import os
import json
import subprocess
from typing import Optional, Callable, Dict, Any


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
        print(f"[DEBUG] Encoding check (file path): {video_info_or_path}")
        print(f"[DEBUG] File extension check: .webm = {needs_encoding}")
        return needs_encoding
    
    # Handle dictionary input (for yt-dlp downloads)
    video_info = video_info_or_path
    vcodec = str(video_info.get('vcodec', '')).lower()
    acodec = str(video_info.get('acodec', '')).lower()
    ext = str(video_info.get('ext', '')).lower()
    
    print(f"[DEBUG] Encoding check (video info): vcodec='{vcodec}', acodec='{acodec}', ext='{ext}'")
    
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
    
    print(f"[DEBUG] Encoding needed: {needs_encoding}")
    if matching_conditions:
        print(f"[DEBUG] Matching conditions: {', '.join(matching_conditions)}")
    else:
        print(f"[DEBUG] No encoding conditions matched")
    
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
                print(f"[DEBUG] Encoding completed successfully: {output_path}")
                if not keep_original:
                    print(f"[DEBUG] Removing original file (keep_original=False): {input_path}")
                    os.remove(input_path)
                else:
                    print(f"[DEBUG] Keeping original file (keep_original=True): {input_path}")
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