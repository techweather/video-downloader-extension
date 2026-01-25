"""
Tests for core downloader functionality
"""

import pytest
import os
import tempfile
import queue
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from core.downloader import DownloadWorker
from test_urls import TEST_URLS, get_sample_url


class TestDownloadWorker:
    """Test cases for DownloadWorker functionality"""
    
    @pytest.fixture
    def download_queue(self):
        """Create a download queue for testing"""
        return queue.Queue()
    
    @pytest.fixture
    def download_worker(self, download_queue):
        """Create a DownloadWorker instance for testing"""
        worker = DownloadWorker(download_queue)
        return worker
    
    def test_download_worker_initialization(self, download_worker, download_queue):
        """Test DownloadWorker initializes correctly"""
        assert download_worker.download_queue == download_queue
        assert download_worker.current_download_id is None
        assert download_worker.cancelled_downloads == set()
        assert download_worker.partial_files == set()
    
    def test_cancel_download(self, download_worker):
        """Test download cancellation"""
        download_id = "test_download_123"
        
        # Test basic cancellation
        download_worker.cancel_download(download_id)
        assert download_id in download_worker.cancelled_downloads
    
    def test_cancel_active_download(self, download_worker):
        """Test cancelling an active download"""
        download_id = "test_download_456"
        download_worker.current_download_id = download_id
        
        # Mock active process
        mock_process = Mock()
        download_worker.active_process = mock_process
        
        download_worker.cancel_download(download_id)
        
        assert download_id in download_worker.cancelled_downloads
        mock_process.terminate.assert_called_once()
    
    @patch('os.path.exists')
    @patch('os.remove')
    def test_cleanup_partial_files(self, mock_remove, mock_exists, download_worker):
        """Test partial file cleanup"""
        # Set up test data
        test_file = "/tmp/test_file.mp4"
        download_worker.partial_files.add(test_file)
        # Set current_download_info as an attribute (not property) as the method uses getattr
        download_worker.current_download_info = {'save_path': '/tmp/test_save'}
        mock_exists.return_value = True
        
        download_worker.cleanup_partial_files("test_id")
        
        mock_remove.assert_called_with(test_file)
        assert len(download_worker.partial_files) == 0
    
    def test_extract_vimeo_id_from_url(self, download_worker):
        """Test Vimeo ID extraction from various URL formats"""
        test_cases = [
            ('https://vimeo.com/123456789', '123456789'),
            ('https://player.vimeo.com/video/987654321', '987654321'),
            ('https://vimeo.com/channels/test/555666777', '555666777'),
            ('invalid-url', None)
        ]
        
        for url, expected_id in test_cases:
            result = download_worker.extract_vimeo_id(url)
            if expected_id:
                assert result == expected_id
            else:
                assert result is None
    
    def test_is_vimeo_embed_error(self, download_worker):
        """Test Vimeo embed error detection"""
        # Test cases for Vimeo embed errors
        test_cases = [
            ('401 Unauthorized from player.vimeo.com', 'https://player.vimeo.com/video/123', True),
            ('403 Forbidden vimeo embed', 'https://vimeo.com/123', True),
            ('Random error message', 'https://youtube.com/watch?v=123', False),
            ('Network timeout', 'https://example.com/video.mp4', False)
        ]
        
        for error_message, url, expected in test_cases:
            result = download_worker.is_vimeo_embed_error(error_message, url)
            assert result == expected
    
    @patch('requests.get')
    def test_download_image_success(self, mock_get, download_worker, temp_download_dir):
        """Test successful image download"""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '1024'}
        mock_response.iter_content.return_value = [b'fake_image_data'] * 10
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test image download
        result = download_worker.download_image(
            url='https://example.com/test.jpg',
            download_id='test_123',
            save_path=temp_download_dir,
            organize_by_platform=True
        )
        
        # Verify result
        assert result is not None
        assert result.endswith('.jpg')
        assert 'images' in result  # Should be in images subdirectory
    
    @patch('requests.get')
    def test_download_image_with_referrer(self, mock_get, download_worker, temp_download_dir):
        """Test image download with referrer headers"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '1024'}
        mock_response.iter_content.return_value = [b'fake_data']
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        referrer = 'https://example.com/source-page'
        
        download_worker.download_image(
            url='https://example.com/test.jpg',
            download_id='test_456',
            save_path=temp_download_dir,
            organize_by_platform=False,
            referrer=referrer
        )
        
        # Check that requests.get was called with proper headers
        call_args = mock_get.call_args
        headers = call_args[1]['headers']
        assert headers['Referer'] == referrer
        assert 'Origin' in headers
    
    def test_progress_hook_downloading(self, download_worker):
        """Test progress hook during downloading"""
        download_worker.current_download_id = 'test_789'
        download_worker.has_emitted_downloading_status = False
        
        # Mock the signals
        download_worker.status_update = Mock()
        download_worker.progress_update = Mock()
        
        # Test downloading progress
        progress_data = {
            'status': 'downloading',
            'downloaded_bytes': 500,
            'total_bytes': 1000
        }
        
        download_worker.progress_hook(progress_data)
        
        # Verify signals were emitted
        download_worker.status_update.emit.assert_called_once()
        download_worker.progress_update.emit.assert_called_once()
        assert download_worker.has_emitted_downloading_status is True
    
    def test_progress_hook_finished(self, download_worker):
        """Test progress hook when download is finished"""
        download_worker.current_download_id = 'test_finished'
        download_worker.progress_update = Mock()
        
        progress_data = {'status': 'finished'}
        download_worker.progress_hook(progress_data)
        
        download_worker.progress_update.emit.assert_called_with(
            'test_finished', 100, "Processing..."
        )
    
    def test_progress_hook_cancelled(self, download_worker):
        """Test progress hook when download is cancelled"""
        download_id = 'test_cancelled'
        download_worker.current_download_id = download_id
        download_worker.cancelled_downloads.add(download_id)
        
        progress_data = {'status': 'downloading'}
        
        with pytest.raises(Exception, match="Download cancelled by user"):
            download_worker.progress_hook(progress_data)


class TestDownloadWorkerIntegration:
    """Integration tests for DownloadWorker (with mocked external dependencies)"""
    
    @pytest.fixture
    def download_queue(self):
        return queue.Queue()
    
    @pytest.fixture
    def download_worker(self, download_queue):
        worker = DownloadWorker(download_queue)
        # Mock the signals to avoid PyQt5 dependencies
        worker.progress_update = Mock()
        worker.download_complete = Mock()
        worker.download_error = Mock()
        worker.download_cancelled = Mock()
        worker.status_update = Mock()
        return worker
    
    def test_download_workflow_image(self, download_worker, download_queue, sample_download_data, mock_requests):
        """Test complete image download workflow"""
        download_data = sample_download_data['image'].copy()
        download_data.update({
            'id': 'test_image_workflow',
            'save_path': '/tmp/test_downloads'
        })
        
        # Add to queue
        download_queue.put(download_data)
        download_queue.put(None)  # Sentinel to stop worker
        
        # Run worker
        download_worker.run()
        
        # Verify download_complete was called
        download_worker.download_complete.emit.assert_called_once()
    
    def test_download_workflow_cancelled(self, download_worker, download_queue, sample_download_data):
        """Test download workflow when cancelled"""
        download_data = sample_download_data['image'].copy()
        download_data.update({
            'id': 'test_cancelled_workflow',
            'save_path': '/tmp/test_downloads'
        })
        
        # Cancel before adding to queue
        download_worker.cancel_download('test_cancelled_workflow')
        
        download_queue.put(download_data)
        download_queue.put(None)  # Sentinel
        
        download_worker.run()
        
        # Verify cancellation was handled
        download_worker.download_cancelled.emit.assert_called_once()
    
    @patch('yt_dlp.YoutubeDL')
    def test_download_workflow_video_ytdlp(self, mock_ytdl, download_worker, download_queue, sample_download_data):
        """Test video download workflow with yt-dlp"""
        # Setup mock
        mock_instance = Mock()
        mock_info = {
            'id': 'test123',
            'title': 'Test Video',
            'extractor': 'youtube',
            'thumbnail': 'https://example.com/thumb.jpg'
        }
        mock_instance.extract_info.return_value = mock_info
        mock_instance.prepare_filename.return_value = '/tmp/test_video.mp4'
        mock_ytdl.return_value.__enter__.return_value = mock_instance
        
        # Mock file existence
        with patch('os.path.exists', return_value=True):
            download_data = sample_download_data['video'].copy()
            download_data.update({
                'id': 'test_video_workflow',
                'save_path': '/tmp/test_downloads'
            })
            
            download_queue.put(download_data)
            download_queue.put(None)
            
            download_worker.run()
            
            # Verify yt-dlp was called
            mock_ytdl.assert_called()
            download_worker.download_complete.emit.assert_called_once()


class TestDownloadWorkerHelpers:
    """Test helper functions and utilities"""
    
    def test_vimeo_id_extraction_edge_cases(self):
        """Test Vimeo ID extraction with edge cases"""
        worker = DownloadWorker(queue.Queue())
        
        edge_cases = [
            ('', None),
            ('https://notavimeourl.com/123', None),
            ('vimeo.com/abc', None),  # Non-numeric ID
            ('https://vimeo.com/123/456/789', '123')  # Multiple numbers, should pick first
        ]
        
        for url, expected in edge_cases:
            result = worker.extract_vimeo_id(url)
            assert result == expected
    
    @patch('pathlib.Path.glob')
    @patch('pathlib.Path.unlink')
    def test_ytdlp_fragment_cleanup(self, mock_unlink, mock_glob, temp_download_dir):
        """Test yt-dlp fragment file cleanup"""
        worker = DownloadWorker(queue.Queue())
        
        # Mock fragment files
        mock_fragment_file1 = Mock(name='test.f1')
        mock_fragment_file1.is_file.return_value = True
        mock_fragment_file1.stat.return_value = Mock(st_mtime=1000000000)
        
        mock_fragment_file2 = Mock(name='test.part')
        mock_fragment_file2.is_file.return_value = True
        mock_fragment_file2.stat.return_value = Mock(st_mtime=1000000000)
        
        # Mock glob to return files only for the first pattern call
        call_count = 0
        def mock_glob_side_effect(pattern):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # First pattern call
                return [mock_fragment_file1, mock_fragment_file2]
            else:
                return []  # Subsequent pattern calls return empty
        
        mock_glob.side_effect = mock_glob_side_effect
        
        import time
        with patch('time.time', return_value=1000000100):  # 100 seconds later
            worker._cleanup_ytdlp_fragments(temp_download_dir)
            
            # Should call unlink on recent files (use assert_called instead of assert_called_once due to multiple patterns)
            mock_fragment_file1.unlink.assert_called()
            mock_fragment_file2.unlink.assert_called()


# Utility functions for test setup
def create_test_download_data(download_type, url=None, **kwargs):
    """Helper to create test download data"""
    base_data = {
        'id': f'test_{download_type}_{hash(url or "default")}',
        'type': download_type,
        'url': url or get_sample_url('youtube' if download_type == 'video' else 'direct_images'),
        'save_path': '/tmp/test_downloads',
        'organize_by_platform': True
    }
    base_data.update(kwargs)
    return base_data