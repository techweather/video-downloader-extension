"""
pytest configuration and fixtures for Media Downloader tests
"""

import pytest
import threading
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.flask_server import FlaskServer


@pytest.fixture(scope="session")
def temp_download_dir():
    """Create a temporary directory for test downloads"""
    temp_dir = tempfile.mkdtemp(prefix="media_downloader_test_")
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def flask_app():
    """Create a Flask app instance for testing"""
    server = FlaskServer(port=5556, debug=False)  # Use different port for tests
    return server.app


@pytest.fixture(scope="session")
def running_flask_server():
    """Start a Flask server in a background thread for testing"""
    server = FlaskServer(port=5556, debug=False)
    
    # Mock the window to avoid PyQt5 dependencies in tests
    mock_window = Mock()
    mock_window.video_list_received = Mock()
    mock_window.new_download = Mock()
    server.set_window(mock_window)
    
    # Start server in a separate thread
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    
    # Wait for server to start
    time.sleep(0.5)
    
    yield {
        'server': server,
        'base_url': 'http://127.0.0.1:5556',
        'mock_window': mock_window
    }
    
    # Server will stop when thread ends due to daemon=True


@pytest.fixture
def mock_download_worker():
    """Mock DownloadWorker for testing without actual downloads"""
    with patch('core.downloader.DownloadWorker') as mock_worker:
        yield mock_worker


@pytest.fixture
def sample_download_data():
    """Sample download request data for testing"""
    return {
        'image': {
            'type': 'image',
            'url': 'https://example.com/image.jpg',
            'pageUrl': 'https://example.com/page',
            'title': 'Test Image',
            'thumbnail': 'https://example.com/thumb.jpg'
        },
        'video': {
            'type': 'video',
            'url': 'https://youtube.com/watch?v=test123',
            'pageUrl': 'https://youtube.com/watch?v=test123',
            'title': 'Test Video',
            'thumbnail': 'https://youtube.com/thumb.jpg'
        },
        'video_list': {
            'type': 'video-list',
            'pageUrl': 'https://instagram.com/p/test123',
            'title': 'Instagram Carousel',
            'videos': [
                {
                    'url': 'https://instagram.com/video1.mp4',
                    'title': 'Video 1',
                    'thumbnail': 'https://instagram.com/thumb1.jpg'
                },
                {
                    'url': 'https://instagram.com/video2.mp4',
                    'title': 'Video 2',
                    'thumbnail': 'https://instagram.com/thumb2.jpg'
                }
            ]
        },
        'direct_video': {
            'type': 'direct-video',
            'url': 'https://example.com/video.mp4',
            'pageUrl': 'https://example.com/video-page',
            'title': 'Direct Video',
            'referrer': 'https://example.com'
        }
    }


@pytest.fixture
def mock_yt_dlp():
    """Mock yt-dlp for testing without actual video extraction"""
    mock_info = {
        'id': 'test123',
        'title': 'Test Video',
        'uploader': 'Test Channel',
        'duration': 120,
        'view_count': 1000,
        'thumbnail': 'https://example.com/thumb.jpg',
        'formats': [
            {'format_id': 'best', 'ext': 'mp4', 'height': 720}
        ]
    }
    
    with patch('yt_dlp.YoutubeDL') as mock_ytdl:
        mock_instance = Mock()
        mock_instance.extract_info.return_value = mock_info
        mock_instance.prepare_filename.return_value = '/fake/path/test_video.mp4'
        mock_ytdl.return_value.__enter__.return_value = mock_instance
        yield mock_ytdl


@pytest.fixture
def mock_requests():
    """Mock requests for testing HTTP downloads"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '1024'}
        mock_response.iter_content.return_value = [b'fake_image_data'] * 10
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        yield mock_get