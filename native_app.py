#!/usr/bin/env python3
"""
Native Media Downloader App
Simple PyQt5 app that receives URLs from browser extension and downloads media
"""

from version import __version__  # noqa: F401  (available for submodules)

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
from PyQt5.QtGui import QIcon, QPixmap, QPalette, QColor

import yt_dlp

from config.settings import Settings
from core.downloader import DownloadWorker
from ui.components.download_item import DownloadItem
from ui.components.video_selector import VideoSelectorDialog
from ui.main_window import MainWindow
from api.flask_server import FlaskServer

def set_dark_mode(app):
    """Force dark mode regardless of system settings"""
    dark_palette = QPalette()

    # Base colors
    dark_palette.setColor(QPalette.Window, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.WindowText, QColor(224, 224, 224))
    dark_palette.setColor(QPalette.Base, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.ToolTipBase, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.ToolTipText, QColor(224, 224, 224))
    dark_palette.setColor(QPalette.Text, QColor(224, 224, 224))
    dark_palette.setColor(QPalette.Button, QColor(50, 50, 50))
    dark_palette.setColor(QPalette.ButtonText, QColor(224, 224, 224))
    dark_palette.setColor(QPalette.BrightText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.Link, QColor(90, 176, 255))
    dark_palette.setColor(QPalette.Highlight, QColor(90, 176, 255))
    dark_palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))

    # Disabled colors
    dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(128, 128, 128))
    dark_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(128, 128, 128))
    dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(128, 128, 128))

    app.setPalette(dark_palette)
    app.setStyle('Fusion')  # Fusion style works well with custom palettes


# Queue for downloads
download_queue = Queue()

# Flask server instance
flask_server = None
window = None





if __name__ == '__main__':
    # Create Qt application
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)  # Important for macOS
    set_dark_mode(qt_app)

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