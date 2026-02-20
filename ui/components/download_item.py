"""
DownloadItem UI component for Media Downloader App
Individual download item widget with thumbnail loading and progress display
"""

import os
import platform
import subprocess
import sys
import requests
from datetime import datetime
from threading import Thread
from urllib.parse import urlparse

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QProgressBar, QApplication)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap, QPainter, QBrush, QColor


class DownloadItem(QWidget):
    """
    UI widget representing a single download item with thumbnail, progress bar, and controls.
    """

    def __init__(self, download_id, title, url, thumbnail_url=None):
        super().__init__()
        self.download_id = download_id
        self.full_error_message = None

        self.setObjectName("downloadItem")
        self.setAttribute(Qt.WA_StyledBackground, True)  # required for QWidget to paint stylesheet bg
        self._apply_border_style("#404040")

        main_layout = QHBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setAlignment(Qt.AlignTop)

        # Thumbnail label (self-contained, 72x54)
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setObjectName("thumbnail")
        self.thumbnail_label.setAttribute(Qt.WA_StyledBackground, True)
        self.thumbnail_label.setFixedSize(72, 54)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.set_default_thumbnail()

        if thumbnail_url:
            self.load_thumbnail(thumbnail_url)

        # Content layout
        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)
        content_layout.setContentsMargins(0, 2, 0, 0)
        content_layout.setAlignment(Qt.AlignTop)

        self.title_label = QLabel(
            f"<b>{title[:50]}...</b>" if len(title) > 50 else f"<b>{title}</b>"
        )
        self.title_label.setStyleSheet("color: #e0e0e0;")

        domain = urlparse(url).netloc or url[:40]
        self.domain_label = QLabel(domain)
        self.domain_label.setStyleSheet("color: #888; font-size: 11px;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setMinimumHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #252525;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a9eff, stop:1 #5ab0ff);
                border-radius: 2px;
            }
        """)

        self.status_label = QLabel("Queued")
        _sf = self.status_label.font()
        _sf.setPixelSize(12)
        self.status_label.setFont(_sf)
        self.status_label.setStyleSheet("color: #888;")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label.setMaximumWidth(150)

        # Progress bar and status on the same line
        progress_row = QHBoxLayout()
        progress_row.setSpacing(8)
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.status_label)

        content_layout.addWidget(self.title_label)
        content_layout.addWidget(self.domain_label)
        content_layout.addLayout(progress_row)

        # Action widget (fixed width, one button at a time)
        self.action_widget = QWidget()
        self.action_widget.setFixedWidth(130)
        action_layout = QVBoxLayout()
        action_layout.setAlignment(Qt.AlignCenter)
        action_layout.setContentsMargins(6, 0, 6, 0)
        action_layout.setSpacing(4)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(110)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f87171, stop:1 #dc2626);
                color: white;
                border: none;
                padding: 6px 8px;
                border-radius: 5px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ef4444, stop:1 #b91c1c);
            }
        """)
        self.cancel_btn.hide()

        self.copy_error_btn = QPushButton("Copy Error")
        self.copy_error_btn.setFixedWidth(110)
        self.copy_error_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fbbf24, stop:1 #d97706);
                color: white;
                border: none;
                padding: 6px 8px;
                border-radius: 5px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f59e0b, stop:1 #b45309);
            }
        """)
        self.copy_error_btn.hide()
        self.copy_error_btn.clicked.connect(self.copy_error_to_clipboard)

        action_layout.addWidget(self.cancel_btn)
        action_layout.addWidget(self.copy_error_btn)
        self.action_widget.setLayout(action_layout)

        main_layout.addWidget(self.thumbnail_label)
        main_layout.addLayout(content_layout, 1)
        main_layout.addWidget(self.action_widget)

        self.setLayout(main_layout)
        self.setMinimumHeight(80)

    def _apply_border_style(self, border_color):
        """Apply gradient background with specified border color."""
        self.setStyleSheet(f"""
            QWidget#downloadItem {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #363636, stop:1 #2e2e2e);
                border: 1px solid {border_color};
                border-radius: 10px;
            }}
        """)

    def set_default_thumbnail(self):
        """Set a default icon as thumbnail."""
        self.thumbnail_label.setPixmap(QPixmap())
        self.thumbnail_label.setText("🎬")
        self.thumbnail_label.setStyleSheet("""
            QLabel#thumbnail {
                background: #252525;
                border: 1px solid #404040;
                border-radius: 6px;
                font-size: 20px;
            }
        """)

    def load_thumbnail(self, url):
        """Load thumbnail from URL in a separate thread."""
        def fetch_and_update():
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    pixmap = QPixmap()
                    success = pixmap.loadFromData(response.content)
                    if success and not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(
                            72, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation
                        )
                        self.thumbnail_pixmap = scaled_pixmap
                        QTimer.singleShot(0, self.update_thumbnail_ui)
            except Exception:
                pass

        Thread(target=fetch_and_update, daemon=True).start()

    def update_thumbnail_ui(self):
        """Update the thumbnail in the main thread (thread-safe)."""
        if hasattr(self, 'thumbnail_pixmap'):
            src = self.thumbnail_pixmap

            # Composite image onto dark background canvas, then clip to rounded rect
            canvas = QPixmap(72, 54)
            canvas.fill(QColor("#252525"))
            scaled = src.scaled(72, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p = QPainter(canvas)
            p.drawPixmap((72 - scaled.width()) // 2, (54 - scaled.height()) // 2, scaled)
            p.end()

            rounded = QPixmap(72, 54)
            rounded.fill(Qt.transparent)
            p = QPainter(rounded)
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QBrush(canvas))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(0, 0, 72, 54, 5, 5)
            p.end()

            self.thumbnail_label.setText("")
            self.thumbnail_label.setStyleSheet("QLabel#thumbnail { background: transparent; border: none; }")
            self.thumbnail_label.setPixmap(rounded)

    def set_downloading(self):
        """Update UI to show download in progress state."""
        self.cancel_btn.show()
        self._apply_border_style("rgba(74,158,255,0.31)")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #252525;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a9eff, stop:1 #5ab0ff);
                border-radius: 2px;
            }
        """)

    def set_complete(self):
        """Update UI to show download complete state."""
        self.cancel_btn.hide()
        self._apply_border_style("rgba(74,222,128,0.31)")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #252525;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #22c55e, stop:1 #4ade80);
                border-radius: 2px;
            }
        """)

    def set_encoding(self):
        """Update progress bar to purple for encoding state."""
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #252525;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #9333ea, stop:1 #a855f7);
                border-radius: 2px;
            }
        """)

    def set_error(self, short_error, full_error):
        """Set error information for this download."""
        self.full_error_message = full_error
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.status_label.setText(f"Failed: {short_error}")
        self.status_label.setStyleSheet("color: #f87171;")
        self.cancel_btn.hide()
        self.copy_error_btn.show()
        self._apply_border_style("rgba(248,113,113,0.31)")

    def set_reveal(self, path, is_folder=False):
        """Create and add a reveal button to the action widget."""
        if is_folder:
            text = "Open Folder"
        else:
            sys_name = platform.system()
            if sys_name == "Darwin":
                text = "Show in Finder"
            elif sys_name == "Windows":
                text = "Show in Explorer"
            else:
                text = "Open Folder"

        reveal_btn = QPushButton(text)
        reveal_btn.setFixedWidth(110)
        reveal_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5ab0ff, stop:1 #3d8fdb);
                color: white;
                border: none;
                padding: 6px 8px;
                border-radius: 5px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a9ff5, stop:1 #2d7ec4);
            }
        """)

        _path = path
        _is_folder = is_folder

        def reveal():
            try:
                if sys.platform == "darwin":
                    if _is_folder:
                        subprocess.run(["open", _path])
                    else:
                        subprocess.run(["open", "-R", _path])
                elif sys.platform == "win32":
                    if _is_folder:
                        subprocess.run(["explorer", _path])
                    else:
                        subprocess.run(["explorer", "/select,", _path])
                else:
                    target = _path if _is_folder else os.path.dirname(_path)
                    subprocess.run(["xdg-open", target])
            except Exception as e:
                print(f"Error revealing file: {e}")

        reveal_btn.clicked.connect(reveal)
        self.action_widget.layout().addWidget(reveal_btn)

    def copy_error_to_clipboard(self):
        """Copy the full error message to clipboard."""
        if self.full_error_message:
            clipboard = QApplication.clipboard()
            title_text = self.title_label.text().replace('<b>', '').replace('</b>', '')
            error_report = f"""Download Error Report
{'='*50}
Download ID: {self.download_id}
Status: Failed
Time: {self._get_current_time()}

Error Details:
{self.full_error_message}

Download Information:
- Title: {title_text}
- URL: {self.domain_label.text()}

System Information:
- Application: dlwithit
- Error copied at: {self._get_current_time()}
"""
            clipboard.setText(error_report)

            original_text = self.copy_error_btn.text()
            self.copy_error_btn.setText("Copied!")
            self.copy_error_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #34d399, stop:1 #059669);
                    color: white;
                    border: none;
                    padding: 6px 8px;
                    border-radius: 5px;
                    font-size: 11px;
                }
            """)
            QTimer.singleShot(2000, lambda: self._reset_copy_button(original_text))

    def _reset_copy_button(self, original_text):
        """Reset the copy button to original state."""
        self.copy_error_btn.setText(original_text)
        self.copy_error_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fbbf24, stop:1 #d97706);
                color: white;
                border: none;
                padding: 5px 8px;
                border-radius: 5px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f59e0b, stop:1 #b45309);
            }
        """)

    def _get_current_time(self):
        """Get current timestamp as string."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _get_title_from_ui(self):
        """Extract title from UI elements."""
        return self.title_label.text().replace('<b>', '').replace('</b>', '')

    def _get_url_from_ui(self):
        """Extract URL from UI elements."""
        return self.domain_label.text()
