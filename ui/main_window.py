"""
MainWindow for Media Downloader App
Main application window with UI initialization, settings management, and download handling
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QPushButton, QLabel, QListWidget, QListWidgetItem, 
                           QSystemTrayIcon, QMenu, QAction, QStyle, QCheckBox, QComboBox,
                           QFileDialog, QApplication, QDesktopWidget)
from PyQt5.QtCore import pyqtSignal, QRect
from PyQt5.QtGui import QResizeEvent, QMoveEvent

from config.settings import Settings
from core.downloader import DownloadWorker
from ui.components.download_item import DownloadItem
from ui.components.video_selector import VideoSelectorDialog


class MainWindow(QMainWindow):
    """
    Main application window for the Media Downloader.
    
    Features:
    - Settings management and UI
    - Download queue display and management
    - System tray integration
    - Video selector dialog handling
    - Download worker coordination
    """
    
    new_download = pyqtSignal(dict)
    video_list_received = pyqtSignal(dict)  # Signal for video lists from scraping
    
    def __init__(self, download_queue):
        """
        Initialize the main window.
        
        Args:
            download_queue: Queue object for coordinating downloads with worker
        """
        super().__init__()
        self.download_queue = download_queue
        self.download_items = {}
        self.settings = Settings.load()
        
        # Initialize UI components
        self.init_ui()
        self.init_worker()
        self.init_tray()
        
        # Restore window position and size
        self.restore_window_geometry()
        
        # Connect signals
        self.new_download.connect(self.add_download)
        self.video_list_received.connect(self.handle_video_list)
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Media Downloader")
        # Window geometry will be set by restore_window_geometry()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        
        # Create UI sections
        self._create_location_section(layout)
        self._create_settings_section(layout)
        self._create_download_queue_section(layout)
        
        # Status bar
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        central_widget.setLayout(layout)
    
    def _create_location_section(self, parent_layout):
        """Create the save location section"""
        location_widget = QWidget()
        location_layout = QHBoxLayout()
        location_layout.setContentsMargins(10, 5, 10, 5)
        
        # Location display
        location_label = QLabel("Save to:")
        location_label.setStyleSheet("color: #333;")
        self.location_display = QLabel(self.get_display_path())
        self.location_display.setStyleSheet("color: #2c3e50; font-weight: bold;")
        
        # Custom location checkbox
        self.use_custom_checkbox = QCheckBox("Use custom location")
        self.use_custom_checkbox.setChecked(self.settings['use_custom_location'])
        self.use_custom_checkbox.toggled.connect(self.toggle_custom_location)
        self.use_custom_checkbox.setStyleSheet("""
            QCheckBox { 
                color: #333;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #666;
                border-radius: 3px;
                background-color: #fff;
            }
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border-color: #2980b9;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iNyIgdmlld0JveD0iMCAwIDEwIDciIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik04LjUgMS41TDMuNSA2LjVMMSA0IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
            }
            QCheckBox::indicator:unchecked {
                background-color: #f8f9fa;
                border-color: #666;
            }
            QCheckBox::indicator:hover {
                border-color: #3498db;
            }
        """)
        
        # Change location button
        self.change_location_btn = QPushButton("Change Location")
        self.change_location_btn.clicked.connect(self.change_save_location)
        self.change_location_btn.setStyleSheet("""
            QPushButton {
                background: #3498db;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        
        # Assemble location layout
        location_layout.addWidget(location_label)
        location_layout.addWidget(self.location_display)
        location_layout.addStretch()
        location_layout.addWidget(self.use_custom_checkbox)
        location_layout.addWidget(self.change_location_btn)
        
        location_widget.setLayout(location_layout)
        location_widget.setStyleSheet("QWidget { background-color: #ecf0f1; border-radius: 5px; }")
        
        parent_layout.addWidget(location_widget)
    
    def _create_settings_section(self, parent_layout):
        """Create the settings section"""
        settings_widget = QWidget()
        settings_layout = QVBoxLayout()
        settings_layout.setContentsMargins(10, 10, 10, 10)
        
        # Encoding settings row
        encoding_row = QHBoxLayout()
        
        self.encode_checkbox = QCheckBox("Auto-encode WebM/VP9 to H.264")
        self.encode_checkbox.setChecked(self.settings.get('encode_vp9', True))
        self.encode_checkbox.toggled.connect(self.save_settings)
        self.encode_checkbox.setStyleSheet("""
            QCheckBox { 
                color: #333;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #666;
                border-radius: 3px;
                background-color: #fff;
            }
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border-color: #2980b9;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iNyIgdmlld0JveD0iMCAwIDEwIDciIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik04LjUgMS41TDMuNSA2LjVMMSA0IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
            }
            QCheckBox::indicator:unchecked {
                background-color: #f8f9fa;
                border-color: #666;
            }
            QCheckBox::indicator:hover {
                border-color: #3498db;
            }
        """)
        
        self.keep_original_checkbox = QCheckBox("Keep original after encoding")
        self.keep_original_checkbox.setChecked(self.settings.get('keep_original', False))
        self.keep_original_checkbox.toggled.connect(self.save_settings)
        self.keep_original_checkbox.setStyleSheet("""
            QCheckBox { 
                color: #333;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #666;
                border-radius: 3px;
                background-color: #fff;
            }
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border-color: #2980b9;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iNyIgdmlld0JveD0iMCAwIDEwIDciIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik04LjUgMS41TDMuNSA2LjVMMSA0IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
            }
            QCheckBox::indicator:unchecked {
                background-color: #f8f9fa;
                border-color: #666;
            }
            QCheckBox::indicator:hover {
                border-color: #3498db;
            }
        """)
        
        encoding_row.addWidget(self.encode_checkbox)
        encoding_row.addWidget(self.keep_original_checkbox)
        encoding_row.addStretch()
        
        # Organization settings row
        organization_row = QHBoxLayout()
        
        self.organize_folders_checkbox = QCheckBox("Organize by platform (YouTube, Instagram, etc.)")
        self.organize_folders_checkbox.setChecked(self.settings.get('organize_by_platform', True))
        self.organize_folders_checkbox.toggled.connect(self.save_settings)
        self.organize_folders_checkbox.setStyleSheet("""
            QCheckBox { 
                color: #333;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #666;
                border-radius: 3px;
                background-color: #fff;
            }
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border-color: #2980b9;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iNyIgdmlld0JveD0iMCAwIDEwIDciIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik04LjUgMS41TDMuNSA2LjVMMSA0IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
            }
            QCheckBox::indicator:unchecked {
                background-color: #f8f9fa;
                border-color: #666;
            }
            QCheckBox::indicator:hover {
                border-color: #3498db;
            }
        """)
        
        # Metadata options dropdown
        metadata_label = QLabel("Metadata:")
        metadata_label.setStyleSheet("color: #333; font-weight: 500;")
        
        self.metadata_combo = QComboBox()
        self.metadata_combo.addItems([
            "None", 
            "Embedded in file", 
            "Sidecar files"
        ])
        
        # Map display text to internal values
        self.metadata_options = {
            "None": "none",
            "Embedded in file": "embedded", 
            "Sidecar files": "sidecar"
        }
        
        # Backward compatibility: migrate old save_metadata boolean to new format
        if 'metadata_option' in self.settings:
            metadata_option = self.settings['metadata_option']
        elif 'save_metadata' in self.settings:
            # Migrate old boolean setting
            metadata_option = "sidecar" if self.settings['save_metadata'] else "none"
            # Remove old setting
            self.settings.pop('save_metadata', None)
        else:
            metadata_option = "none"
        
        # Set dropdown selection based on current setting
        for i, text in enumerate(self.metadata_combo.itemText(j) for j in range(self.metadata_combo.count())):
            if self.metadata_options[text] == metadata_option:
                self.metadata_combo.setCurrentIndex(i)
                break
        
        self.metadata_combo.currentTextChanged.connect(self.save_settings)
        self.metadata_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #666;
                border-radius: 5px;
                padding: 5px 8px;
                background-color: #fff;
                color: #333;
                font-size: 13px;
                min-width: 120px;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 8px;
                border: 2px solid #666;
                border-bottom: none;
                border-left: none;
                transform: rotate(45deg);
                margin-right: 8px;
            }
        """)
        
        organization_row.addWidget(self.organize_folders_checkbox)
        organization_row.addWidget(metadata_label)
        organization_row.addWidget(self.metadata_combo)
        organization_row.addStretch()
        
        # Assemble settings layout
        settings_layout.addLayout(encoding_row)
        settings_layout.addLayout(organization_row)
        
        settings_widget.setLayout(settings_layout)
        settings_widget.setStyleSheet("QWidget { background-color: #f0f0f0; border-radius: 5px; }")
        
        parent_layout.addWidget(settings_widget)
    
    def _create_adaptive_divider(self):
        """Create a system-aware adaptive divider that blends with the current theme"""
        divider = QWidget()
        divider.setFixedHeight(1)
        
        # Get system palette to detect theme using proper roles
        palette = QApplication.palette()
        window_color = palette.color(palette.Window)
        window_text_color = palette.color(palette.WindowText)
        
        # Extract RGB values
        bg_r, bg_g, bg_b = window_color.red(), window_color.green(), window_color.blue()
        text_r, text_g, text_b = window_text_color.red(), window_text_color.green(), window_text_color.blue()
        
        # Calculate luminance of background to determine theme
        bg_luminance = (0.299 * bg_r + 0.587 * bg_g + 0.114 * bg_b) / 255
        text_luminance = (0.299 * text_r + 0.587 * text_g + 0.114 * text_b) / 255
        
        # Use the contrast between background and text to determine theme
        is_dark_theme = bg_luminance < text_luminance
        
        if is_dark_theme:
            # Dark theme: make divider 30-40% lighter than background
            factor = 1.35
            divider_r = min(255, int(bg_r * factor))
            divider_g = min(255, int(bg_g * factor))
            divider_b = min(255, int(bg_b * factor))
            theme_type = "Dark"
        else:
            # Light theme: make divider 20-30% darker than background
            factor = 0.75
            divider_r = int(bg_r * factor)
            divider_g = int(bg_g * factor)
            divider_b = int(bg_b * factor)
            theme_type = "Light"
        
        divider_color = f"rgb({divider_r}, {divider_g}, {divider_b})"
        
        # Debug prints for theme detection verification
        print(f"[DEBUG] Theme detected: {theme_type}")
        print(f"[DEBUG] Background RGB: ({bg_r}, {bg_g}, {bg_b}) - Luminance: {bg_luminance:.2f}")
        print(f"[DEBUG] Text RGB: ({text_r}, {text_g}, {text_b}) - Luminance: {text_luminance:.2f}")
        print(f"[DEBUG] Divider color: {divider_color}")
        
        divider.setStyleSheet(f"""
            QWidget {{
                background-color: {divider_color};
                border: none;
                margin: 0px;
            }}
        """)
        
        return divider
    
    def _create_download_queue_section(self, parent_layout):
        """Create the download queue section"""
        # Header with clear button
        header_layout = QHBoxLayout()
        header_label = QLabel("<h2>Download Queue</h2>")
        clear_btn = QPushButton("Clear Completed")
        clear_btn.clicked.connect(self.clear_completed)
        
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        header_layout.addWidget(clear_btn)
        
        # Download list
        self.download_list = QListWidget()
        
        parent_layout.addLayout(header_layout)
        parent_layout.addWidget(self.download_list)
    
    def get_display_path(self):
        """
        Get a user-friendly display path.
        
        Returns:
            str: Display path with ~ substitution for home directory
        """
        if self.settings['use_custom_location']:
            path = self.settings['custom_location']
        else:
            path = str(Path.home() / 'Downloads' / 'Media')
        
        # Replace home directory with ~
        home = str(Path.home())
        if path.startswith(home):
            path = '~' + path[len(home):]
        
        return path
    
    def change_save_location(self):
        """Open folder picker dialog"""
        current_path = (self.settings['custom_location'] if self.settings['use_custom_location'] 
                       else str(Path.home() / 'Downloads' / 'Media'))
        
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Download Folder",
            current_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder:
            self.settings['custom_location'] = folder
            self.settings['use_custom_location'] = True
            self.use_custom_checkbox.setChecked(True)
            self.save_settings()
            self.location_display.setText(self.get_display_path())
    
    def toggle_custom_location(self, checked):
        """Toggle between custom and default location"""
        self.settings['use_custom_location'] = checked
        self.save_settings()
        self.location_display.setText(self.get_display_path())
    
    def save_settings(self):
        """Save current settings to file"""
        self.settings['encode_vp9'] = self.encode_checkbox.isChecked()
        self.settings['keep_original'] = self.keep_original_checkbox.isChecked()
        self.settings['organize_by_platform'] = self.organize_folders_checkbox.isChecked()
        # Save the new metadata option
        current_text = self.metadata_combo.currentText()
        self.settings['metadata_option'] = self.metadata_options.get(current_text, "none")
        Settings.save(self.settings)
    
    def init_worker(self):
        """Initialize the download worker thread"""
        self.worker = DownloadWorker(self.download_queue)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.download_complete.connect(self.download_finished)
        self.worker.download_error.connect(self.download_failed)
        self.worker.download_cancelled.connect(self.download_cancelled)
        self.worker.status_update.connect(self.update_status)
        self.worker.playlist_detected.connect(self.handle_playlist_detected)
        self.worker.start()
    
    def init_tray(self):
        """Initialize system tray icon and menu"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
        
        # Create tray menu
        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.quit)
        
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        # Connect tray activation
        self.tray_icon.activated.connect(self.tray_activated)
    
    def tray_activated(self, reason):
        """Handle system tray icon activation"""
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
                self.activateWindow()
    
    def get_current_save_path(self):
        """
        Get the current save path based on settings.
        
        Returns:
            str: Current save path
        """
        if self.settings['use_custom_location']:
            return self.settings['custom_location']
        else:
            return str(Path.home() / 'Downloads' / 'Media')
    
    def add_download(self, data):
        """
        Add a new download to the queue.
        
        Args:
            data: Dictionary containing download information
        """
        download_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        # Determine title based on download type
        title = data.get('title', 'Unknown')
        if data['type'] == 'image':
            # Extract filename for images
            title = os.path.basename(urlparse(data['url']).path) or 'Image'
        
        # Get thumbnail URL
        thumbnail_url = data.get('thumbnail')
        print(f"[DEBUG] Received download with thumbnail: {thumbnail_url}")
        
        # Create download item widget
        item_widget = DownloadItem(download_id, title, data['url'], thumbnail_url)
        
        # Connect cancel button
        item_widget.cancel_btn.clicked.connect(lambda: self.cancel_download(download_id))
        
        # Create container widget with download item and divider
        container_widget = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # Add the download item
        container_layout.addWidget(item_widget)
        
        # Add adaptive system-aware divider
        divider = self._create_adaptive_divider()
        container_layout.addWidget(divider)
        
        container_widget.setLayout(container_layout)
        
        # Create list item with proper height
        list_item = QListWidgetItem()
        list_item.setSizeHint(container_widget.minimumSizeHint())
        
        # Add to list (insert at top)
        self.download_list.insertItem(0, list_item)
        self.download_list.setItemWidget(list_item, container_widget)
        
        # Store reference for later access
        self.download_items[download_id] = {
            'widget': item_widget,
            'item': list_item,
            'data': data
        }
        
        # Add to download queue with current settings
        download_queue_data = {
            'id': download_id,
            'url': data['url'],
            'type': data.get('type', 'video'),
            'referrer': data.get('pageUrl', data.get('source')),
            'quality': 'best',  # Always best quality
            'encode_vp9': self.settings.get('encode_vp9', True),
            'keep_original': self.settings.get('keep_original', False),
            'save_path': self.get_current_save_path(),
            'organize_by_platform': self.settings.get('organize_by_platform', True),
            'metadata_option': self.settings.get('metadata_option', 'none'),
            'detectedVideos': data.get('detectedVideos'),
            'skip_playlist_detection': data.get('skip_playlist_detection', False),
            'playlist_index': data.get('playlist_index')
        }
        
        print(f"[DEBUG] About to put download in queue: {download_id}")
        print(f"[DEBUG] Queue data: {download_queue_data}")
        self.download_queue.put(download_queue_data)
        print(f"[DEBUG] Download added to queue: {download_id}")
        
        # Update UI status
        item_widget.status_label.setText("Starting...")
        item_widget.status_label.setStyleSheet("color: #3498db;")
        
        # Show system notification
        media_type = data.get('type', 'video').capitalize()
        self.tray_icon.showMessage(
            f"{media_type} Download Started",
            f"Downloading: {title}",
            QSystemTrayIcon.Information,
            2000
        )
        
        # Update status label
        self.status_label.setText(f"Active downloads: {self.count_active()}")
    
    def handle_video_list(self, data):
        """
        Handle a list of videos from page scraping.
        
        Args:
            data: Dictionary containing video list and page metadata
        """
        print(f"[DEBUG] handle_video_list called with: {data}")
        print(f"[DEBUG] handle_video_list called with {len(data.get('videos', []))} videos")
        
        try:
            # Show video selector dialog
            dialog = VideoSelectorDialog(
                data['videos'],
                data['pageTitle'],
                data['pageUrl'],
                self
            )
            
            print("[DEBUG] Showing video selector dialog...")
            
            if dialog.exec_():
                selected = dialog.get_selected_videos()
                
                if selected:
                    print(f"[DEBUG] User selected {len(selected)} videos")
                    
                    # Process each selected video
                    for video_info in selected:
                        url = video_info['url']
                        
                        # Check if this should use yt-dlp (video type) or direct download (direct-video type)
                        if (video_info.get('type') == 'hls' or 
                            url.endswith('.m3u8') or
                            'vimeo.com' in url or
                            'youtube.com' in url or 
                            'youtu.be' in url or
                            'instagram.com' in url or
                            'tiktok.com' in url):
                            # Platform video or HLS stream - use yt-dlp
                            download_data = {
                                'url': url,
                                'title': video_info.get('original_title', video_info.get('title', 'Video')),
                                'type': 'video',
                                'pageUrl': data['pageUrl'],
                                'source': data['source'],
                                'thumbnail': video_info.get('thumbnail')
                            }
                            print(f"[DEBUG] Queueing platform video for yt-dlp download: {download_data}")
                            self.add_download(download_data)
                        else:
                            # Check if it's actually a direct file URL
                            is_direct_file = (url.endswith(('.mp4', '.webm', '.mov', '.avi', '.mkv', '.m4v')) or
                                            any(ext in url.lower() for ext in ['.mp4?', '.webm?', '.mov?']))
                            
                            if is_direct_file:
                                # Direct file - use direct download
                                download_data = {
                                    'url': url,
                                    'title': video_info.get('title', 'Video'),
                                    'pageUrl': data['pageUrl'],
                                    'source': data['source'],
                                    'thumbnail': video_info.get('thumbnail')
                                }
                                print(f"[DEBUG] Queueing direct file for download: {download_data}")
                                self.add_direct_video_download(download_data)
                            else:
                                # Unknown format - default to yt-dlp to be safe
                                download_data = {
                                    'url': url,
                                    'title': video_info.get('title', 'Video'),
                                    'type': 'video',
                                    'pageUrl': data['pageUrl'],
                                    'source': data['source'],
                                    'thumbnail': video_info.get('thumbnail')
                                }
                                print(f"[DEBUG] Queueing unknown format for yt-dlp download (safe fallback): {download_data}")
                                self.add_download(download_data)
                    
                    # Show batch notification
                    self.tray_icon.showMessage(
                        "Video Downloads Started",
                        f"Downloading {len(selected)} videos from {data['pageTitle']}",
                        QSystemTrayIcon.Information,
                        2000
                    )
            else:
                print("[DEBUG] User cancelled video selection")
                
        except Exception as e:
            print(f"[ERROR] Failed to show video dialog: {e}")
            import traceback
            traceback.print_exc()
    
    def handle_playlist_detected(self, download_id, playlist_data):
        """
        Handle playlist detected by yt-dlp during download.
        
        Args:
            download_id: ID of the original download that detected a playlist
            playlist_data: Dictionary containing playlist videos and metadata
        """
        print(f"[DEBUG] handle_playlist_detected called for download {download_id}")
        print(f"[DEBUG] Playlist data: {len(playlist_data.get('videos', []))} videos")
        
        try:
            # Remove the original download item since it will be replaced with selected videos
            if download_id in self.download_items:
                original_item = self.download_items[download_id]
                self.download_list.takeItem(self.download_list.row(original_item['item']))
                del self.download_items[download_id]
            
            # Show video selector dialog (same as video-list handling)
            from ui.components.video_selector import VideoSelectorDialog
            dialog = VideoSelectorDialog(
                playlist_data['videos'],
                playlist_data['pageTitle'],
                playlist_data['pageUrl'],
                self
            )
            
            print("[DEBUG] Showing playlist video selector dialog...")
            
            if dialog.exec_():
                selected = dialog.get_selected_videos()
                
                if selected:
                    print(f"[DEBUG] User selected {len(selected)} videos from playlist")
                    
                    # Process each selected video (same logic as handle_video_list)
                    for video_info in selected:
                        print(f"[DEBUG] Selected video keys: {list(video_info.keys())}")
                        print(f"[DEBUG] Selected video playlist_index: {video_info.get('playlist_index')}")
                        url = video_info['url']
                        
                        # Check if this should use yt-dlp (video type) or direct download (direct-video type)
                        if ('vimeo.com' in url or
                            'youtube.com' in url or 
                            'youtu.be' in url or
                            'instagram.com' in url or
                            'tiktok.com' in url or
                            video_info.get('type') == 'hls' or 
                            url.endswith('.m3u8')):
                            # Platform video or HLS stream - use yt-dlp
                            download_data = {
                                'url': url,
                                'title': video_info.get('original_title', video_info.get('title', 'Video')),
                                'type': 'video',
                                'pageUrl': playlist_data['pageUrl'],
                                'source': playlist_data['source'],
                                'thumbnail': video_info.get('thumbnail'),
                                'skip_playlist_detection': True,
                                'playlist_index': video_info.get('playlist_index')
                            }
                            print(f"[DEBUG] Queueing from playlist: {download_data}")
                            print(f"[DEBUG] video_info.get('playlist_index') = {video_info.get('playlist_index')}")
                            self.add_download(download_data)
                        else:
                            # Check if it's actually a direct file URL
                            is_direct_file = (url.endswith(('.mp4', '.webm', '.mov', '.avi', '.mkv', '.m4v')) or
                                            any(ext in url.lower() for ext in ['.mp4?', '.webm?', '.mov?']))
                            
                            if is_direct_file:
                                # Direct file - use direct download
                                download_data = {
                                    'url': url,
                                    'title': video_info.get('title', 'Video'),
                                    'pageUrl': playlist_data['pageUrl'],
                                    'source': playlist_data['source'],
                                    'thumbnail': video_info.get('thumbnail')
                                }
                                print(f"[DEBUG] Queueing from playlist: {download_data}")
                                self.add_direct_video_download(download_data)
                            else:
                                # Unknown format - default to yt-dlp to be safe
                                download_data = {
                                    'url': url,
                                    'title': video_info.get('title', 'Video'),
                                    'type': 'video',
                                    'pageUrl': playlist_data['pageUrl'],
                                    'source': playlist_data['source'],
                                    'thumbnail': video_info.get('thumbnail'),
                                    'skip_playlist_detection': True,
                                    'playlist_index': video_info.get('playlist_index')
                                }
                                print(f"[DEBUG] Queueing from playlist: {download_data}")
                                self.add_download(download_data)
                    
                    # Show batch notification
                    self.tray_icon.showMessage(
                        "Playlist Downloads Started",
                        f"Downloading {len(selected)} videos from playlist",
                        QSystemTrayIcon.Information,
                        2000
                    )
                else:
                    print("[DEBUG] No videos selected from playlist")
            else:
                print("[DEBUG] User cancelled playlist video selection")
                
        except Exception as e:
            print(f"[ERROR] Failed to show playlist dialog: {e}")
            import traceback
            traceback.print_exc()
    
    def add_direct_video_download(self, data):
        """
        Add a direct video download (MP4 from webpage).
        
        Args:
            data: Dictionary containing direct video download information
        """
        download_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        # Create download item
        title = data.get('title', 'Video')
        thumbnail_url = data.get('thumbnail')
        
        item_widget = DownloadItem(download_id, title, data['url'], thumbnail_url)
        
        # Connect cancel button
        item_widget.cancel_btn.clicked.connect(lambda: self.cancel_download(download_id))
        
        # Create container widget with download item and divider
        container_widget = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # Add the download item
        container_layout.addWidget(item_widget)
        
        # Add adaptive system-aware divider
        divider = self._create_adaptive_divider()
        container_layout.addWidget(divider)
        
        container_widget.setLayout(container_layout)
        
        # Create and add list item
        list_item = QListWidgetItem()
        list_item.setSizeHint(container_widget.minimumSizeHint())
        
        self.download_list.insertItem(0, list_item)
        self.download_list.setItemWidget(list_item, container_widget)
        
        # Store reference
        self.download_items[download_id] = {
            'widget': item_widget,
            'item': list_item,
            'data': data
        }
        
        # Add to queue as direct video download
        download_queue_data = {
            'id': download_id,
            'url': data['url'],
            'type': 'direct-video',
            'title': data.get('title', 'video'),
            'referrer': data.get('pageUrl'),
            'save_path': self.get_current_save_path(),
            'organize_by_platform': self.settings.get('organize_by_platform', True),
            'encode_vp9': self.settings.get('encode_vp9', True),
            'keep_original': self.settings.get('keep_original', False),
            'metadata_option': self.settings.get('metadata_option', 'none')
        }
        
        print(f"[DEBUG] About to put direct video download in queue: {download_id}")
        print(f"[DEBUG] Direct video queue data: {download_queue_data}")
        self.download_queue.put(download_queue_data)
        print(f"[DEBUG] Direct video download added to queue: {download_id}")
        
        # Update UI status
        item_widget.status_label.setText("Starting...")
        item_widget.status_label.setStyleSheet("color: #3498db;")
        
        self.status_label.setText(f"Active downloads: {self.count_active()}")
    
    def cancel_download(self, download_id):
        """Cancel a download"""
        self.worker.cancel_download(download_id)
        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            widget.status_label.setText("Cancelling...")
            widget.status_label.setStyleSheet("color: #e74c3c;")
            widget.cancel_btn.setEnabled(False)
    
    def update_progress(self, download_id, percent, status):
        """Update download progress"""
        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            widget.progress_bar.setValue(percent)
            widget.status_label.setText(status)
    
    def update_status(self, download_id, status):
        """Update download status"""
        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            
            if status.startswith('thumbnail:'):
                # Extract and load thumbnail URL
                thumbnail_url = status.replace('thumbnail:', '')
                widget.load_thumbnail(thumbnail_url)
            elif status == 'downloading':
                widget.set_downloading()
                widget.status_label.setText("Downloading...")
                widget.status_label.setStyleSheet("color: #3498db;")
            elif status == 'encoding':
                widget.status_label.setText("Encoding to H.264...")
                widget.status_label.setStyleSheet("color: #9b59b6;")
                widget.progress_bar.setValue(0)  # Reset for encoding progress
    
    def download_finished(self, download_id, path):
        """Handle download completion"""
        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            widget.progress_bar.setValue(100)
            
            # Handle multi-file downloads
            if "|MULTI|" in path:
                actual_path, _, file_count = path.partition("|MULTI|")
                widget.status_label.setText(f"Complete - {file_count}")
                widget.status_label.setStyleSheet("color: #27ae60;")
                
                # Create folder reveal button
                folder_path = os.path.dirname(actual_path)
                reveal_btn = self._create_reveal_button("Show Folder", 
                                                       lambda: self.reveal_in_finder(folder_path, is_folder=True))
            else:
                widget.status_label.setText("Complete")
                widget.status_label.setStyleSheet("color: #27ae60;")
                
                # Create file reveal button
                reveal_btn = self._create_reveal_button("Show in Finder", 
                                                       lambda: self.reveal_in_finder(path))
            
            # Add reveal button to widget
            widget.layout().addWidget(reveal_btn)
            widget.set_complete()
            
            # Show completion notification
            self.tray_icon.showMessage(
                "Download Complete",
                f"Saved: {os.path.basename(path.split('|')[0])}",
                QSystemTrayIcon.Information,
                2000
            )
        
        self.status_label.setText(f"Active downloads: {self.count_active()}")
    
    def _create_reveal_button(self, text, callback):
        """Create a styled reveal button"""
        reveal_btn = QPushButton(text)
        reveal_btn.setStyleSheet("""
            QPushButton {
                background: #3498db;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        reveal_btn.clicked.connect(callback)
        return reveal_btn
    
    def reveal_in_finder(self, path, is_folder=False):
        """
        Open file location in system file manager.
        
        Args:
            path: File or folder path to reveal
            is_folder: Whether the path is a folder (affects behavior on some platforms)
        """
        try:
            if sys.platform == "darwin":  # macOS
                if is_folder:
                    subprocess.run(["open", path])
                else:
                    subprocess.run(["open", "-R", path])
            elif sys.platform == "win32":  # Windows
                if is_folder:
                    subprocess.run(["explorer", path])
                else:
                    subprocess.run(["explorer", "/select,", path])
            else:  # Linux
                target_path = path if is_folder else os.path.dirname(path)
                subprocess.run(["xdg-open", target_path])
        except Exception as e:
            print(f"Error revealing file: {e}")
    
    def download_failed(self, download_id, error):
        """Handle download failure"""
        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            widget.progress_bar.setValue(0)
            
            # Create short error for display (first 50 chars)
            short_error = error[:50] + "..." if len(error) > 50 else error
            
            # Use the new set_error method to store full error details
            widget.set_error(short_error, error)
        
        self.status_label.setText(f"Active downloads: {self.count_active()}")
    
    def download_cancelled(self, download_id):
        """Handle download cancellation"""
        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            widget.progress_bar.setValue(0)
            widget.status_label.setText("Cancelled")
            widget.status_label.setStyleSheet("color: #6c757d;")
            widget.cancel_btn.setEnabled(False)
            
            # Show cancellation notification
            self.tray_icon.showMessage(
                "Download Cancelled",
                "Download was cancelled and files cleaned up",
                QSystemTrayIcon.Information,
                2000
            )
        
        self.status_label.setText(f"Active downloads: {self.count_active()}")
    
    def clear_completed(self):
        """Clear completed and failed downloads from the list"""
        to_remove = []
        for download_id, item_data in self.download_items.items():
            status = item_data['widget'].status_label.text()
            if status.startswith("Complete") or status.startswith("Failed"):
                to_remove.append(download_id)
        
        # Remove items from UI and storage
        for download_id in to_remove:
            item = self.download_items[download_id]['item']
            self.download_list.takeItem(self.download_list.row(item))
            del self.download_items[download_id]
    
    def count_active(self):
        """
        Count active downloads (not complete, failed, or cancelled).
        
        Returns:
            int: Number of active downloads
        """
        count = 0
        for item_data in self.download_items.values():
            status = item_data['widget'].status_label.text()
            if not (status.startswith("Complete") or status.startswith("Failed") or status.startswith("Cancel")):
                count += 1
        return count
    
    def restore_window_geometry(self):
        """Restore window position and size from settings with multi-monitor support"""
        geometry = self.settings.get('window_geometry', {})
        
        # Get desktop widget for multi-monitor support
        desktop = QApplication.desktop()
        
        # Set window size
        width = geometry.get('width', 500)
        height = geometry.get('height', 600)
        
        # Ensure minimum and maximum sizes (use virtual desktop for multi-monitor)
        virtual_geometry = desktop.geometry()  # Combined geometry of all monitors
        width = max(400, min(width, virtual_geometry.width() - 100))
        height = max(300, min(height, virtual_geometry.height() - 100))
        
        # Set window position
        x = geometry.get('x')
        y = geometry.get('y')
        
        if x is None or y is None:
            # Default position: top-right corner of primary monitor
            primary_screen = desktop.screenGeometry(desktop.primaryScreen())
            x = primary_screen.x() + primary_screen.width() - width - 50
            y = primary_screen.y() + 50
        else:
            # Validate position across all monitors
            target_point = QRect(x, y, width, height)
            screen_containing_window = self._find_best_screen_for_window(target_point)
            
            if screen_containing_window is None:
                # Window is completely off-screen, move to primary monitor
                primary_screen = desktop.screenGeometry(desktop.primaryScreen())
                x = primary_screen.x() + primary_screen.width() - width - 50
                y = primary_screen.y() + 50
                print(f"[DEBUG] Window was off-screen, moved to primary monitor")
            else:
                # Ensure window fits within the screen that contains it
                screen_rect = desktop.screenGeometry(screen_containing_window)
                
                # Adjust if window extends beyond screen boundaries
                if x + width > screen_rect.right():
                    x = screen_rect.right() - width
                if y + height > screen_rect.bottom():
                    y = screen_rect.bottom() - height
                if x < screen_rect.left():
                    x = screen_rect.left()
                if y < screen_rect.top():
                    y = screen_rect.top()
        
        # Apply geometry
        self.setGeometry(x, y, width, height)
        
        # Get screen info for debug
        screen_num = desktop.screenNumber(QRect(x, y, width, height).center())
        screen_geometry = desktop.screenGeometry(screen_num)
        print(f"[DEBUG] Restored window geometry: {x}, {y}, {width}x{height}")
        print(f"[DEBUG] Window on screen {screen_num}: {screen_geometry.x()},{screen_geometry.y()} {screen_geometry.width()}x{screen_geometry.height()}")
    
    def _find_best_screen_for_window(self, window_rect):
        """Find which screen contains the largest portion of the window"""
        desktop = QApplication.desktop()
        best_screen = None
        max_intersection_area = 0
        
        # Check each screen
        for screen_num in range(desktop.screenCount()):
            screen_geometry = desktop.screenGeometry(screen_num)
            
            # Calculate intersection area
            intersection = window_rect.intersected(screen_geometry)
            intersection_area = intersection.width() * intersection.height()
            
            if intersection_area > max_intersection_area:
                max_intersection_area = intersection_area
                best_screen = screen_num
        
        # Only return a screen if there's meaningful intersection (at least 25% of window)
        window_area = window_rect.width() * window_rect.height()
        if max_intersection_area >= window_area * 0.25:
            return best_screen
        
        return None
    
    def save_window_geometry(self):
        """Save current window position and size to settings with multi-monitor info"""
        geometry = self.geometry()
        desktop = QApplication.desktop()
        
        # Get current screen information
        screen_num = desktop.screenNumber(geometry.center())
        screen_geometry = desktop.screenGeometry(screen_num)
        
        # Update settings with current window geometry
        self.settings['window_geometry'] = {
            'x': geometry.x(),
            'y': geometry.y(),
            'width': geometry.width(),
            'height': geometry.height()
        }
        
        # Save settings to file
        Settings.save(self.settings)
        
        print(f"[DEBUG] Saved window geometry: {geometry.x()}, {geometry.y()}, {geometry.width()}x{geometry.height()}")
        print(f"[DEBUG] Window on screen {screen_num}: {screen_geometry.x()},{screen_geometry.y()} {screen_geometry.width()}x{screen_geometry.height()}")
        
        # Additional debug info about multi-monitor setup
        if desktop.screenCount() > 1:
            print(f"[DEBUG] Multi-monitor setup detected: {desktop.screenCount()} screens")
            for i in range(desktop.screenCount()):
                screen_rect = desktop.screenGeometry(i)
                is_primary = " (PRIMARY)" if i == desktop.primaryScreen() else ""
                print(f"[DEBUG] Screen {i}{is_primary}: {screen_rect.x()},{screen_rect.y()} {screen_rect.width()}x{screen_rect.height()}")
    
    def moveEvent(self, event):
        """Handle window move events to save position"""
        super().moveEvent(event)
        # Save position when window is moved (with slight delay to avoid excessive saves)
        if hasattr(self, '_move_timer'):
            self._move_timer.stop()
        
        from PyQt5.QtCore import QTimer
        self._move_timer = QTimer()
        self._move_timer.setSingleShot(True)
        self._move_timer.timeout.connect(self.save_window_geometry)
        self._move_timer.start(500)  # Save after 500ms of no movement
    
    def resizeEvent(self, event):
        """Handle window resize events to save size"""
        super().resizeEvent(event)
        # Save size when window is resized (with slight delay to avoid excessive saves)
        if hasattr(self, '_resize_timer'):
            self._resize_timer.stop()
        
        from PyQt5.QtCore import QTimer
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self.save_window_geometry)
        self._resize_timer.start(500)  # Save after 500ms of no resizing
    
    def closeEvent(self, event):
        """Handle window close event (minimize to tray instead of quit)"""
        # Save window position and size before hiding
        self.save_window_geometry()
        
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Media Downloader",
            "Application minimized to tray",
            QSystemTrayIcon.Information,
            1000
        )