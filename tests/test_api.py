"""
Tests for Flask API endpoints
"""

import pytest
import requests
import json
from unittest.mock import patch
from api.flask_server import FlaskServer


class TestFlaskAPI:
    """Test cases for Flask API endpoints"""
    
    def test_health_endpoint_basic(self, flask_app):
        """Test basic health endpoint functionality"""
        with flask_app.test_client() as client:
            response = client.get('/health')
            assert response.status_code == 200
            
            data = response.get_json()
            assert data['status'] == 'healthy'
            assert data['message'] == 'Media Downloader API is running'
            assert 'window_connected' in data
    
    def test_health_endpoint_with_running_server(self, running_flask_server):
        """Test health endpoint with actual running server"""
        base_url = running_flask_server['base_url']
        response = requests.get(f'{base_url}/health')
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert data['window_connected'] is True  # Should be True because of mock window
    
    def test_root_endpoint(self, flask_app):
        """Test root endpoint returns API information"""
        with flask_app.test_client() as client:
            response = client.get('/')
            assert response.status_code == 200
            
            data = response.get_json()
            assert data['name'] == 'Media Downloader API'
            assert data['version'] == '1.0.0'
            assert 'endpoints' in data
            assert len(data['endpoints']) == 3
    
    def test_download_endpoint_no_data(self, flask_app):
        """Test download endpoint with no data returns 415"""
        with flask_app.test_client() as client:
            response = client.post('/download')
            assert response.status_code == 415
    
    def test_download_endpoint_image(self, running_flask_server, sample_download_data):
        """Test download endpoint with image data"""
        base_url = running_flask_server['base_url']
        mock_window = running_flask_server['mock_window']
        mock_window.reset_mock()
        
        image_data = sample_download_data['image']
        
        response = requests.post(
            f'{base_url}/download',
            json=image_data,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'queued'
        
        # Verify the window signal was emitted
        mock_window.new_download.emit.assert_called_once_with(image_data)
    
    def test_download_endpoint_video(self, running_flask_server, sample_download_data):
        """Test download endpoint with video data"""
        base_url = running_flask_server['base_url']
        mock_window = running_flask_server['mock_window']
        mock_window.reset_mock()
        
        video_data = sample_download_data['video']
        
        response = requests.post(
            f'{base_url}/download',
            json=video_data,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'queued'
        
        # Verify the window signal was emitted
        mock_window.new_download.emit.assert_called_once_with(video_data)
    
    def test_download_endpoint_video_list(self, running_flask_server, sample_download_data):
        """Test download endpoint with video list data"""
        base_url = running_flask_server['base_url']
        mock_window = running_flask_server['mock_window']
        mock_window.reset_mock()
        
        video_list_data = sample_download_data['video_list']
        
        response = requests.post(
            f'{base_url}/download',
            json=video_list_data,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'queued'
        
        # Verify the video_list_received signal was emitted
        mock_window.video_list_received.emit.assert_called_once_with(video_list_data)
    
    def test_download_endpoint_without_window(self, flask_app, sample_download_data):
        """Test download endpoint fails gracefully without window reference"""
        with flask_app.test_client() as client:
            # Don't set window reference (server.set_window not called)
            image_data = sample_download_data['image']
            
            response = client.post('/download', json=image_data)
            assert response.status_code == 503
            
            data = response.get_json()
            assert data['status'] == 'error'
            assert 'Application not ready' in data['message']
    
    def test_invalid_json_data(self, running_flask_server):
        """Test download endpoint with invalid JSON"""
        base_url = running_flask_server['base_url']
        
        response = requests.post(
            f'{base_url}/download',
            data='invalid json',
            headers={'Content-Type': 'application/json'}
        )
        
        # Should return 400 for invalid JSON
        assert response.status_code == 400
    
    def test_cors_headers_present(self, running_flask_server):
        """Test that CORS headers are present in responses"""
        base_url = running_flask_server['base_url']
        
        response = requests.get(f'{base_url}/health')
        assert response.status_code == 200
        
        # CORS headers should be present (though specific headers depend on flask-cors config)
        # At minimum, we should be able to make cross-origin requests
        assert response.headers.get('Access-Control-Allow-Origin') is not None
    
    @pytest.mark.parametrize("endpoint", ["/health", "/", "/download"])
    def test_endpoints_exist(self, flask_app, endpoint):
        """Test that all documented endpoints exist"""
        with flask_app.test_client() as client:
            if endpoint == "/download":
                # POST endpoint
                response = client.post(endpoint)
            else:
                # GET endpoint
                response = client.get(endpoint)
            
            # Should not return 404
            assert response.status_code != 404


class TestFlaskServerClass:
    """Test cases for FlaskServer class functionality"""
    
    def test_flask_server_initialization(self):
        """Test FlaskServer initializes correctly"""
        server = FlaskServer(port=5557, debug=True)
        
        assert server.port == 5557
        assert server.debug is True
        assert server.window is None
        assert server.app is not None
    
    def test_set_window_method(self):
        """Test setting window reference"""
        from unittest.mock import Mock
        
        server = FlaskServer()
        mock_window = Mock()
        
        server.set_window(mock_window)
        assert server.window == mock_window
    
    def test_default_configuration(self):
        """Test default server configuration"""
        server = FlaskServer()
        
        assert server.port == 5555
        assert server.debug is False