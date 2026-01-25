"""
VideoSelectorDialog component for Media Downloader App
Dialog for selecting which videos to download from a scraped page
"""

import re

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QListWidget, QListWidgetItem, QWidget, QCheckBox,
                           QPushButton, QDialogButtonBox)
from PyQt5.QtCore import Qt, QTimer


class VideoSelectorDialog(QDialog):
    """
    Dialog for selecting which videos to download from a page.
    
    Features:
    - Clean display of video titles, URLs, and types
    - Checkbox selection for each video
    - Essential video information (filename, stream type)
    - Select all/deselect all functionality
    - Returns selected videos with cleaned titles
    - Full URL display with text selection support
    """
    
    def __init__(self, videos, page_title, page_url, parent=None):
        """
        Initialize video selector dialog.
        
        Args:
            videos: List of video dictionaries with metadata
            page_title: Title of the page containing videos
            page_url: URL of the page containing videos
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self.videos = videos
        self.page_title = page_title
        self.page_url = page_url
        self.selected_videos = []
        self.checkboxes = []
        
        self.setWindowTitle(f"Select Videos from {page_title}")
        self.setModal(True)
        self.resize(700, 500)
        
        layout = QVBoxLayout()
        
        # Header section
        header = QLabel(f"<b>Found {len(videos)} videos on page</b>")
        header.setStyleSheet("color: #2c3e50;")
        layout.addWidget(header)
        
        # Subtitle with page URL
        url_label = QLabel(f"<small>{page_url}</small>")
        url_label.setWordWrap(True)
        url_label.setStyleSheet("color: #666;")
        layout.addWidget(url_label)
        
        # Video list widget
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        
        # Store references for easy access
        self.checkboxes = []
        self.item_widgets = []
        
        # Create video list items
        for i, video in enumerate(videos):
            self._create_video_item(i, video)
        
        # Force immediate visual update of all checkboxes
        self.list_widget.update()
        for checkbox in self.checkboxes:
            checkbox.update()
        
        layout.addWidget(self.list_widget)
        
        # Control buttons section
        self._create_control_buttons(layout)
        
        # Dialog buttons (OK/Cancel)
        self._create_dialog_buttons(layout)
        
        self.setLayout(layout)
        
        # Checkboxes are now set to checked during creation, no delay needed
    
    def _create_video_item(self, index, video):
        """
        Create a single video item widget.
        
        Args:
            index: Video index in the list
            video: Video metadata dictionary
        """
        # Create the item widget container
        item_widget = QWidget()
        item_layout = QHBoxLayout()
        item_layout.setContentsMargins(5, 5, 5, 5)
        
        # Checkbox for selection (initially checked by default)
        checkbox = QCheckBox()
        checkbox.setChecked(True)  # Check immediately during creation
        
        # Ensure checkbox styling doesn't interfere with visual state
        checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 5px;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border: 1px solid #2980b9;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                background-color: white;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
            }
        """)
        
        self.checkboxes.append(checkbox)
        
        # Video information section (expanded to full width without thumbnails)
        info_layout = QVBoxLayout()
        
        # Video title (full width, no truncation)
        title = video.get('title', f'Video {index+1}')
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setStyleSheet("color: #2c3e50; font-size: 14px; padding: 2px 0px;")
        title_label.setWordWrap(True)  # Allow title to wrap to multiple lines
        info_layout.addWidget(title_label)
        
        # Video details (type, filename, etc.) - enhanced formatting
        details = self._format_video_details(video)
        if details:
            details_label = QLabel(" • ".join(details))
            details_label.setStyleSheet("color: #7f8c8d; font-size: 12px; padding: 1px 0px;")
            details_label.setWordWrap(True)
            info_layout.addWidget(details_label)
        
        # Video URL (full URL with word wrap, no truncation)
        url = video['url']
        url_label = QLabel(url)
        url_label.setStyleSheet("color: #95a5a6; font-size: 11px; padding: 1px 0px;")
        url_label.setWordWrap(True)  # Allow URL to wrap naturally
        url_label.setTextInteractionFlags(url_label.textInteractionFlags() | Qt.TextSelectableByMouse)  # Make URL selectable
        info_layout.addWidget(url_label)
        
        # Assemble item layout - checkbox on left, full-width text content on right
        item_layout.addWidget(checkbox)
        item_layout.addLayout(info_layout, 1)  # Give info_layout stretch factor of 1 to use full width
        
        item_widget.setLayout(item_layout)
        item_widget.setStyleSheet("""
            QWidget {
                background: #ffffff;
                border: 1px solid #ecf0f1;
                border-radius: 4px;
            }
            QWidget:hover {
                background: #f8f9fa;
                border: 1px solid #bdc3c7;
            }
        """)
        
        # Add to list widget
        list_item = QListWidgetItem()
        list_item.setSizeHint(item_widget.minimumSizeHint())
        self.list_widget.addItem(list_item)
        self.list_widget.setItemWidget(list_item, item_widget)
        self.item_widgets.append(item_widget)
    
    def _format_video_details(self, video):
        """
        Format video details for display with essential available information.
        
        Args:
            video: Video metadata dictionary
            
        Returns:
            List of detail strings
        """
        details = []
        
        # Original filename if available
        if video.get('originalFilename'):
            details.append(f"File: {video['originalFilename']}")
        
        # Video type description
        video_type = video.get('type', 'unknown')
        if video_type == 'hls':
            details.append("HLS Stream")
        elif video_type == 'direct':
            details.append("Direct MP4")
        elif video_type == 'data-attribute':
            details.append("Embedded")
        
        return details
    
    def _create_control_buttons(self, layout):
        """
        Create select all/deselect all buttons.
        
        Args:
            layout: Parent layout to add buttons to
        """
        button_row = QHBoxLayout()
        
        # Select all button
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        select_all_btn.setStyleSheet("""
            QPushButton {
                background: #3498db;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        
        # Deselect all button
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self.deselect_all)
        deselect_all_btn.setStyleSheet("""
            QPushButton {
                background: #95a5a6;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #7f8c8d;
            }
        """)
        
        button_row.addWidget(select_all_btn)
        button_row.addWidget(deselect_all_btn)
        button_row.addStretch()
        
        layout.addLayout(button_row)
    
    def _create_dialog_buttons(self, layout):
        """
        Create OK/Cancel dialog buttons.
        
        Args:
            layout: Parent layout to add buttons to
        """
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        # Change OK button text
        buttons.button(QDialogButtonBox.Ok).setText("Download Selected")
        
        layout.addWidget(buttons)
    
    def check_all_initially(self):
        """Check all checkboxes immediately (legacy method, now handled during creation)"""
        # This method is now redundant since checkboxes are created as checked
        # Keeping for compatibility but functionality moved to _create_video_item
        for checkbox in self.checkboxes:
            if not checkbox.isChecked():
                checkbox.setChecked(True)
        # Force immediate visual update
        self.list_widget.repaint()
    
    # Removed load_thumbnail method - no longer needed without thumbnail display
    
    def select_all(self):
        """Select all videos"""
        for checkbox in self.checkboxes:
            checkbox.setChecked(True)
    
    def deselect_all(self):
        """Deselect all videos"""
        for checkbox in self.checkboxes:
            checkbox.setChecked(False)
    
    def get_selected_videos(self):
        """
        Return list of selected video URLs and titles.
        
        Returns:
            List of dictionaries containing selected video metadata
        """
        selected = []
        for i, checkbox in enumerate(self.checkboxes):
            if checkbox.isChecked():
                video = self.videos[i]
                
                # Get and clean title for filename usage
                title = video.get('title', f'Video_{i+1}')
                clean_title = re.sub(r'[^\w\s-]', '', title)
                clean_title = re.sub(r'[-\s]+', '_', clean_title)
                
                # Use original filename if title is generic
                if clean_title.startswith('Video_') and video.get('originalFilename'):
                    clean_title = video['originalFilename'].replace('.mp4', '').replace('.m4v', '')
                
                selected.append({
                    'url': video['url'],
                    'title': clean_title,
                    'type': video.get('type', 'direct'),
                    'original_title': title,
                    'thumbnail': video.get('thumbnail'),
                    'playlist_index': video.get('playlist_index')
                })
        
        return selected