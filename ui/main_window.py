"""
MainWindow for Media Downloader App
Main application window with UI initialization, settings management, and download handling
"""

import os
import sys
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                           QPushButton, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                           QAbstractItemView, QMessageBox, QSystemTrayIcon, QMenu, QAction,
                           QCheckBox, QComboBox, QSizePolicy, QFrame,
                           QFileDialog, QApplication, QDesktopWidget)
from PyQt5.QtCore import Qt, pyqtSignal, QRect
from PyQt5.QtGui import QIcon

from version import __version__
from config.settings import Settings
from core.downloader import DownloadWorker
from core.encoder import EncodingWorker, file_needs_encoding
from core.updater import get_ytdlp_version, VersionCheckWorker, InstallUpdateWorker
from core.app_updater import AppVersionCheckWorker, is_newer, notify_update_available
from core.macos import set_dock_visible, set_launch_at_login, refresh_dock_icon
from core.url_router import classify_pasted_url
from ui.components.download_item import DownloadItem
from ui.components.video_selector import VideoSelectorDialog
from ui.window_utils import bring_window_to_front


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
        self._first_download_received = False  # Track first download for bring-to-front

        # Apply Dock visibility from saved setting before any UI work.
        set_dock_visible(not self.settings.get('hide_from_dock', False))
        
        # Set app icon (appears in dock and window title bar)
        self._assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')
        app_icon = QIcon(os.path.join(self._assets_dir, 'app-icon.png'))
        self.setWindowIcon(app_icon)
        QApplication.setWindowIcon(app_icon)

        # Initialize UI components
        self.init_ui()
        self.init_worker()
        self.init_tray()
        
        # Restore window position and size
        self.restore_window_geometry()
        
        # Connect signals
        self.new_download.connect(self.add_download)
        self.video_list_received.connect(self.handle_video_list)

        # Check for yt-dlp updates in the background
        self._check_ytdlp_version()
        # Check for dlwithit app updates in the background
        self._check_app_version()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("dlwithit")
        # Window geometry will be set by restore_window_geometry()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 12)

        # Create UI sections
        self._create_settings_section(layout)
        layout.addSpacing(8)
        self._create_download_queue_section(layout)
        self._create_paste_url_row(layout)

        # Thin separator between paste-URL area and footer
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setStyleSheet("color: #404040;")
        separator.setFixedHeight(1)
        layout.addSpacing(6)
        layout.addWidget(separator)
        layout.addSpacing(4)

        # Footer: active downloads (left) + queue count (right)
        footer_layout = QHBoxLayout()
        self.status_label = QLabel("Active downloads: 0")
        self.status_label.setStyleSheet("color: #aaa; font-size: 12px;")
        self.queue_label = QLabel("")
        self.queue_label.setStyleSheet("color: #aaa; font-size: 12px;")
        self.queue_label.setAlignment(Qt.AlignRight)
        footer_layout.addWidget(self.status_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.queue_label)
        layout.addLayout(footer_layout)
        
        central_widget.setLayout(layout)
    
    def _create_settings_section(self, parent_layout):
        """Create the combined save location + settings section"""
        settings_widget = QWidget()
        settings_widget.setObjectName("settingsPanel")
        settings_layout = QVBoxLayout()
        settings_layout.setContentsMargins(10, 10, 10, 10)
        settings_layout.setSpacing(8)

        # === Save location widget (goes in grid row 0, col 0) ===
        location_widget = QWidget()
        location_inner = QHBoxLayout()
        location_inner.setContentsMargins(0, 0, 0, 0)
        location_inner.setSpacing(4)
        location_label = QLabel("Save to:")
        location_label.setStyleSheet("color: #888; font-size: 11px;")
        self.location_display = QLabel(self.get_display_path())
        self.location_display.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        self.location_display.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        change_link = QLabel("Change")
        change_link.setStyleSheet("color: #888; font-size: 11px;")
        change_link.setCursor(Qt.PointingHandCursor)
        change_link.mousePressEvent = lambda _: self.change_save_location()
        change_link.enterEvent = lambda _: change_link.setStyleSheet(
            "color: #5ab0ff; font-size: 11px; text-decoration: underline;")
        change_link.leaveEvent = lambda _: change_link.setStyleSheet(
            "color: #888; font-size: 11px;")
        location_inner.addWidget(location_label)
        location_inner.addWidget(self.location_display)
        location_inner.addSpacing(6)
        location_inner.addWidget(change_link)
        location_inner.addStretch()
        location_widget.setLayout(location_inner)

        checkmark_path = os.path.join(self._assets_dir, 'checkmark.svg').replace('\\', '/')
        _chk_style = f"""
            QCheckBox {{
                color: #e0e0e0;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #555;
                background: #444;
            }}
            QCheckBox::indicator:checked {{
                background: #5ab0ff;
                border: 1px solid #5ab0ff;
                image: url({checkmark_path});
            }}
        """

        self.encode_checkbox = QCheckBox("Auto-convert WebM/VP9 to MP4")
        self.encode_checkbox.setChecked(self.settings.get('encode_vp9', True))
        self.encode_checkbox.toggled.connect(self.save_settings)
        self.encode_checkbox.setStyleSheet(_chk_style)

        self.keep_original_checkbox = QCheckBox("Keep original after encoding")
        self.keep_original_checkbox.setChecked(self.settings.get('keep_original', False))
        self.keep_original_checkbox.toggled.connect(self.save_settings)
        self.keep_original_checkbox.setStyleSheet(_chk_style)

        self.organize_folders_checkbox = QCheckBox("Organize by platform (YouTube, Instagram, etc.)")
        self.organize_folders_checkbox.setChecked(self.settings.get('organize_by_platform', True))
        self.organize_folders_checkbox.toggled.connect(self.save_settings)
        self.organize_folders_checkbox.setStyleSheet(_chk_style)

        self.show_tray_checkbox = QCheckBox("Show in system tray")
        self.show_tray_checkbox.setChecked(self.settings.get('show_in_tray', True))
        self.show_tray_checkbox.toggled.connect(self.toggle_tray_visibility)
        self.show_tray_checkbox.setStyleSheet(_chk_style)

        self.hide_dock_checkbox = QCheckBox("Hide from Dock")
        self.hide_dock_checkbox.setChecked(self.settings.get('hide_from_dock', False))
        self.hide_dock_checkbox.toggled.connect(self.toggle_hide_from_dock)
        self.hide_dock_checkbox.setStyleSheet(_chk_style)

        self.launch_at_login_checkbox = QCheckBox("Launch at login (hidden)")
        self.launch_at_login_checkbox.setChecked(self.settings.get('launch_at_login', False))
        self.launch_at_login_checkbox.toggled.connect(self.toggle_launch_at_login)
        self.launch_at_login_checkbox.setStyleSheet(_chk_style)

        # Metadata options dropdown (self-contained, no separate label)
        self.metadata_combo = QComboBox()
        self.metadata_combo.addItems([
            "Metadata: None",
            "Metadata: Embedded in file",
            "Metadata: Sidecar files"
        ])

        # Map display text to internal values
        self.metadata_options = {
            "Metadata: None": "none",
            "Metadata: Embedded in file": "embedded",
            "Metadata: Sidecar files": "sidecar"
        }

        # Backward compatibility: migrate old save_metadata boolean to new format
        if 'metadata_option' in self.settings:
            metadata_option = self.settings['metadata_option']
        elif 'save_metadata' in self.settings:
            metadata_option = "sidecar" if self.settings['save_metadata'] else "none"
            self.settings.pop('save_metadata', None)
        else:
            metadata_option = "none"

        # Set dropdown selection based on current setting
        for i, text in enumerate(self.metadata_combo.itemText(j) for j in range(self.metadata_combo.count())):
            if self.metadata_options[text] == metadata_option:
                self.metadata_combo.setCurrentIndex(i)
                break

        self.metadata_combo.currentTextChanged.connect(self.save_settings)

        caret_path = os.path.join(self._assets_dir, 'caret-down.svg').replace('\\', '/')
        self.metadata_combo.setStyleSheet(f"""
            QComboBox {{
                background: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 6px 10px;
                padding-right: 28px;
                font-size: 12px;
            }}
            QComboBox:hover {{
                border-color: #666;
                background: #444;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }}
            QComboBox::down-arrow {{
                image: url({caret_path});
                width: 12px;
                height: 12px;
            }}
        """)

        # 2-column grid layout
        grid_layout = QGridLayout()
        grid_layout.setHorizontalSpacing(16)
        grid_layout.setVerticalSpacing(8)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)

        # Row 0: Save location | Metadata dropdown
        grid_layout.addWidget(location_widget, 0, 0)
        grid_layout.addWidget(self.metadata_combo, 0, 1)

        # Rows 1-2: checkboxes
        grid_layout.addWidget(self.organize_folders_checkbox, 1, 0)
        grid_layout.addWidget(self.show_tray_checkbox, 1, 1)
        grid_layout.addWidget(self.encode_checkbox, 2, 0)
        grid_layout.addWidget(self.keep_original_checkbox, 2, 1)
        grid_layout.addWidget(self.hide_dock_checkbox, 3, 0)
        grid_layout.addWidget(self.launch_at_login_checkbox, 3, 1)

        settings_layout.addLayout(grid_layout)

        # Divider above yt-dlp row
        divider_layout = QHBoxLayout()
        divider_layout.setContentsMargins(0, 2, 0, 2)
        divider_widget = QWidget()
        divider_widget.setFixedHeight(1)
        divider_widget.setAttribute(Qt.WA_StyledBackground, True)
        divider_widget.setStyleSheet("background-color: #404040;")
        divider_layout.addWidget(divider_widget)
        settings_layout.addLayout(divider_layout)

        # yt-dlp version and update status
        self._ytdlp_current_version = get_ytdlp_version()
        self._ytdlp_latest_version = None  # set after background check

        self.ytdlp_version_label = QLabel(f"yt-dlp: {self._ytdlp_current_version}")
        self.ytdlp_version_label.setStyleSheet("color: #aaa; font-size: 12px;")

        self.ytdlp_status_label = QLabel("checking for updates...")
        self.ytdlp_status_label.setStyleSheet("color: #999; font-size: 12px; font-style: italic;")

        self._app_release_url = None  # set after background check, if newer

        self.app_status_label = QLabel("")
        self.app_status_label.setStyleSheet("color: #999; font-size: 12px; font-style: italic;")

        self.app_version_label = QLabel(f"dlwithit {__version__}")
        self.app_version_label.setStyleSheet("color: #aaa; font-size: 12px;")
        self.app_version_label.setAlignment(Qt.AlignRight)

        version_row = QHBoxLayout()
        version_row.setContentsMargins(0, 0, 0, 0)
        version_row.setSpacing(6)
        version_row.addWidget(self.ytdlp_version_label)
        version_row.addWidget(self.ytdlp_status_label)
        version_row.addStretch()
        version_row.addWidget(self.app_status_label)
        version_row.addWidget(self.app_version_label)
        settings_layout.addLayout(version_row)

        settings_widget.setLayout(settings_layout)
        settings_widget.setStyleSheet("""
            QWidget#settingsPanel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #363636, stop:1 #2e2e2e);
                border: 1px solid #404040;
                border-radius: 12px;
            }
        """)

        parent_layout.addWidget(settings_widget)
    
    def _create_download_queue_section(self, parent_layout):
        """Create the download queue section"""
        # Header with clear button
        header_layout = QHBoxLayout()
        header_label = QLabel("<h2>Download Queue</h2>")
        clear_btn = QPushButton("Clear Completed")
        clear_btn.clicked.connect(self.clear_completed)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #3a3a3a;
                color: #aaa;
                border: 1px solid #505050;
                padding: 5px 12px;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #444;
                color: #ccc;
                border-color: #606060;
            }
        """)
        
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        header_layout.addWidget(clear_btn)
        
        # Download list
        self.download_list = QListWidget()
        self.download_list.setSpacing(0)
        self.download_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.download_list.setFocusPolicy(Qt.NoFocus)
        self.download_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.download_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.download_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item:selected {
                background: transparent;
                border: none;
            }
            QListWidget::item:hover {
                background: transparent;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 14px;
                margin: 0;
                padding: 0;
            }
            QScrollBar::handle:vertical {
                background: #555;
                border-radius: 3px;
                min-height: 30px;
                margin: 0 4px 0 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #777;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; background: none; }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical { background: none; }
        """)

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
            path = str(Path.home() / 'Downloads' / 'dlwithit')
        
        # Replace home directory with ~
        home = str(Path.home())
        if path.startswith(home):
            path = '~' + path[len(home):]
        
        return path
    
    def change_save_location(self):
        """Open folder picker dialog"""
        current_path = (self.settings['custom_location'] if self.settings['use_custom_location'] 
                       else str(Path.home() / 'Downloads' / 'dlwithit'))
        
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Download Folder",
            current_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder:
            self.settings['custom_location'] = folder
            self.settings['use_custom_location'] = True
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
        """Initialize the download worker thread and encoding worker"""
        # Initialize download worker
        self.worker = DownloadWorker(self.download_queue)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.download_complete.connect(self.download_finished)
        self.worker.download_error.connect(self.download_failed)
        self.worker.download_cancelled.connect(self.download_cancelled)
        self.worker.status_update.connect(self.update_status)
        self.worker.playlist_detected.connect(self.handle_playlist_detected)
        self.worker.download_skipped.connect(self.download_skipped_handler)
        self.worker.encoding_needed.connect(self.queue_encoding_job)
        self.worker.start()

        # Initialize encoding worker (runs in parallel with downloads)
        self.encoding_worker = EncodingWorker()
        self.encoding_worker.encoding_started.connect(self.encoding_started_handler)
        self.encoding_worker.encoding_progress.connect(self.encoding_progress_handler)
        self.encoding_worker.encoding_complete.connect(self.encoding_complete_handler)
        self.encoding_worker.encoding_error.connect(self.encoding_error_handler)
        self.encoding_worker.encoding_cancelled.connect(self.encoding_cancelled_handler)
        self.encoding_worker.start()
    
    def init_tray(self):
        """Initialize system tray icon and menu"""
        self.tray_icon = QSystemTrayIcon(self)
        tray_icon_path = os.path.join(self._assets_dir, 'trayIconTemplate@2x.png')
        tray_icon = QIcon(tray_icon_path)
        tray_icon.setIsMask(True)
        self.tray_icon.setIcon(tray_icon)

        # Create tray menu
        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(lambda: bring_window_to_front(self))
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)

        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)

        # Show/hide tray based on setting
        if self.settings.get('show_in_tray', True):
            self.tray_icon.show()
        else:
            self.tray_icon.hide()

        # Connect tray activation
        self.tray_icon.activated.connect(self.tray_activated)

    def quit_application(self):
        """Properly shut down workers and quit the application"""
        # Stop the encoding worker
        self.encoding_worker.stop()
        self.encoding_worker.wait(5000)  # Wait up to 5 seconds for clean shutdown
        # Stop the download worker
        self.download_queue.put(None)  # Signal worker to stop
        self.worker.wait(5000)
        QApplication.quit()
    
    def toggle_tray_visibility(self, checked):
        """Toggle system tray icon visibility based on checkbox"""
        self.settings['show_in_tray'] = checked
        Settings.save(self.settings)

    def _create_paste_url_row(self, parent_layout):
        """Build the paste-URL fallback row as a collapsible disclosure.

        Sits between the download queue and the footer. Collapsed by default
        so the extension reads as the canonical entry point; expanded state
        persists in Settings as `paste_url_expanded`.
        """
        container_layout = QVBoxLayout()
        container_layout.setSpacing(0)
        container_layout.setContentsMargins(0, 4, 0, 0)

        self.paste_url_toggle = QWidget()
        self.paste_url_toggle.setCursor(Qt.PointingHandCursor)
        toggle_layout = QHBoxLayout(self.paste_url_toggle)
        toggle_layout.setContentsMargins(2, 4, 0, 4)
        toggle_layout.setSpacing(8)

        self._paste_url_chevron = QLabel()
        self._paste_url_chevron.setStyleSheet("color: #888; font-size: 14px; font-weight: bold;")
        self._paste_url_chevron.setFixedWidth(18)
        self._paste_url_chevron.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)

        self._paste_url_label = QLabel()
        self._paste_url_label.setStyleSheet("color: #888; font-size: 12px;")
        self._paste_url_label.setAlignment(Qt.AlignVCenter)

        toggle_layout.addWidget(self._paste_url_chevron)
        toggle_layout.addWidget(self._paste_url_label)
        toggle_layout.addStretch()

        # Clicks anywhere on the row toggle the disclosure
        self.paste_url_toggle.mousePressEvent = lambda _e: self._toggle_paste_url_row()

        self.paste_url_container = QWidget()
        paste_layout = QHBoxLayout(self.paste_url_container)
        paste_layout.setContentsMargins(0, 4, 0, 0)
        paste_layout.setSpacing(6)

        self.paste_url_input = QLineEdit()
        self.paste_url_input.setPlaceholderText("Paste URL…")
        self.paste_url_input.setStyleSheet(
            "QLineEdit { background: #3a3a3a; color: #e0e0e0; "
            "border: 1px solid #555; border-radius: 6px; padding: 6px 10px; "
            "font-size: 12px; }"
            "QLineEdit:focus { border-color: #5ab0ff; }"
        )
        self.paste_url_input.returnPressed.connect(self._submit_pasted_url)

        self.paste_url_button = QPushButton("Download")
        self.paste_url_button.setStyleSheet(
            "QPushButton { background: #4a4a4a; color: #e0e0e0; "
            "border: 1px solid #555; border-radius: 6px; padding: 6px 14px; "
            "font-size: 12px; }"
            "QPushButton:hover { background: #555; }"
            "QPushButton:pressed { background: #3a3a3a; }"
        )
        self.paste_url_button.clicked.connect(self._submit_pasted_url)

        paste_layout.addWidget(self.paste_url_input, stretch=1)
        paste_layout.addWidget(self.paste_url_button)

        container_layout.addWidget(self.paste_url_toggle)
        container_layout.addWidget(self.paste_url_container)
        parent_layout.addLayout(container_layout)

        self._paste_url_expanded = self.settings.get('paste_url_expanded', False)
        self._update_paste_url_disclosure()

    def _toggle_paste_url_row(self):
        self._paste_url_expanded = not self._paste_url_expanded
        self.settings['paste_url_expanded'] = self._paste_url_expanded
        Settings.save(self.settings)
        self._update_paste_url_disclosure()
        if self._paste_url_expanded:
            self.paste_url_input.setFocus()

    def _update_paste_url_disclosure(self):
        self._paste_url_chevron.setText("▼" if self._paste_url_expanded else "▶")
        self._paste_url_label.setText("Paste a URL")
        self.paste_url_container.setVisible(self._paste_url_expanded)

    def _submit_pasted_url(self):
        """Route a pasted URL through classify and queue it for download."""
        url = self.paste_url_input.text().strip()
        if not url:
            return

        kind = classify_pasted_url(url)

        if kind == 'unsupported':
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("No media detected at that URL")
            msg.setTextFormat(Qt.RichText)
            msg.setText("<b>We couldn't find any media at this URL.</b>")
            msg.setInformativeText(
                "Some pages load videos only when you scroll or interact — "
                "pasting a URL can't see those.<br><br>"
                "To download from a page like this, open it in your browser "
                "and use the extension's <b>Video Download</b> or "
                "<b>Pick Images</b>."
            )
            msg.exec_()
            return

        # Mirror the extension's payload shape so the existing add_download
        # path handles it without special casing. The image path overrides
        # the title with the URL filename; for video we pass a placeholder
        # — yt-dlp will fill in the real title once it extracts info.
        self.new_download.emit({
            'url': url,
            'type': kind,
            'pageUrl': url,
            'title': os.path.basename(urlparse(url).path) or 'Pasted URL',
        })
        self.paste_url_input.clear()

    def toggle_hide_from_dock(self, checked):
        """Toggle Dock icon visibility live (no restart needed)."""
        self.settings['hide_from_dock'] = checked
        Settings.save(self.settings)
        set_dock_visible(not checked)
        if not checked:
            # Restore our icon — macOS drops it on Accessory→Regular.
            refresh_dock_icon(os.path.join(self._assets_dir, 'app-icon.png'))

    def toggle_launch_at_login(self, checked):
        """Add or remove dlwithit from macOS login items."""
        self.settings['launch_at_login'] = checked
        Settings.save(self.settings)
        set_launch_at_login(checked, hidden=True)
        if checked:
            self.tray_icon.show()
        else:
            self.tray_icon.hide()

    def _check_ytdlp_version(self):
        """Spawn a background thread to check for yt-dlp updates."""
        self._version_check_worker = VersionCheckWorker()
        self._version_check_worker.finished.connect(self._on_version_check_done)
        self._version_check_worker.start()

    def _on_version_check_done(self, latest):
        """Handle the result of the background version check."""
        current = self._ytdlp_current_version
        if not latest:
            # Check failed (network error, etc.) — just hide status quietly
            self.ytdlp_status_label.setText("")
            return

        self._ytdlp_latest_version = latest

        if current == latest:
            self.ytdlp_status_label.setText("")
        else:
            # Show clickable "Update available" text
            self.ytdlp_status_label.setText(f"Update available ({latest})")
            self.ytdlp_status_label.setStyleSheet(
                "color: #2980b9; font-size: 12px; font-style: normal; "
                "text-decoration: underline; cursor: pointer;"
            )
            self.ytdlp_status_label.setCursor(__import__('PyQt5').QtCore.Qt.PointingHandCursor)
            self.ytdlp_status_label.mousePressEvent = lambda _: self._start_ytdlp_update()

    def _start_ytdlp_update(self):
        """Kick off the actual yt-dlp install in a background thread."""
        if not self._ytdlp_latest_version:
            return

        # Switch to "Updating..." state
        self.ytdlp_status_label.setText("Updating...")
        self.ytdlp_status_label.setStyleSheet("color: #999; font-size: 12px; font-style: italic;")
        self.ytdlp_status_label.setCursor(__import__('PyQt5').QtCore.Qt.ArrowCursor)
        self.ytdlp_status_label.mousePressEvent = lambda _: None  # disable click

        self._install_worker = InstallUpdateWorker(self._ytdlp_latest_version)
        self._install_worker.status_update.connect(
            lambda msg: self.ytdlp_status_label.setText(msg))
        self._install_worker.finished.connect(self._on_install_finished)
        self._install_worker.start()

    def _on_install_finished(self, success, message, new_version):
        """Handle install completion."""
        if success:
            self._ytdlp_current_version = new_version
            self.ytdlp_version_label.setText(f"yt-dlp: {new_version}")
            self.ytdlp_status_label.setText(f"\u2713 {message}")
            self.ytdlp_status_label.setStyleSheet("color: #27ae60; font-size: 12px; font-style: normal;")
        else:
            self.ytdlp_status_label.setText(message)
            self.ytdlp_status_label.setStyleSheet("color: #e67e22; font-size: 12px; font-style: normal;")

    def _check_app_version(self):
        """Spawn a background thread to check for dlwithit app updates."""
        self._app_version_check_worker = AppVersionCheckWorker()
        self._app_version_check_worker.finished.connect(self._on_app_version_check_done)
        self._app_version_check_worker.start()

    def _on_app_version_check_done(self, latest, release_url):
        """Show 'Update available' link + fire one launch notification when newer."""
        if not latest or not is_newer(latest, __version__):
            return

        self._app_release_url = release_url
        self.app_status_label.setText(f"Update available ({latest})")
        self.app_status_label.setStyleSheet(
            "color: #2980b9; font-size: 12px; font-style: normal; "
            "text-decoration: underline; cursor: pointer;"
        )
        self.app_status_label.setCursor(Qt.PointingHandCursor)
        self.app_status_label.mousePressEvent = lambda _: self._open_app_release_page()
        notify_update_available(latest)

    def _open_app_release_page(self):
        """Open the GitHub release page in the user's default browser."""
        if self._app_release_url:
            webbrowser.open(self._app_release_url)

    def tray_activated(self, reason):
        """Handle system tray icon activation (single-click toggle, works on Windows/Linux)"""
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible() and not self.isMinimized():
                self.hide()
            else:
                bring_window_to_front(self)
    
    def get_current_save_path(self):
        """
        Get the current save path based on settings.
        
        Returns:
            str: Current save path
        """
        if self.settings['use_custom_location']:
            return self.settings['custom_location']
        else:
            return str(Path.home() / 'Downloads' / 'dlwithit')
    
    def add_download(self, data):
        """
        Add a new download to the queue.

        Args:
            data: Dictionary containing download information
        """
        # Bring window to front on first download of the session
        if not self._first_download_received:
            self._first_download_received = True
            bring_window_to_front(self)

        download_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        # Determine title based on download type
        title = data.get('title', 'Unknown')
        if data['type'] == 'image':
            # Extract filename for images
            title = os.path.basename(urlparse(data['url']).path) or 'Image'
        
        # Get thumbnail URL
        thumbnail_url = data.get('thumbnail')
        
        # Create download item widget
        item_widget = DownloadItem(download_id, title, data['url'], thumbnail_url)
        
        # Connect cancel button
        item_widget.cancel_btn.clicked.connect(lambda: self.cancel_download(download_id))
        
        # Create container widget with download item
        container_widget = QWidget()
        container_widget.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(0, 4, 0, 4)
        container_layout.setSpacing(0)

        # Add the download item
        container_layout.addWidget(item_widget)

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
            'title': data.get('title'),
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
        
        self.download_queue.put(download_queue_data)

        # Update UI status
        item_widget.status_label.setText("Starting...")
        item_widget.status_label.setStyleSheet("color: #5ab0ff;")
        item_widget.cancel_btn.show()

        # Show system notification
        media_type = data.get('type', 'video').capitalize()
        self.tray_icon.showMessage(
            f"{media_type} Download Started",
            f"Downloading: {title}",
            QSystemTrayIcon.Information,
            2000
        )
        
        # Update status label
        self._update_status_footer()
    
    def handle_video_list(self, data):
        """
        Handle a list of videos from page scraping.

        Args:
            data: Dictionary containing video list and page metadata
        """
        # Mark first download received (dialog's showEvent handles bring-to-front)
        self._first_download_received = True

        
        try:
            # Show video selector dialog
            dialog = VideoSelectorDialog(
                data['videos'],
                data['pageTitle'],
                data['pageUrl'],
                self
            )
            
            
            if dialog.exec_():
                selected = dialog.get_selected_videos()
                
                if selected:
                    
                    # Process each selected video
                    for video_info in selected:
                        url = video_info['url']
                        video_type = video_info.get('type', 'direct')

                        # Types from the extension that always mean direct file download.
                        # Includes HTML MIME types (e.g. 'video/mp4' from <source type="...">)
                        # and extension-defined type strings.
                        DIRECT_TYPES = {
                            'direct', 'srcset', 'data-attribute', 'script-json',
                            'preload', 'mux', 'meta-tag',
                            'video/mp4', 'video/webm', 'video/quicktime',
                            'video/x-m4v', 'video/ogg', 'video/x-matroska',
                        }

                        # Check if this should use yt-dlp (HLS or platform URL)
                        if (video_type == 'hls' or
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
                            self.add_download(download_data)
                        else:
                            # Determine if this is a direct file download.
                            # Trust the extension's type field first; fall back to URL extension.
                            is_direct_file = (
                                video_type in DIRECT_TYPES or
                                url.endswith(('.mp4', '.webm', '.mov', '.avi', '.mkv', '.m4v')) or
                                any(ext in url.lower() for ext in ['.mp4?', '.webm?', '.mov?'])
                            )

                            if is_direct_file:
                                # Direct file - use direct download
                                download_data = {
                                    'url': url,
                                    'title': video_info.get('title', 'Video'),
                                    'pageUrl': data['pageUrl'],
                                    'source': data['source'],
                                    'thumbnail': video_info.get('thumbnail')
                                }
                                self.add_direct_video_download(download_data)
                            else:
                                # Unknown format - use yt-dlp as last resort
                                download_data = {
                                    'url': url,
                                    'title': video_info.get('title', 'Video'),
                                    'type': 'video',
                                    'pageUrl': data['pageUrl'],
                                    'source': data['source'],
                                    'thumbnail': video_info.get('thumbnail')
                                }
                                self.add_download(download_data)
                    
                    # Show batch notification
                    self.tray_icon.showMessage(
                        "Video Downloads Started",
                        f"Downloading {len(selected)} videos from {data['pageTitle']}",
                        QSystemTrayIcon.Information,
                        2000
                    )
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
        # Mark first download received (dialog's showEvent handles bring-to-front)
        # Note: This is usually already set, but handles edge cases
        self._first_download_received = True

        
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
            
            
            if dialog.exec_():
                selected = dialog.get_selected_videos()
                
                if selected:
                    
                    # Process each selected video (same logic as handle_video_list)
                    for video_info in selected:
                        url = video_info['url']
                        video_type = video_info.get('type', 'direct')

                        DIRECT_TYPES = {
                            'direct', 'srcset', 'data-attribute', 'script-json',
                            'preload', 'mux', 'meta-tag',
                            'video/mp4', 'video/webm', 'video/quicktime',
                            'video/x-m4v', 'video/ogg', 'video/x-matroska',
                        }

                        # Check if this should use yt-dlp (HLS or platform URL)
                        if (video_type == 'hls' or
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
                                'pageUrl': playlist_data['pageUrl'],
                                'source': playlist_data['source'],
                                'thumbnail': video_info.get('thumbnail'),
                                'skip_playlist_detection': True,
                                'playlist_index': video_info.get('playlist_index')
                            }
                            self.add_download(download_data)
                        else:
                            is_direct_file = (
                                video_type in DIRECT_TYPES or
                                url.endswith(('.mp4', '.webm', '.mov', '.avi', '.mkv', '.m4v')) or
                                any(ext in url.lower() for ext in ['.mp4?', '.webm?', '.mov?'])
                            )

                            if is_direct_file:
                                # Direct file - use direct download
                                download_data = {
                                    'url': url,
                                    'title': video_info.get('title', 'Video'),
                                    'pageUrl': playlist_data['pageUrl'],
                                    'source': playlist_data['source'],
                                    'thumbnail': video_info.get('thumbnail')
                                }
                                self.add_direct_video_download(download_data)
                            else:
                                # Unknown format - use yt-dlp as last resort
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
                                self.add_download(download_data)
                    
                    # Show batch notification
                    self.tray_icon.showMessage(
                        "Playlist Downloads Started",
                        f"Downloading {len(selected)} videos from playlist",
                        QSystemTrayIcon.Information,
                        2000
                    )
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
        # Bring window to front on first download of the session
        if not self._first_download_received:
            self._first_download_received = True
            bring_window_to_front(self)

        download_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        # Create download item
        title = data.get('title', 'Video')
        thumbnail_url = data.get('thumbnail')
        
        item_widget = DownloadItem(download_id, title, data['url'], thumbnail_url)
        
        # Connect cancel button
        item_widget.cancel_btn.clicked.connect(lambda: self.cancel_download(download_id))
        
        # Create container widget with download item
        container_widget = QWidget()
        container_widget.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(0, 4, 0, 4)
        container_layout.setSpacing(0)

        # Add the download item
        container_layout.addWidget(item_widget)

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
        
        self.download_queue.put(download_queue_data)

        # Update UI status
        item_widget.status_label.setText("Starting...")
        item_widget.status_label.setStyleSheet("color: #5ab0ff;")
        item_widget.cancel_btn.show()

        self._update_status_footer()
    
    def cancel_download(self, download_id):
        """Cancel a download or encoding job"""
        self.worker.cancel_download(download_id)
        self.encoding_worker.cancel_job(download_id)  # Also cancel any pending/active encoding
        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            widget.status_label.setText("Cancelling...")
            widget.status_label.setStyleSheet("color: #f87171;")
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
                widget.status_label.setStyleSheet("color: #5ab0ff;")
            elif status == 'merging':
                widget.status_label.setText("Merging...")
                widget.status_label.setStyleSheet("color: #16a085;")  # Teal color
                widget.progress_bar.setValue(100)  # Show as complete since we can't track merge progress
            elif status == 'encoding':
                widget.set_encoding()
                widget.status_label.setText("Converting to MP4...")
                widget.status_label.setStyleSheet("color: #9b59b6;")
                widget.progress_bar.setValue(0)  # Reset for encoding progress
            elif status.startswith('embedding'):
                widget.status_label.setText("Embedding...")
                widget.status_label.setStyleSheet("color: #16a085;")
    
    def download_finished(self, download_id, path):
        """Handle download completion"""
        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            widget.progress_bar.setValue(100)
            # Clear any prior reveal/re-encode buttons (e.g. after a manual re-encode pass)
            widget.clear_extra_action_buttons()

            # Handle multi-file downloads
            if "|MULTI|" in path:
                actual_path, _, file_count = path.partition("|MULTI|")
                widget.status_label.setText(f"Complete - {file_count}")
                widget.status_label.setStyleSheet("color: #4ade80;")

                folder_path = os.path.dirname(actual_path)
                widget.set_reveal(folder_path, is_folder=True)
            else:
                widget.status_label.setText("Complete")
                widget.status_label.setStyleSheet("color: #4ade80;")

                widget.set_reveal(path, is_folder=False)

                # Offer manual re-encode if the file is still VP9/VP8/AV1
                # (e.g. user opted out of auto-encoding, or it was a direct .webm)
                try:
                    if file_needs_encoding(path):
                        widget.enable_reencode(path, lambda p, did=download_id: self.start_manual_reencode(did, p))
                except Exception:
                    pass

            widget.set_complete()
            
            # Show completion notification
            self.tray_icon.showMessage(
                "Download Complete",
                f"Saved: {os.path.basename(path.split('|')[0])}",
                QSystemTrayIcon.Information,
                2000
            )
        
        self._update_status_footer()
    
    def _extract_short_error(self, raw_error):
        """Extract a concise one-line error summary from yt-dlp/requests output."""
        import re
        clean = re.sub(r'\x1b\[[0-9;]*m', '', raw_error)  # strip ANSI codes
        # yt-dlp errors always contain an 'ERROR: ...' line — extract just that
        for line in clean.splitlines():
            line = line.strip()
            if line.startswith('ERROR:'):
                msg = line[6:].strip()
                msg = re.sub(r'^\[[^\]]+\]\s*', '', msg)   # strip [extractor] prefix
                msg = re.sub(r'https?://\S+', 'URL', msg)  # shorten URLs
                return msg[:55] + '\u2026' if len(msg) > 55 else msg
        # Fallback: collapse whitespace, strip verbose exception prefixes
        clean = ' '.join(clean.split())
        clean = re.sub(r'(Exception Type|Error Message|Traceback)[^:]*:\s*', '', clean)
        return clean[:55] + '\u2026' if len(clean) > 55 else clean

    def download_failed(self, download_id, error):
        """Handle download failure"""
        # Bring window to front so user sees the error
        bring_window_to_front(self)

        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            widget.progress_bar.setValue(0)
            short_error = self._extract_short_error(error)
            widget.set_error(short_error, error)

        self._update_status_footer()
    
    def download_cancelled(self, download_id):
        """Handle download cancellation"""
        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            widget.progress_bar.setValue(0)
            widget.status_label.setText("Cancelled")
            widget.status_label.setStyleSheet("color: #888;")
            widget.cancel_btn.setEnabled(False)

            # Show cancellation notification
            self.tray_icon.showMessage(
                "Download Cancelled",
                "Download was cancelled and files cleaned up",
                QSystemTrayIcon.Information,
                2000
            )

        self._update_status_footer()

    def download_skipped_handler(self, download_id, reason, filepath):
        """Handle skipped download (file already exists)"""

        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            widget.progress_bar.setValue(100)
            widget.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            widget.status_label.setText("Skipped: File exists")
            widget.status_label.setStyleSheet("color: #fbbf24;")
            widget.cancel_btn.hide()
            widget.set_reveal(filepath)

        # Show notification (always, even if item not found in UI)
        self.tray_icon.showMessage(
            "Download Skipped",
            reason,
            QSystemTrayIcon.Information,
            2000
        )

        self._update_status_footer()

    def queue_encoding_job(self, download_id, filepath, keep_original, metadata_info):
        """Queue an encoding job for the encoding worker"""
        # Update UI to show download complete, awaiting encoding
        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            widget.progress_bar.setValue(100)
            widget.status_label.setText("Queued for conversion...")
            widget.status_label.setStyleSheet("color: #8e44ad;")  # Purple to indicate encoding-related
        self.encoding_worker.add_job(download_id, filepath, keep_original, metadata_info)

    def start_manual_reencode(self, download_id, filepath):
        """User-triggered re-encode of an already-completed download. Keeps the original."""
        if download_id not in self.download_items:
            return
        widget = self.download_items[download_id]['widget']
        widget.set_reencode_busy(True)
        widget.cancel_btn.setEnabled(True)
        widget.cancel_btn.show()
        widget.progress_bar.setValue(0)
        # keep_original=True so the source .webm stays put alongside the new _h264.mp4
        self.queue_encoding_job(download_id, filepath, True, {})

    def encoding_started_handler(self, download_id):
        """Handle encoding started"""
        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            widget.set_encoding()
            widget.status_label.setText("Converting to MP4...")
            widget.status_label.setStyleSheet("color: #9b59b6;")
            widget.progress_bar.setValue(0)

    def encoding_progress_handler(self, download_id, percent, status):
        """Handle encoding progress updates"""
        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            widget.progress_bar.setValue(percent)
            widget.status_label.setText(status)

    def encoding_complete_handler(self, download_id, final_path):
        """Handle encoding completion - same as download_finished"""
        # Reuse the download_finished handler since the UI behavior is the same
        self.download_finished(download_id, final_path)

    def encoding_error_handler(self, download_id, error):
        """Handle encoding error"""
        # Bring window to front so user sees the error
        bring_window_to_front(self)

        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            widget.progress_bar.setValue(0)
            short_error = f"Conversion: {self._extract_short_error(error)}"
            widget.set_error(short_error, f"Conversion Error: {error}")
            # If a manual re-encode failed, let the user retry
            widget.set_reencode_busy(False)

        self._update_status_footer()

    def encoding_cancelled_handler(self, download_id):
        """Handle encoding cancellation"""
        if download_id in self.download_items:
            widget = self.download_items[download_id]['widget']
            widget.progress_bar.setValue(0)
            widget.status_label.setText("Conversion Cancelled")
            widget.status_label.setStyleSheet("color: #888;")
            widget.cancel_btn.setEnabled(False)
            # If this was a manual re-encode, leave the Re-encode button available for retry
            widget.set_reencode_busy(False)

        self._update_status_footer()

    def clear_completed(self):
        """Clear completed, failed, skipped, and cancelled downloads from the list"""
        to_remove = []
        for download_id, item_data in self.download_items.items():
            status = item_data['widget'].status_label.text()
            if (status.startswith("Complete") or status.startswith("Failed") or
                status.startswith("Skipped") or status.startswith("Cancel") or
                status.startswith("Conversion Cancelled") or status.startswith("Conversion failed")):
                to_remove.append(download_id)

        # Remove items from UI and storage
        for download_id in to_remove:
            item = self.download_items[download_id]['item']
            self.download_list.takeItem(self.download_list.row(item))
            del self.download_items[download_id]

    def count_active(self):
        """
        Count active downloads and encoding jobs.

        Returns:
            int: Number of active downloads/encoding jobs
        """
        count = 0
        for item_data in self.download_items.values():
            status = item_data['widget'].status_label.text()
            # Active if not in a terminal state
            if not (status.startswith("Complete") or status.startswith("Failed") or
                    status.startswith("Cancel") or status.startswith("Skipped") or
                    status.startswith("Conversion Cancelled") or status.startswith("Conversion failed")):
                count += 1
        return count

    def _update_status_footer(self):
        """Update the footer labels with current active and queued counts."""
        active = self.count_active()
        queued = self.download_queue.qsize()
        self.status_label.setText(f"Active downloads: {active}")
        self.queue_label.setText(f"{queued} in queue" if queued else "")

    def restore_window_geometry(self):
        """Restore window position and size from settings with multi-monitor support"""
        geometry = self.settings.get('window_geometry', {})
        
        # Get desktop widget for multi-monitor support
        desktop = QApplication.desktop()
        
        # Set window size
        width = geometry.get('width', 580)
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
        
        
        # Additional debug info about multi-monitor setup
        if desktop.screenCount() > 1:
            for i in range(desktop.screenCount()):
                screen_rect = desktop.screenGeometry(i)
                is_primary = " (PRIMARY)" if i == desktop.primaryScreen() else ""
    
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
        """Handle window close event (minimize to tray if enabled, otherwise quit)"""
        # Save window position and size before hiding
        self.save_window_geometry()

        if self.settings.get('show_in_tray', True) and self.tray_icon.isVisible():
            # Minimize to tray
            event.ignore()
            self.hide()

            # Show one-time notification that app is still running
            # Use a short delay so the notification fires after the hide completes
            if not self.settings.get('tray_minimize_notified', False):
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(500, self._show_tray_minimize_notification)
        else:
            # Tray disabled — actually quit
            event.accept()
            self.quit_application()

    def _show_tray_minimize_notification(self):
        """Show one-time notification that app is still running in tray"""
        self.tray_icon.showMessage(
            "dlwithit",
            "dlwithit is still running in the system tray",
            QSystemTrayIcon.Information,
            3000
        )
        self.settings['tray_minimize_notified'] = True
        Settings.save(self.settings)