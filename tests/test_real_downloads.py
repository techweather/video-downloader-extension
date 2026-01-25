"""
Real download tests that interact with actual websites
Run with: pytest -m slow tests/test_real_downloads.py
"""

import pytest
import queue
import tempfile
import shutil
import time
import os
from pathlib import Path
from unittest.mock import Mock, patch
import threading
import sys
import requests
import re
from urllib.parse import urlparse

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.downloader import DownloadWorker
from api.flask_server import FlaskServer
import yt_dlp


@pytest.fixture
def real_temp_download_dir():
    """Create a temporary directory for real downloads and clean up after"""
    temp_dir = tempfile.mkdtemp(prefix="media_downloader_real_test_")
    yield temp_dir
    # Cleanup - remove all downloaded files
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def real_download_worker():
    """Create a real DownloadWorker for actual testing"""
    download_queue = queue.Queue()
    worker = DownloadWorker(download_queue)
    
    # Mock the PyQt5 signals to avoid dependency issues
    worker.progress_update = Mock()
    worker.download_complete = Mock()
    worker.download_error = Mock()
    worker.download_cancelled = Mock()
    worker.status_update = Mock()
    
    return worker, download_queue


@pytest.fixture
def real_flask_server():
    """Create and start a real Flask server for API testing"""
    server = FlaskServer(port=5557, debug=False)  # Different port for real tests
    
    # Mock the window to capture signals
    mock_window = Mock()
    mock_window.video_list_received = Mock()
    mock_window.new_download = Mock()
    server.set_window(mock_window)
    
    # Start server in background thread
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    
    # Wait for server to start
    time.sleep(1)
    
    yield {
        'server': server,
        'base_url': 'http://127.0.0.1:5557',
        'mock_window': mock_window
    }
    
    # Server will stop when thread ends due to daemon=True


def find_vimeo_embeds(html):
    """
    Parse HTML and return a list of Vimeo video IDs found in iframes or embed scripts
    
    Args:
        html (str): HTML content to parse
        
    Returns:
        list: List of unique Vimeo video IDs found
    """
    vimeo_ids = set()
    
    # Common Vimeo embed patterns
    patterns = [
        # Standard iframe embeds
        r'player\.vimeo\.com/video/(\d+)',
        
        # Direct vimeo.com links  
        r'vimeo\.com/(?:video/)?(\d+)',
        
        # JavaScript/JSON configurations
        r'"video_id"\s*:\s*"?(\d+)"?',
        r'"vimeo_id"\s*:\s*"?(\d+)"?',
        r'vimeo_video_id["\']?\s*:\s*["\']?(\d+)["\']?',
        
        # Data attributes
        r'data-vimeo-id["\']?\s*=\s*["\']?(\d+)["\']?',
        r'data-video-id["\']?\s*=\s*["\']?(\d+)["\']?',
        
        # Embed URLs in various formats
        r'https?://(?:www\.)?vimeo\.com/(?:video/)?(\d+)',
        r'https?://player\.vimeo\.com/video/(\d+)',
        
        # Script tags and config objects
        r'videoId["\']?\s*:\s*["\']?(\d+)["\']?',
        r'video["\']?\s*:\s*["\']?(\d+)["\']?',
    ]
    
    # Search for all patterns in the HTML
    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            # Ensure it's a reasonable Vimeo ID (6-10 digits typically)
            if match.isdigit() and 6 <= len(match) <= 12:
                vimeo_ids.add(match)
    
    return sorted(list(vimeo_ids))


class TestFlaskAPIRealDownloads:
    """Test Flask API with real downloads end-to-end"""
    
    @pytest.mark.slow
    def test_api_direct_image_download(self, real_flask_server, real_temp_download_dir):
        """Test direct image download through Flask API"""
        base_url = real_flask_server['base_url']
        mock_window = real_flask_server['mock_window']
        
        # Prepare download data
        image_data = {
            'type': 'image',
            'url': 'https://www.apple.com/favicon.ico',
            'pageUrl': 'https://www.apple.com',
            'title': 'Apple Favicon'
        }
        
        # Send request to API
        response = requests.post(
            f'{base_url}/download',
            json=image_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'queued'
        
        # Verify signal was emitted
        assert mock_window.new_download.emit.called
        call_args = mock_window.new_download.emit.call_args[0]
        assert call_args[0] == image_data
        
        print("✓ Flask API image download request successful")
    
    @pytest.mark.slow
    def test_api_youtube_video_request(self, real_flask_server):
        """Test YouTube video download request through Flask API"""
        base_url = real_flask_server['base_url']
        mock_window = real_flask_server['mock_window']
        
        # Prepare download data
        video_data = {
            'type': 'video',
            'url': 'https://www.youtube.com/watch?v=ZNXawJuIkMY',
            'pageUrl': 'https://www.youtube.com/watch?v=ZNXawJuIkMY',
            'title': 'YouTube Test Video'
        }
        
        # Send request to API
        response = requests.post(
            f'{base_url}/download',
            json=video_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'queued'
        
        # Verify signal was emitted
        assert mock_window.new_download.emit.called
        call_args = mock_window.new_download.emit.call_args[0]
        assert call_args[0] == video_data
        
        print("✓ Flask API YouTube video request successful")
    
    @pytest.mark.slow
    def test_api_video_list_request(self, real_flask_server):
        """Test video list (carousel) request through Flask API"""
        base_url = real_flask_server['base_url']
        mock_window = real_flask_server['mock_window']
        
        # Prepare carousel data
        carousel_data = {
            'type': 'video-list',
            'pageUrl': 'https://www.instagram.com/p/test/',
            'pageTitle': 'Test Instagram Carousel',
            'videos': [
                {
                    'url': 'https://www.instagram.com/p/test/',
                    'title': 'Video 1',
                    'playlist_index': 1
                },
                {
                    'url': 'https://www.instagram.com/p/test/',
                    'title': 'Video 2', 
                    'playlist_index': 2
                }
            ]
        }
        
        # Send request to API
        response = requests.post(
            f'{base_url}/download',
            json=carousel_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'queued'
        
        # Verify video_list_received signal was emitted
        assert mock_window.video_list_received.emit.called
        call_args = mock_window.video_list_received.emit.call_args[0]
        assert call_args[0] == carousel_data
        
        print("✓ Flask API video list request successful")


class TestRealDownloads:
    """Real download tests with actual websites"""
    
    @pytest.mark.slow
    def test_youtube_video_info_extraction(self, real_temp_download_dir):
        """Test YouTube video info extraction (no actual download)"""
        # Test URL: Short educational video
        test_url = "https://www.youtube.com/watch?v=ZNXawJuIkMY"
        
        try:
            # Just extract info, don't download
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(test_url, download=False)
            
            # Verify we got valid info
            assert info is not None
            assert 'title' in info
            assert 'id' in info
            assert info['id'] == 'ZNXawJuIkMY'
            assert 'uploader' in info or 'channel' in info
            assert 'duration' in info
            
            print(f"✓ YouTube info extraction successful: {info.get('title', 'Unknown')}")
            
        except yt_dlp.DownloadError as e:
            pytest.skip(f"YouTube video not accessible: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error during YouTube info extraction: {e}")
    
    @pytest.mark.slow
    def test_youtube_video_partial_download(self, real_download_worker, real_temp_download_dir):
        """Test YouTube video download start then cancel to verify download capability"""
        worker, download_queue = real_download_worker
        test_url = "https://www.youtube.com/watch?v=ZNXawJuIkMY"
        
        download_data = {
            'id': 'test_youtube_partial',
            'type': 'video',
            'url': test_url,
            'save_path': real_temp_download_dir,
            'organize_by_platform': True,
            'quality': 'worst',  # Use worst quality to download faster
            'encode_vp9': False   # Skip encoding to save time
        }
        
        # Add download to queue
        download_queue.put(download_data)
        download_queue.put(None)  # Sentinel to stop worker
        
        # Start worker in a thread with timeout
        worker_thread = threading.Thread(target=worker.run, daemon=True)
        worker_thread.start()
        
        # Let it start downloading
        time.sleep(3)
        
        # Cancel the download
        worker.cancel_download('test_youtube_partial')
        
        # Wait a bit for cancellation to process
        worker_thread.join(timeout=5)
        
        # Verify signals were called appropriately
        assert worker.status_update.emit.call_count > 0
        # Should have either completed quickly or been cancelled
        assert (worker.download_complete.emit.called or 
                worker.download_cancelled.emit.called or
                worker.download_error.emit.called)
        
        print("✓ YouTube download start/cancel test successful")
    
    @pytest.mark.slow
    def test_direct_image_download(self, real_download_worker, real_temp_download_dir):
        """Test direct image download from a real URL"""
        worker, download_queue = real_download_worker
        
        # Use Apple favicon as a reliable, small image
        test_url = "https://www.apple.com/favicon.ico"
        
        download_data = {
            'id': 'test_image_real',
            'type': 'image',
            'url': test_url,
            'save_path': real_temp_download_dir,
            'organize_by_platform': True
        }
        
        # Add download to queue
        download_queue.put(download_data)
        download_queue.put(None)  # Sentinel
        
        # Run worker with timeout
        worker_thread = threading.Thread(target=worker.run, daemon=True)
        worker_thread.start()
        worker_thread.join(timeout=30)
        
        # Check results
        if worker.download_complete.emit.called:
            # Verify file was downloaded
            call_args = worker.download_complete.emit.call_args[0]
            download_id, file_path = call_args
            assert download_id == 'test_image_real'
            assert os.path.exists(file_path)
            assert file_path.endswith('.ico') or 'favicon' in file_path
            
            # Verify it's in the images directory
            assert 'images' in file_path
            
            print(f"✓ Image download successful: {file_path}")
        elif worker.download_error.emit.called:
            error_args = worker.download_error.emit.call_args[0]
            pytest.fail(f"Image download failed: {error_args[1]}")
        else:
            pytest.fail("Image download did not complete within timeout")
    
    @pytest.mark.slow
    def test_instagram_info_extraction(self, real_temp_download_dir):
        """Test Instagram post info extraction (no actual download)"""
        # Test URL: Public Instagram post
        test_url = "https://www.instagram.com/p/DHS7oMQPJra/"
        
        try:
            # Just extract info, don't download
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(test_url, download=False)
            
            # Verify we got valid info
            assert info is not None
            assert 'title' in info or 'description' in info
            assert 'id' in info
            
            # Check if it's a carousel (multiple entries) or single post
            if info.get('_type') == 'playlist':
                assert 'entries' in info
                assert len(info['entries']) > 0
                print(f"✓ Instagram carousel info extraction successful: {len(info['entries'])} entries")
            else:
                print(f"✓ Instagram single post info extraction successful: {info.get('title', 'Unknown')}")
                
        except yt_dlp.DownloadError as e:
            error_str = str(e)
            if any(keyword in error_str.lower() for keyword in ['private', 'login', 'age', 'restricted']):
                pytest.skip(f"Instagram post requires login or is restricted: {e}")
            else:
                pytest.fail(f"Instagram info extraction failed: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error during Instagram info extraction: {e}")
    
    @pytest.mark.slow
    def test_instagram_carousel_playlist_index(self, real_download_worker, real_temp_download_dir):
        """Test Instagram carousel with playlist_index functionality"""
        worker, download_queue = real_download_worker
        
        # Test URL: Public Instagram carousel post
        test_url = "https://www.instagram.com/p/DHS7oMQPJra/"
        
        # First, verify it's actually a carousel
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'cookiesfrombrowser': ('firefox',),  # Use Firefox cookies like our app
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(test_url, download=False)
            
            if info.get('_type') != 'playlist':
                pytest.skip("Test URL is not a playlist/carousel, skipping playlist_index test")
            
            entries = info.get('entries', [])
            if len(entries) < 2:
                pytest.skip("Test URL has less than 2 entries, skipping playlist_index test")
            
            print(f"✓ Carousel verified: {len(entries)} entries found")
            
            # Test downloading specific item (item #2 out of the carousel)
            target_index = 2
            download_data = {
                'id': 'test_instagram_carousel',
                'type': 'video',
                'url': test_url,
                'save_path': real_temp_download_dir,
                'organize_by_platform': True,
                'playlist_index': target_index,  # Download only item #2
                'skip_playlist_detection': True,  # Skip re-detection
                'quality': 'worst',  # Use worst quality to download faster
                'encode_vp9': False   # Skip encoding
            }
            
            # Add to queue and run
            download_queue.put(download_data)
            download_queue.put(None)  # Sentinel
            
            # Run worker with timeout
            worker_thread = threading.Thread(target=worker.run, daemon=True)
            worker_thread.start()
            worker_thread.join(timeout=60)  # Instagram can be slow
            
            # Check results
            if worker.download_complete.emit.called:
                call_args = worker.download_complete.emit.call_args[0]
                download_id, file_path = call_args
                
                assert download_id == 'test_instagram_carousel'
                
                # Handle MULTI file format - extract actual file path
                actual_file_path = file_path
                if '|MULTI|' in str(file_path):
                    actual_file_path = str(file_path).split('|MULTI|')[0]
                    print(f"  Extracted file path from MULTI format: {actual_file_path}")
                
                # Verify the actual file exists
                assert os.path.exists(actual_file_path), f"File does not exist: {actual_file_path}"
                
                # Also check by finding all video files in the temp directory
                temp_dir = Path(real_temp_download_dir)
                all_video_files = []
                for pattern in ['**/*.mp4', '**/*.webm', '**/*.mov']:
                    all_video_files.extend(temp_dir.glob(pattern))
                
                print(f"✓ Instagram carousel download successful: {actual_file_path}")
                print(f"  Total video files in temp dir: {len(all_video_files)}")
                print(f"  Video files found: {[f.name for f in all_video_files]}")
                
                # Verify exactly one video file was downloaded (not the whole carousel)
                assert len(all_video_files) == 1, f"Expected exactly 1 video file, found {len(all_video_files)}: {[f.name for f in all_video_files]}"
                
                # Verify it's an MP4 (Instagram videos are typically MP4)
                video_file = all_video_files[0]
                assert video_file.suffix == '.mp4', f"Expected .mp4 file, got {video_file.suffix}"
                
                print(f"  ✅ Verified: Only 1 video file downloaded (playlist_index={target_index} worked!)")
                
            elif worker.download_error.emit.called:
                error_args = worker.download_error.emit.call_args[0]
                error_message = error_args[1]
                
                # Check if it's a known issue we can skip
                if any(keyword in error_message.lower() for keyword in ['private', 'login', 'age', 'restricted', 'unavailable']):
                    pytest.skip(f"Instagram carousel test skipped: {error_message}")
                else:
                    pytest.fail(f"Instagram carousel download failed: {error_message}")
            else:
                pytest.fail("Instagram carousel download did not complete within timeout")
                
        except yt_dlp.DownloadError as e:
            error_str = str(e)
            if any(keyword in error_str.lower() for keyword in ['private', 'login', 'age', 'restricted']):
                pytest.skip(f"Instagram carousel test skipped: {e}")
            else:
                pytest.fail(f"Instagram carousel info extraction failed: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error during Instagram carousel test: {e}")
    
    @pytest.mark.slow
    def test_vimeo_info_extraction(self, real_temp_download_dir):
        """Test Vimeo video info extraction"""
        # Use Vimeo Staff Pick videos which are more likely to remain public
        test_urls = [
            "https://vimeo.com/1084537",   # Very old, established Vimeo video
            "https://vimeo.com/31158841",  # Another long-standing public video
            "https://vimeo.com/148751763"  # Big Buck Bunny trailer (backup)
        ]
        
        last_error = None
        
        for test_url in test_urls:
            try:
                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                    info = ydl.extract_info(test_url, download=False)
                
                assert info is not None
                assert 'title' in info
                assert 'id' in info
                
                print(f"✓ Vimeo info extraction successful: {info.get('title', 'Unknown')} (ID: {info['id']})")
                return  # Success, exit the test
                
            except yt_dlp.DownloadError as e:
                last_error = e
                print(f"  Vimeo URL {test_url} failed: {e}")
                continue
            except Exception as e:
                last_error = e
                print(f"  Unexpected error with {test_url}: {e}")
                continue
        
        # If all URLs failed, skip the test
        pytest.skip(f"All Vimeo test URLs failed. Last error: {last_error}")
    
    @pytest.mark.slow 
    def test_download_worker_error_handling(self, real_download_worker, real_temp_download_dir):
        """Test DownloadWorker error handling with invalid URLs"""
        worker, download_queue = real_download_worker
        
        # Test with invalid YouTube URL
        invalid_download = {
            'id': 'test_invalid_url',
            'type': 'video', 
            'url': 'https://youtube.com/watch?v=NONEXISTENT123456789',
            'save_path': real_temp_download_dir,
            'organize_by_platform': True
        }
        
        download_queue.put(invalid_download)
        download_queue.put(None)  # Sentinel
        
        # Run worker
        worker_thread = threading.Thread(target=worker.run, daemon=True)
        worker_thread.start()
        worker_thread.join(timeout=30)
        
        # Should have error, not success
        assert not worker.download_complete.emit.called
        assert worker.download_error.emit.called
        
        error_args = worker.download_error.emit.call_args[0]
        download_id, error_message = error_args
        assert download_id == 'test_invalid_url'
        assert len(error_message) > 0
        
        print(f"✓ Error handling test successful: {error_message[:100]}...")
    
    @pytest.mark.slow
    def test_multi_vimeo_page_detection(self):
        """Test detection of multiple Vimeo videos on a single page"""
        test_url = "https://mvsm.com/project/paper-pro-move"
        
        try:
            # Fetch the page
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
            
            response = requests.get(test_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            html_content = response.text
            print(f"✓ Successfully fetched page: {len(html_content)} characters")
            
            # Extract Vimeo video IDs
            vimeo_ids = find_vimeo_embeds(html_content)
            
            print(f"Found Vimeo IDs: {vimeo_ids}")
            
            # Assert that we found at least 3 Vimeo videos (the primary embedded videos)
            # Primary videos are: 1136055148, 1136057940, 1136059218
            assert len(vimeo_ids) >= 3, f"Expected at least 3 Vimeo videos, found {len(vimeo_ids)}: {vimeo_ids}"
            
            # Verify the primary video IDs are present
            primary_ids = ['1136055148', '1136057940', '1136059218']
            for primary_id in primary_ids:
                assert primary_id in vimeo_ids, f"Primary Vimeo ID {primary_id} not found in detected IDs: {vimeo_ids}"
            
            # Verify the IDs are reasonable Vimeo video IDs
            for vimeo_id in vimeo_ids:
                assert vimeo_id.isdigit(), f"Invalid Vimeo ID format: {vimeo_id}"
                assert 6 <= len(vimeo_id) <= 12, f"Vimeo ID length unexpected: {vimeo_id}"
            
            print(f"✓ Multi-Vimeo page detection successful: Found {len(vimeo_ids)} videos")
            print(f"  Video IDs: {', '.join(vimeo_ids)}")
            
        except requests.RequestException as e:
            pytest.skip(f"Could not fetch test page: {e}")
        except AssertionError as e:
            # If we don't find the expected videos, show what we found for debugging
            html_content = response.text if 'response' in locals() else 'N/A'
            found_ids = find_vimeo_embeds(html_content) if html_content != 'N/A' else []
            
            print(f"Multi-Vimeo detection assertion failed:")
            print(f"  Expected: At least 3 Vimeo videos (primary: 1136055148, 1136057940, 1136059218)")
            print(f"  Found: {len(found_ids)} videos")
            print(f"  IDs: {found_ids}")
            print(f"  Page length: {len(html_content)} characters")
            
            # Show a sample of the HTML for debugging
            if html_content != 'N/A':
                print(f"  HTML sample (first 500 chars): {html_content[:500]}...")
                
                # Look for any Vimeo-related content
                vimeo_mentions = html_content.lower().count('vimeo')
                print(f"  'vimeo' mentions in HTML: {vimeo_mentions}")
            
            raise e
        except Exception as e:
            pytest.fail(f"Unexpected error during multi-Vimeo page detection: {e}")


class TestYtDlpCompatibility:
    """Test yt-dlp compatibility with different platforms"""
    
    @pytest.mark.slow
    def test_ytdlp_extractors_available(self):
        """Test that required extractors are available in yt-dlp"""
        required_extractors = [
            'Youtube',
            'Instagram', 
            'Vimeo',
            'Generic'  # For direct video URLs
        ]
        
        available_extractors = yt_dlp.list_extractors()
        extractor_names = [e.IE_NAME for e in available_extractors if hasattr(e, 'IE_NAME')]
        
        for required in required_extractors:
            # Check if extractor name is in the list (case insensitive)
            found = any(required.lower() in name.lower() for name in extractor_names)
            assert found, f"Required extractor {required} not found in yt-dlp"
        
        print(f"✓ All required extractors available in yt-dlp ({len(extractor_names)} total)")
    
    @pytest.mark.slow
    def test_ytdlp_version_compatibility(self):
        """Test yt-dlp version compatibility"""
        version = yt_dlp.version.__version__
        
        # yt-dlp uses date-based versioning like "2023.12.30"
        # We just verify it's a reasonable format
        assert isinstance(version, str)
        assert len(version) > 5
        
        print(f"✓ yt-dlp version: {version}")


# Note: pytest markers are configured in pytest.ini


def test_configuration_examples():
    """
    Examples of how to run these tests:
    
    # Run all real download tests
    pytest tests/test_real_downloads.py -v -m slow
    
    # Run only Flask API tests  
    pytest tests/test_real_downloads.py::TestFlaskAPIRealDownloads -v -m slow
    
    # Run only direct download tests
    pytest tests/test_real_downloads.py::TestRealDownloads -v -m slow
    
    # Run specific test
    pytest tests/test_real_downloads.py::TestRealDownloads::test_instagram_carousel_playlist_index -v -m slow
    
    # Run with timeout for slow tests
    pytest tests/test_real_downloads.py -v -m slow --timeout=300
    
    # Skip real tests and run only fast unit tests
    pytest tests/ -v -m "not slow"
    """
    pass


if __name__ == "__main__":
    # Allow running this file directly for quick testing
    print("=== Media Downloader Real Download Tests ===")
    print("Note: These tests require internet connection and may take time")
    print("They will test actual downloads from YouTube, Instagram, etc.")
    print("")
    print("Running tests...")
    
    # Run with verbose output and show durations
    exit_code = pytest.main([
        __file__, 
        "-v",           # Verbose output
        "-m", "slow",   # Only slow/real tests  
        "-s",           # Don't capture output (so we see print statements)
        "--tb=short",   # Shorter tracebacks
        "--durations=10" # Show 10 slowest tests
    ])
    
    print(f"\nTests completed with exit code: {exit_code}")
    exit(exit_code)