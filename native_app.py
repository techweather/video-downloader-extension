#!/usr/bin/env python3
"""
Native Media Downloader App
Simple PyQt5 app that receives URLs from browser extension and downloads media
"""

import sys
import os
import json
import requests
import subprocess
import re
from pathlib import Path
from datetime import datetime
from threading import Thread
from queue import Queue
from urllib.parse import urlparse, unquote

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QLabel, QProgressBar,
                           QListWidget, QListWidgetItem, QSystemTrayIcon, 
                           QMenu, QAction, QStyle, QDialog, QComboBox,
                           QCheckBox, QDialogButtonBox, QFileDialog, QScrollArea)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QPixmap

import yt_dlp

from config.settings import Settings
from core.downloader import DownloadWorker
from ui.components.download_item import DownloadItem
from ui.components.video_selector import VideoSelectorDialog
from ui.main_window import MainWindow
from api.flask_server import FlaskServer

# Queue for downloads
download_queue = Queue()

# Flask server instance
flask_server = None
window = None





if __name__ == '__main__':
    # Create Qt application
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)  # Important for macOS
    
    # Create main window
    window = MainWindow(download_queue)
    window.show()  # Show immediately for testing
    
    # Create and configure Flask server
    flask_server = FlaskServer(port=5555, debug=False)
    flask_server.set_window(window)
    
    # Start Flask in background thread
    flask_thread = Thread(target=flask_server.run, daemon=True)
    flask_thread.start()
    
    print("Native app running on http://127.0.0.1:5555")
    print("Window should be visible. Check your dock/menu bar.")
    
    # Run Qt event loop
    sys.exit(qt_app.exec_())