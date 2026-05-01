"""
DownloadItem UI component for Media Downloader App
Individual download item widget with thumbnail loading and progress display
"""

import os
import platform
import subprocess
import sys
import requests
from version import __version__
from datetime import datetime
from threading import Thread
from urllib.parse import urlparse

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QProgressBar, QApplication, QDialog, QPlainTextEdit,
                             QSizePolicy)
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
        self._url = url
        self._extra_action_buttons = []
        self._reencode_btn = None
        self._reencode_filepath = None
        self._reencode_callback = None

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

        self.report_error_btn = QPushButton("Report Error")
        self.report_error_btn.setFixedWidth(110)
        self.report_error_btn.setStyleSheet("""
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
        self.report_error_btn.hide()
        self.report_error_btn.clicked.connect(self.show_error_report_dialog)

        action_layout.addWidget(self.cancel_btn)
        action_layout.addWidget(self.report_error_btn)
        self.action_widget.setLayout(action_layout)

        # Wrap content in a widget with Ignored size policy so it never
        # enforces a minimum width — thumbnail and action_widget get their
        # fixed widths first, content gets whatever remains.
        content_widget = QWidget()
        content_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        content_widget.setMinimumWidth(0)
        content_widget.setLayout(content_layout)

        main_layout.addWidget(self.thumbnail_label)
        main_layout.addWidget(content_widget, 1)
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
        self._error_type = "Conversion Error" if full_error.startswith("Conversion Error") else "Download Error"
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.status_label.setText(f"Failed: {short_error}")
        self.status_label.setStyleSheet("color: #f87171;")
        self.cancel_btn.hide()
        self.report_error_btn.show()
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
        self._extra_action_buttons.append(reveal_btn)

    def clear_extra_action_buttons(self):
        """Remove dynamically-added action buttons (reveal, re-encode) and reset state."""
        for btn in self._extra_action_buttons:
            btn.setParent(None)
            btn.deleteLater()
        self._extra_action_buttons = []
        self._reencode_btn = None
        self._reencode_filepath = None
        self._reencode_callback = None

    def enable_reencode(self, filepath, callback):
        """Show a Re-encode button for this item."""
        self._reencode_filepath = filepath
        self._reencode_callback = callback

        btn = QPushButton("Convert to MP4")
        btn.setFixedWidth(110)
        btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #a48ac0, stop:1 #6f5d8c);
                color: white;
                border: none;
                padding: 6px 8px;
                border-radius: 5px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #9078b0, stop:1 #5c4d77);
            }
        """)
        btn.clicked.connect(self._trigger_reencode)
        self.action_widget.layout().addWidget(btn)
        self._extra_action_buttons.append(btn)
        self._reencode_btn = btn

    def set_reencode_busy(self, busy):
        """Hide/show the Re-encode button without losing state, so it can be restored on cancel."""
        if self._reencode_btn is None:
            return
        if busy:
            self._reencode_btn.hide()
        else:
            self._reencode_btn.show()

    def _trigger_reencode(self):
        if self._reencode_callback and self._reencode_filepath:
            self._reencode_callback(self._reencode_filepath)

    def _clipboard_error_text(self):
        """Format error details as plain text for clipboard."""
        title_text = self.title_label.text().replace('<b>', '').replace('</b>', '')
        return (
            f"Download Error Report\n{'=' * 50}\n"
            f"Download ID: {self.download_id}\n"
            f"Status: Failed\n"
            f"Time: {self._get_current_time()}\n\n"
            f"Error Details:\n{self.full_error_message}\n\n"
            f"Download Information:\n"
            f"- Title: {title_text}\n"
            f"- URL: {self._url}\n\n"
            f"System Information:\n"
            f"- Application: dlwithit {__version__}\n"
            f"- Error copied at: {self._get_current_time()}\n"
        )

    def show_error_report_dialog(self):
        """Open the error report dialog."""
        if not self.full_error_message:
            return
        from core.error_reporter import clean_error_text
        error_type = getattr(self, '_error_type', 'Download Error')
        preview = (
            f"Error Type: {error_type}\n\n"
            f"Error Details:\n{clean_error_text(self.full_error_message)}\n\n"
            f"URL: {self._url}\n"
            f"App Version: {__version__}"
        )
        error_info = {
            'error_type': error_type,
            'error_message': self.full_error_message,
            'url': self._url,
            'clipboard_text': self._clipboard_error_text(),
            'preview_text': preview,
        }
        dialog = ErrorReportDialog(error_info, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self.report_error_btn.setText("Sent!")
            self.report_error_btn.setStyleSheet("""
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
            QTimer.singleShot(2000, self._reset_report_button)

    def _reset_report_button(self):
        """Reset the report button to its default state."""
        self.report_error_btn.setText("Report Error")
        self.report_error_btn.setStyleSheet("""
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

    def _get_current_time(self):
        """Get current timestamp as string."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _get_title_from_ui(self):
        """Extract title from UI elements."""
        return self.title_label.text().replace('<b>', '').replace('</b>', '')

    def _get_url_from_ui(self):
        """Extract URL from UI elements."""
        return self.domain_label.text()


class ErrorReportDialog(QDialog):
    """Dialog that lets the user send an anonymous error report or copy details."""

    _BTN_SECONDARY = """
        QPushButton {
            background: #3a3a3a;
            border: 1px solid #555;
            border-radius: 6px;
            color: #ccc;
            padding: 8px 16px;
            font-size: 12px;
        }
        QPushButton:hover { background: #4a4a4a; border-color: #666; }
    """
    _BTN_PRIMARY = """
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #5ab0ff, stop:1 #3d8fdb);
            border: none;
            border-radius: 6px;
            color: white;
            padding: 8px 20px;
            font-size: 13px;
        }
        QPushButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #4a9ff5, stop:1 #2d7ec4);
        }
        QPushButton:disabled { background: #555; color: #888; }
    """

    def __init__(self, error_info: dict, parent=None):
        super().__init__(parent)
        self.error_info = error_info
        self.setWindowTitle("Report Error")
        self.setMinimumSize(380, 300)
        self.setModal(True)
        self.setStyleSheet("QDialog { background: #2d2d2d; }")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Report Error")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(title)

        desc = QLabel(
            "Send error details anonymously to help improve dlwithit. "
            "No email or account required.\n\n"
            "Includes: error type, page URL, app version."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #aaa; font-size: 12px;")
        layout.addWidget(desc)

        # Scrollable preview of what will be sent
        preview_text = self.error_info.get('preview_text', '')
        self._preview = QPlainTextEdit(preview_text)
        self._preview.setReadOnly(True)
        self._preview.setMinimumHeight(100)
        self._preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._preview.setStyleSheet("""
            QPlainTextEdit {
                background: #252525;
                color: #aaa;
                font-family: monospace;
                font-size: 11px;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        layout.addWidget(self._preview)

        # Single button row: [Copy to Clipboard] <stretch> [Cancel] [Send Report]
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.setStyleSheet(self._BTN_SECONDARY)
        copy_btn.clicked.connect(self._copy_to_clipboard)
        btn_row.addWidget(copy_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(self._BTN_SECONDARY)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._send_btn = QPushButton("Send Report")
        self._send_btn.setStyleSheet(self._BTN_PRIMARY)
        self._send_btn.clicked.connect(self._send_report)
        btn_row.addWidget(self._send_btn)

        layout.addLayout(btn_row)

    def _copy_to_clipboard(self):
        QApplication.clipboard().setText(self.error_info.get('preview_text', ''))

    def _send_report(self):
        self._send_btn.setEnabled(False)
        self._send_btn.setText("Sending…")

        from core.error_reporter import send_error_report
        success = send_error_report(
            error_type=self.error_info.get('error_type', 'Unknown'),
            error_message=self.error_info.get('error_message', ''),
            url=self.error_info.get('url', ''),
        )

        if success:
            self.accept()
        else:
            # Sending failed — let user copy manually instead
            self._send_btn.setText("Send failed")
            QTimer.singleShot(2000, lambda: (
                self._send_btn.setText("Send Report"),
                self._send_btn.setEnabled(True),
            ))
