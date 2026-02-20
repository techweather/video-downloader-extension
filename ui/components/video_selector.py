"""
VideoSelectorDialog component for Media Downloader App
Dialog for selecting which videos to download from a scraped page
"""

import os
import re

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QWidget, QCheckBox,
                             QPushButton, QAbstractItemView)
from PyQt5.QtCore import Qt

from ui.window_utils import bring_dialog_to_front


_BTN_PRIMARY = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #5ab0ff, stop:1 #3d8fdb);
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        font-size: 12px;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #4a9ff5, stop:1 #2d7ec4);
    }
"""

_BTN_SECONDARY = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #555555, stop:1 #444444);
        color: #e0e0e0;
        border: 1px solid #606060;
        padding: 8px 16px;
        border-radius: 6px;
        font-size: 12px;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #666666, stop:1 #555555);
        border-color: #777;
    }
"""


class VideoSelectorDialog(QDialog):
    """Dialog for selecting which videos to download from a page."""

    def __init__(self, videos, page_title, page_url, parent=None):
        super().__init__(parent)
        self.videos = videos
        self.page_title = page_title
        self.page_url = page_url
        self.checkboxes = []
        self.item_widgets = []

        # Checkmark SVG path — assets/ is two directories up from ui/components/
        assets_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'assets'
        )
        self._checkmark_path = os.path.join(assets_dir, 'checkmark.svg').replace('\\', '/')

        self.setWindowTitle(f"Select Videos — {page_title}")
        self.setModal(True)
        self.resize(680, 520)
        self.setStyleSheet("QDialog { background-color: #2d2d2d; }")

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        count = len(videos)
        count_label = QLabel(f"Found <b>{count}</b> video{'s' if count != 1 else ''}")
        count_label.setStyleSheet("color: #e0e0e0; font-size: 14px;")
        layout.addWidget(count_label)

        url_label = QLabel(page_url)
        url_label.setWordWrap(True)
        url_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(url_label)

        # Video list — transparent, no border, scrollbar overlays when needed
        self.list_widget = QListWidget()
        self.list_widget.setSpacing(0)
        self.list_widget.setSelectionMode(QAbstractItemView.NoSelection)
        self.list_widget.setFocusPolicy(Qt.NoFocus)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background: transparent;
                border: none;
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

        for i, video in enumerate(videos):
            self._create_video_item(i, video)

        layout.addWidget(self.list_widget)

        # Bottom row: select controls on left, action buttons on right
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        select_all_btn = QPushButton("Select All")
        select_all_btn.setStyleSheet(_BTN_SECONDARY)
        select_all_btn.clicked.connect(self.select_all)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.setStyleSheet(_BTN_SECONDARY)
        deselect_all_btn.clicked.connect(self.deselect_all)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_BTN_SECONDARY)
        cancel_btn.clicked.connect(self.reject)

        download_btn = QPushButton("Download Selected")
        download_btn.setStyleSheet(_BTN_PRIMARY)
        download_btn.clicked.connect(self.accept)

        bottom_row.addWidget(select_all_btn)
        bottom_row.addWidget(deselect_all_btn)
        bottom_row.addStretch()
        bottom_row.addWidget(cancel_btn)
        bottom_row.addWidget(download_btn)

        layout.addLayout(bottom_row)
        self.setLayout(layout)

    def showEvent(self, event):
        super().showEvent(event)
        bring_dialog_to_front(self, self.parent())

    def _create_video_item(self, index, video):
        """Create a single video item widget."""
        # Transparent container provides top/bottom gap between cards
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(0, 4, 0, 4)
        container_layout.setSpacing(0)

        # Card — matches download item visual style
        card = QWidget()
        card.setObjectName("videoCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet("""
            QWidget#videoCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #363636, stop:1 #2e2e2e);
                border: 1px solid #404040;
                border-radius: 10px;
            }
        """)

        card_layout = QHBoxLayout()
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(12)

        # Checkbox — matches main window style with checkmark
        checkbox = QCheckBox()
        checkbox.setChecked(True)
        checkbox.setStyleSheet(f"""
            QCheckBox {{
                spacing: 0px;
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
                image: url({self._checkmark_path});
            }}
        """)
        self.checkboxes.append(checkbox)

        # Text: title + optional file details
        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)
        info_layout.setContentsMargins(0, 0, 0, 0)

        title = video.get('title', f'Video {index + 1}')
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setStyleSheet("color: #e0e0e0; font-size: 13px;")
        title_label.setWordWrap(True)
        info_layout.addWidget(title_label)

        details = self._format_video_details(video)
        if details:
            details_label = QLabel(" · ".join(details))
            details_label.setStyleSheet("color: #888; font-size: 11px;")
            info_layout.addWidget(details_label)

        card_layout.addWidget(checkbox, 0, Qt.AlignVCenter)
        card_layout.addLayout(info_layout, 1)
        card.setLayout(card_layout)

        container_layout.addWidget(card)
        container.setLayout(container_layout)

        list_item = QListWidgetItem()
        list_item.setSizeHint(container.sizeHint())
        self.list_widget.addItem(list_item)
        self.list_widget.setItemWidget(list_item, container)
        self.item_widgets.append(card)

    def _format_video_details(self, video):
        """Format video type/filename details for display."""
        details = []
        if video.get('originalFilename'):
            details.append(video['originalFilename'])
        video_type = video.get('type', 'unknown')
        if video_type == 'hls':
            details.append("HLS Stream")
        elif video_type == 'direct':
            details.append("MP4")
        elif video_type == 'data-attribute':
            details.append("Embedded")
        return details

    def select_all(self):
        for checkbox in self.checkboxes:
            checkbox.setChecked(True)

    def deselect_all(self):
        for checkbox in self.checkboxes:
            checkbox.setChecked(False)

    def get_selected_videos(self):
        """Return list of selected video metadata dicts."""
        selected = []
        for i, checkbox in enumerate(self.checkboxes):
            if checkbox.isChecked():
                video = self.videos[i]
                title = video.get('title', f'Video_{i + 1}')
                clean_title = re.sub(r'[^\w\s-]', '', title)
                clean_title = re.sub(r'[-\s]+', '_', clean_title)
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
