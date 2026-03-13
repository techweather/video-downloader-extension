"""
Flask API server for Media Downloader App
Handles requests from browser extension and communicates with the main application
"""

from flask import Flask, request, jsonify
from flask_cors import CORS


class FlaskServer:
    """
    Flask API server for handling download requests from browser extensions.
    
    Features:
    - CORS-enabled for cross-origin requests
    - Download endpoint for individual downloads and video lists
    - Integration with main application window via callbacks
    """
    
    def __init__(self, port=5555, debug=False):
        """
        Initialize Flask server.
        
        Args:
            port: Port number to run server on (default: 5555)
            debug: Enable Flask debug mode (default: False)
        """
        self.port = port
        self.debug = debug
        self.app = Flask(__name__)
        
        # Enable CORS for all routes to allow extension requests
        CORS(self.app)
        
        # Reference to main application window for signal emission
        self.window = None
        
        # Set up routes
        self._setup_routes()
    
    def set_window(self, window):
        """
        Set reference to main application window.
        
        Args:
            window: MainWindow instance for signal emission
        """
        self.window = window
    
    def _setup_routes(self):
        """Set up Flask routes"""
        
        @self.app.route('/download', methods=['POST'])
        def download():
            """
            Handle download requests from browser extension.
            
            Expected JSON payload:
            - type: 'image', 'video', 'video-list'
            - url: Media URL (for single downloads)
            - videos: List of video objects (for video-list type)
            - pageUrl: Source page URL
            - title: Media title
            - thumbnail: Thumbnail URL (optional)
            
            Returns:
                JSON response with status
            """
            data = request.json
            
            # Add detailed logging for debugging
            import json
            
            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400
            
            # Check if this is a video list that needs selection
            if data.get('type') == 'video-list':
                
                if self.window:
                    # Emit signal to show video selector dialog
                    self.window.video_list_received.emit(data)
                else:
                    print("[ERROR] Window reference is None!")
                    return jsonify({"status": "error", "message": "Application not ready"}), 503
                    
            else:
                # Handle single download (image, video, etc.)
                if self.window:
                    # Emit signal to add single download
                    self.window.new_download.emit(data)
                else:
                    print("[ERROR] Window reference is None!")
                    return jsonify({"status": "error", "message": "Application not ready"}), 503
            
            return jsonify({"status": "queued"})

        @self.app.route('/classify', methods=['POST'])
        def classify_url():
            data = request.json
            url = data.get('url', '') if data else ''
            try:
                import yt_dlp
                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                    supported = any(
                        ie.suitable(url)
                        for ie in ydl._ies.values()
                        if ie.ie_key() != 'Generic'
                    )
                return jsonify({'supported': supported})
            except Exception:
                return jsonify({'supported': False})

        @self.app.route('/health', methods=['GET'])
        def health():
            """
            Health check endpoint.
            
            Returns:
                JSON response indicating server status
            """
            return jsonify({
                "status": "healthy",
                "message": "dlwithit API is running",
                "window_connected": self.window is not None
            })
        
        @self.app.route('/', methods=['GET'])
        def root():
            """
            Root endpoint with basic information.
            
            Returns:
                JSON response with API information
            """
            return jsonify({
                "name": "dlwithit API",
                "version": "1.0.0",
                "endpoints": [
                    {"path": "/download", "method": "POST", "description": "Submit download requests"},
                    {"path": "/health", "method": "GET", "description": "Health check"},
                    {"path": "/", "method": "GET", "description": "API information"}
                ]
            })
    
    def run(self):
        """
        Start the Flask server.
        
        This method blocks and should typically be run in a separate thread.
        """
        print(f"[INFO] Starting Flask server on port {self.port}")
        self.app.run(
            host='127.0.0.1',
            port=self.port, 
            debug=self.debug,
            use_reloader=False,  # Disable reloader to prevent issues with threading
            threaded=True  # Enable threading for concurrent requests
        )
    
    def shutdown(self):
        """
        Shutdown the Flask server gracefully.
        
        Note: This requires the server to be running with threaded=True
        """
        try:
            # Get the shutdown function from Werkzeug
            shutdown = request.environ.get('werkzeug.server.shutdown')
            if shutdown:
                shutdown()
                print("[INFO] Flask server shutdown requested")
            else:
                print("[WARNING] Unable to shutdown Flask server gracefully")
        except Exception as e:
            print(f"[ERROR] Error during Flask server shutdown: {e}")


# Convenience function for creating and configuring server
def create_flask_server(port=5555, debug=False):
    """
    Create and configure a Flask server instance.
    
    Args:
        port: Port number to run server on (default: 5555)
        debug: Enable Flask debug mode (default: False)
        
    Returns:
        FlaskServer: Configured Flask server instance
    """
    return FlaskServer(port=port, debug=debug)


# Convenience function for running server in background thread
def run_flask_server(server, daemon=True):
    """
    Run Flask server in a background thread.
    
    Args:
        server: FlaskServer instance to run
        daemon: Whether thread should be daemon thread (default: True)
        
    Returns:
        Thread: The thread running the Flask server
    """
    from threading import Thread
    
    flask_thread = Thread(target=server.run, daemon=daemon)
    flask_thread.start()
    return flask_thread