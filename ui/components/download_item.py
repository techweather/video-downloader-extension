"""
DownloadItem UI component for Media Downloader App
Individual download item widget with thumbnail loading and progress display
"""

import requests
from threading import Thread

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QLabel, QProgressBar, QApplication)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap


class DownloadItem(QWidget):
    """
    UI widget representing a single download item with thumbnail, progress bar, and controls.
    """
    
    def __init__(self, download_id, title, url, thumbnail_url=None):
        """
        Initialize a download item widget.
        
        Args:
            download_id: Unique identifier for the download
            title: Display title for the download
            url: URL being downloaded
            thumbnail_url: Optional URL for thumbnail image
        """
        super().__init__()
        self.download_id = download_id
        self.full_error_message = None  # Store detailed error information
        
        main_layout = QHBoxLayout()
        main_layout.setSpacing(10)
        
        # Thumbnail container with fixed size
        thumbnail_container = QWidget()
        thumbnail_container.setFixedSize(80, 60)
        thumbnail_container.setStyleSheet("""
            QWidget {
                background: #f0f0f0;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        
        # Thumbnail label inside container
        self.thumbnail_label = QLabel(thumbnail_container)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        
        # Set default thumbnail based on type
        self.set_default_thumbnail()
        
        # Load actual thumbnail if URL provided
        if thumbnail_url:
            self.load_thumbnail(thumbnail_url)
        
        # Content layout
        content_layout = QVBoxLayout()
        content_layout.setSpacing(5)
        
        # Title and URL labels
        title_label = QLabel(f"<b>{title[:50]}...</b>" if len(title) > 50 else f"<b>{title}</b>")
        url_label = QLabel(f"<small>{url[:60]}...</small>" if len(url) > 60 else f"<small>{url}</small>")
        url_label.setStyleSheet("color: #666;")
        url_label.setWordWrap(True)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setMinimumHeight(20)
        
        # Status and controls row
        controls_layout = QHBoxLayout()
        
        # Status label
        self.status_label = QLabel("Queued")
        self.status_label.setStyleSheet("color: #888;")
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: #e74c3c;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 3px;
                font-size: 11px;
                min-height: 20px;
            }
            QPushButton:hover {
                background: #c0392b;
            }
        """)
        self.cancel_btn.hide()  # Initially hidden
        
        # Copy Error button (for failed downloads)
        self.copy_error_btn = QPushButton("Copy Error")
        self.copy_error_btn.setStyleSheet("""
            QPushButton {
                background: #f39c12;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 3px;
                font-size: 11px;
                min-height: 20px;
            }
            QPushButton:hover {
                background: #e67e22;
            }
        """)
        self.copy_error_btn.hide()  # Initially hidden
        self.copy_error_btn.clicked.connect(self.copy_error_to_clipboard)
        
        # Assemble controls layout
        controls_layout.addWidget(self.status_label)
        controls_layout.addStretch()
        controls_layout.addWidget(self.copy_error_btn)
        controls_layout.addWidget(self.cancel_btn)
        
        # Assemble content layout
        content_layout.addWidget(title_label)
        content_layout.addWidget(url_label)
        content_layout.addWidget(self.progress_bar)
        content_layout.addLayout(controls_layout)
        
        # Assemble main layout
        main_layout.addWidget(thumbnail_container)
        main_layout.addLayout(content_layout)
        
        self.setLayout(main_layout)
        self.setMinimumHeight(100)  # Ensure minimum height
    
    def set_default_thumbnail(self):
        """Set a default icon as thumbnail"""
        self.thumbnail_label.setText("🎬")
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setStyleSheet("""
            QLabel {
                background: #f0f0f0;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 24px;
            }
        """)
    
    def load_thumbnail(self, url):
        """
        Load thumbnail from URL in a separate thread.
        
        Args:
            url: URL of the thumbnail image to load
        """        
        print(f"[DEBUG] Loading thumbnail from: {url}")
        
        def fetch_and_update():
            """Fetch thumbnail data and schedule UI update"""
            try:
                response = requests.get(url, timeout=5)
                print(f"[DEBUG] Thumbnail response status: {response.status_code}")
                
                if response.status_code == 200:
                    # Load image data directly in the worker thread
                    pixmap = QPixmap()
                    success = pixmap.loadFromData(response.content)
                    print(f"[DEBUG] Pixmap loaded: {success}, size: {pixmap.size()}")
                    
                    if success and not pixmap.isNull():
                        # Scale the pixmap to fit thumbnail container
                        scaled_pixmap = pixmap.scaled(80, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        
                        # Store pixmap for UI thread update
                        self.thumbnail_pixmap = scaled_pixmap
                        # Schedule UI update in main thread
                        QTimer.singleShot(0, self.update_thumbnail_ui)
                    else:
                        print("[DEBUG] Pixmap is null or failed to load")
                        
            except Exception as e:
                print(f"[DEBUG] Thumbnail loading error: {e}")
        
        # Start thumbnail loading in background thread
        Thread(target=fetch_and_update, daemon=True).start()
    
    def update_thumbnail_ui(self):
        """Update the thumbnail in the main thread (thread-safe)"""
        if hasattr(self, 'thumbnail_pixmap'):
            # Center the thumbnail in the container
            container_size = self.thumbnail_label.parent().size()
            x = (container_size.width() - self.thumbnail_pixmap.width()) // 2
            y = (container_size.height() - self.thumbnail_pixmap.height()) // 2
            
            # Update thumbnail label
            self.thumbnail_label.resize(self.thumbnail_pixmap.size())
            self.thumbnail_label.move(x, y)
            self.thumbnail_label.setPixmap(self.thumbnail_pixmap)
            print("[DEBUG] Thumbnail UI updated")
    
    def set_downloading(self):
        """Update UI to show download in progress state"""
        self.cancel_btn.show()
    
    def set_complete(self):
        """Update UI to show download complete state"""
        self.cancel_btn.hide()
    
    def set_error(self, short_error, full_error):
        """
        Set error information for this download.
        
        Args:
            short_error: Brief error message for display
            full_error: Detailed error information for clipboard
        """
        self.full_error_message = full_error
        self.status_label.setText(f"Failed: {short_error}")
        self.status_label.setStyleSheet("color: #e74c3c;")
        self.cancel_btn.hide()
        self.copy_error_btn.show()
    
    def copy_error_to_clipboard(self):
        """Copy the full error message to clipboard"""
        if self.full_error_message:
            clipboard = QApplication.clipboard()
            
            # Create detailed error report
            error_report = f"""Download Error Report
{'='*50}
Download ID: {self.download_id}
Status: Failed
Time: {self._get_current_time()}

Error Details:
{self.full_error_message}

Download Information:
- Title: {self._get_title_from_ui()}
- URL: {self._get_url_from_ui()}

System Information:
- Application: dlwithit
- Error copied at: {self._get_current_time()}
"""
            clipboard.setText(error_report)
            
            # Temporarily change button text to show success
            original_text = self.copy_error_btn.text()
            self.copy_error_btn.setText("Copied!")
            self.copy_error_btn.setStyleSheet("""
                QPushButton {
                    background: #27ae60;
                    color: white;
                    border: none;
                    padding: 4px 8px;
                    border-radius: 3px;
                    font-size: 11px;
                    min-height: 20px;
                }
            """)
            
            # Reset button after 2 seconds
            QTimer.singleShot(2000, lambda: self._reset_copy_button(original_text))
    
    def _reset_copy_button(self, original_text):
        """Reset the copy button to original state"""
        self.copy_error_btn.setText(original_text)
        self.copy_error_btn.setStyleSheet("""
            QPushButton {
                background: #f39c12;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 3px;
                font-size: 11px;
                min-height: 20px;
            }
            QPushButton:hover {
                background: #e67e22;
            }
        """)
    
    def _get_current_time(self):
        """Get current timestamp as string"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _get_title_from_ui(self):
        """Extract title from UI elements"""
        try:
            # Get the first QLabel (title label) from content layout
            content_layout = self.layout().itemAt(1).layout()
            title_label = content_layout.itemAt(0).widget()
            if isinstance(title_label, QLabel):
                # Remove HTML formatting
                text = title_label.text()
                return text.replace('<b>', '').replace('</b>', '')
            return "Unknown"
        except:
            return "Unknown"
    
    def _get_url_from_ui(self):
        """Extract URL from UI elements"""
        try:
            # Get the second QLabel (URL label) from content layout
            content_layout = self.layout().itemAt(1).layout()
            url_label = content_layout.itemAt(1).widget()
            if isinstance(url_label, QLabel):
                # Remove HTML formatting and truncation
                text = url_label.text()
                return text.replace('<small>', '').replace('</small>', '').replace('...', '')
            return "Unknown"
        except:
            return "Unknown"