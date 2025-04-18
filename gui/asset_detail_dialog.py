# -*- coding: utf-8 -*-
# gui/asset_detail_dialog.py

import logging
import shutil
import tempfile
import zipfile # Importa il modulo zipfile
import time # Needed for timestamp in temp filename
from pathlib import Path
from datetime import datetime
from typing import Optional, Union

from PyQt6.QtCore import (
    QSize,
    Qt,
    QThreadPool,
    pyqtSignal,
    pyqtSlot,
    QRect,
    QPoint,
    QUrl,
)
from PyQt6.QtGui import (
    QDesktopServices,
    QPixmap,
    QPainter,
    QColor,
    QMouseEvent,
    QPolygon,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QProgressBar,
    QFileDialog,
    QSizePolicy,
    QCheckBox,
    QSpacerItem,
    QSplitter,
    QStatusBar,
    QInputDialog,
    QLineEdit,
)

# Import necessary functions and classes
from api_clients import fetch_asset_details_sync
from data_manager import DataManager # Import the class, not the deprecated function
from utils import ICON_SIZE, IconDownloader, DownloadThread, extract_zip
from project_handler import get_godot_version_string, install_extensions_logic # Assuming install_extensions_logic is imported

# Constants for preview sizes
PREVIEW_MAX_HEIGHT = 300 # Max height for the main preview image (can be adjusted)
THUMBNAIL_SIZE = QSize(120, 70) # Size for thumbnail previews
# Colors for video overlay
PLAY_ICON_COLOR = QColor(255, 255, 255, 200) # Semi-transparent white for play icon
OVERLAY_COLOR = QColor(0, 0, 0, 100) # Semi-transparent black overlay


def _add_video_overlay(pixmap: QPixmap) -> QPixmap:
    """Draws a dark overlay and a Play icon onto a QPixmap, indicating a video."""
    if pixmap.isNull():
        return pixmap # Return original if null

    # Create a copy to draw on
    overlay_pixmap = pixmap.copy()
    painter = QPainter(overlay_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Draw dark overlay
    overlay_rect = overlay_pixmap.rect()
    painter.fillRect(overlay_rect, OVERLAY_COLOR)

    # Draw Play icon (triangle) in the center
    w, h = overlay_rect.width(), overlay_rect.height()
    icon_size = min(w, h) * 0.4 # Icon size proportional to pixmap size
    cx, cy = w / 2, h / 2
    # Define triangle points relative to center
    triangle_points = [
        QPoint(int(cx - icon_size * 0.3), int(cy - icon_size * 0.4)), # Top-left vertex
        QPoint(int(cx + icon_size * 0.5), int(cy)),                   # Right vertex
        QPoint(int(cx - icon_size * 0.3), int(cy + icon_size * 0.4)), # Bottom-left vertex
    ]
    poly = QPolygon(triangle_points)

    # Set brush and pen for the icon
    pen = painter.pen()
    pen.setColor(PLAY_ICON_COLOR)
    painter.setPen(pen)
    brush = painter.brush()
    brush.setColor(PLAY_ICON_COLOR)
    brush.setStyle(Qt.BrushStyle.SolidPattern)
    painter.setBrush(brush)
    painter.drawPolygon(poly) # Draw the triangle

    painter.end()
    return overlay_pixmap


class AssetDetailDialog(QDialog):
    """
    A dialog window displaying detailed information about a specific asset
    (template or extension) fetched from the Asset Library API.
    Allows initiating download/installation actions.
    """
    # Signals
    install_extension_requested = pyqtSignal(int) # Emits asset_id when install is requested for an extension
    template_download_finished = pyqtSignal(str, str) # Emits project_name, project_path when template creation succeeds

    def __init__(self, asset_id: Union[str, int], initial_data: dict, data_manager: DataManager, parent: Optional[QWidget] = None):
        """
        Initializes the AssetDetailDialog.

        Args:
            asset_id: The ID of the asset to display.
            initial_data: Basic data dictionary from the list view (used for initial display).
            parent: The parent widget.
        """
        super().__init__(parent)
        self.asset_id = str(asset_id) # Ensure asset_id is a string
        self.initial_data = initial_data
        self.full_asset_data: Optional[dict] = None # Will be populated by fetch_details
        asset_type = initial_data.get("type")
        logging.debug(f"AssetDetailDialog __init__: Asset ID={self.asset_id}, Initial Type='{asset_type}'")
        self.is_template: bool = asset_type == "project" # Determine type from initial data
        logging.debug(f"AssetDetailDialog __init__: self.is_template set to {self.is_template}")
        self.data_manager = data_manager # Salva l'istanza del DataManager

        # State for template download managed within this dialog
        self.download_thread: Optional[DownloadThread] = None
        self.template_extract_path: Optional[Path] = None

        # Image handling
        self.image_downloader_pool = QThreadPool()
        self.image_downloader_pool.setMaxThreadCount(3) # Limit concurrent image downloads
        # self.preview_labels = {} # No longer needed to cache labels here
        self.thumbnail_labels: Dict[str, QLabel] = {} # url -> QLabel (for thumbnail widgets)
        self.current_preview_url: Optional[str] = None # URL of the image currently shown in the main preview area
        self.asset_info: Dict[str, dict] = {} # Stores info about each preview {display_url: {type, thumb_url, link_url}}

        self.setWindowTitle(f"Asset Details: {initial_data.get('title', self.asset_id)}")
        self.setMinimumSize(850, 600)

        self.init_ui()
        self.populate_initial_data()
        # Fetch full details synchronously (consider making async later if needed)
        self.fetch_full_details()

    def init_ui(self):
        """Initializes the UI elements of the dialog."""
        main_layout = QVBoxLayout(self)
        content_layout = QHBoxLayout() # Main horizontal split

        # --- Left Panel (Textual Info) ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header: Icon and Title
        header_layout = QHBoxLayout()
        self.icon_label = QLabel("...")
        self.icon_label.setFixedSize(ICON_SIZE)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("background-color:#ddd; border:1px solid #aaa;")
        header_layout.addWidget(self.icon_label)
        self.title_label = QLabel(f"<b>{self.initial_data.get('title', 'Loading...')}</b>")
        self.title_label.setStyleSheet("font-size: 14pt;")
        self.title_label.setWordWrap(True)
        header_layout.addWidget(self.title_label, 1) # Title takes available space
        left_layout.addLayout(header_layout)

        # Info Grid (Author, License, Version, etc.)
        self.info_grid = QVBoxLayout() # Using QVBoxLayout for simplicity
        self.info_grid.setSpacing(4)
        self.author_label = QLabel("Author: Loading...")
        self.license_label = QLabel("License: Loading...")
        self.version_label = QLabel("Version: Loading...")
        self.godot_version_label = QLabel("Godot Version: Loading...")
        self.category_label = QLabel("Category: Loading...")
        self.support_label = QLabel("Support: Loading...")
        self.modified_label = QLabel("Last Modified: Loading...")

        self.info_grid.addWidget(self.author_label)
        self.info_grid.addWidget(self.license_label)
        self.info_grid.addWidget(self.version_label)
        self.info_grid.addWidget(self.godot_version_label)
        self.info_grid.addWidget(self.category_label)
        self.info_grid.addWidget(self.support_label)
        self.info_grid.addWidget(self.modified_label)
        left_layout.addLayout(self.info_grid)
        left_layout.addSpacing(10)

        # Description (Scrollable)
        left_layout.addWidget(QLabel("<b>Description:</b>"))
        self.description_edit = QTextEdit()
        self.description_edit.setReadOnly(True)
        self.description_edit.setText("Loading description...")
        left_layout.addWidget(self.description_edit, 1) # Takes vertical space

        content_layout.addWidget(left_panel, 1) # Left panel takes ~1/3 width

        # --- Right Panel (Previews) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Main Preview Area (using custom PreviewLabel)
        self.preview_area = PreviewLabel(self) # Pass self as parent
        right_layout.addWidget(self.preview_area, 1) # Takes more vertical space

        # Thumbnail Area (Horizontally Scrollable)
        right_layout.addWidget(QLabel("Previews:"))
        self.thumbnail_scroll_area = QScrollArea()
        self.thumbnail_scroll_area.setWidgetResizable(True)
        self.thumbnail_scroll_area.setFixedHeight(THUMBNAIL_SIZE.height() + 20) # Fixed height
        self.thumbnail_widget = QWidget()
        # Ensure the inner widget expands horizontally but has fixed height
        size_policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.thumbnail_widget.setSizePolicy(size_policy)
        self.thumbnail_widget.setFixedHeight(THUMBNAIL_SIZE.height() + 5)
        self.thumbnail_layout = QHBoxLayout(self.thumbnail_widget)
        self.thumbnail_layout.setAlignment(Qt.AlignmentFlag.AlignLeft) # Align thumbnails left
        self.thumbnail_scroll_area.setWidget(self.thumbnail_widget)
        right_layout.addWidget(self.thumbnail_scroll_area)

        content_layout.addWidget(right_panel, 2) # Right panel takes ~2/3 width

        main_layout.addLayout(content_layout, 1)

        # --- Download Status Bar (for Template downloads) ---
        self.download_status_frame = QFrame()
        self.download_status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        dl_status_layout = QHBoxLayout(self.download_status_frame)
        dl_status_layout.setContentsMargins(5, 2, 5, 2)
        self.dl_status_label = QLabel("Ready.")
        self.dl_progress_bar = QProgressBar()
        self.dl_progress_bar.setTextVisible(False)
        self.dl_cancel_btn = QPushButton("Cancel Download")
        dl_status_layout.addWidget(self.dl_status_label, 1)
        dl_status_layout.addWidget(self.dl_progress_bar)
        dl_status_layout.addWidget(self.dl_cancel_btn)
        self.download_status_frame.setVisible(False) # Hidden initially
        main_layout.addWidget(self.download_status_frame)
        self.dl_cancel_btn.clicked.connect(self._cancel_template_download)

        # --- Dialog Buttons ---
        self.button_box = QDialogButtonBox()
        # Action button text/action depends on asset type (set later)
        self.action_button = QPushButton("...") # Placeholder text
        self.action_button.setEnabled(False) # Disabled until details are loaded
        self.button_box.addButton(self.action_button, QDialogButtonBox.ButtonRole.AcceptRole)
        self.button_box.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
        self.button_box.accepted.connect(self.perform_action) # Connect Action button
        # Explicitly connect the rejected signal to the dialog's reject slot
        self.button_box.rejected.connect(self.reject)

        # --- Checkbox for Default Extension Installation (only for templates) ---
        self.install_defaults_cb = QCheckBox("Install default extensions (if available)")
        self.install_defaults_cb.setChecked(True)
        self.install_defaults_cb.setToolTip(
            "If selected, it will attempt to install globally marked extensions for auto-installation\n"
            "(Extensions tab > Checkbox column)"
        )
        # Hide checkbox if not a template
        self.install_defaults_cb.setVisible(self.is_template)
        # Add the checkbox to the MAIN layout, above the button_box
        if self.is_template:
            main_layout.insertWidget(main_layout.count() - 1, self.install_defaults_cb)

        main_layout.addWidget(self.button_box)

    def populate_initial_data(self):
        """Populates widgets with basic data available immediately from the list view."""
        logging.debug(f"Populating initial data for asset {self.asset_id}")
        self.title_label.setText(f"<b>{self.initial_data.get('title', f'ID: {self.asset_id}')}</b>")
        self.author_label.setText(f"Author: {self.initial_data.get('author', '?')} (ID: {self.initial_data.get('author_id', '?')})")
        self.license_label.setText(f"License: {self.initial_data.get('cost', '?')}")
        self.version_label.setText(f"Version: {self.initial_data.get('version_string', '?')} (internal: {self.initial_data.get('version', '?')})")
        self.godot_version_label.setText(f"Godot Version: {self.initial_data.get('godot_version', '?')}")
        self.category_label.setText(f"Category: {self.initial_data.get('category', '?')}")
        self.support_label.setText(f"Support: {self.initial_data.get('support_level', '?')}")

        # Format modification date
        modify_date_str = "?"
        try:
            modify_timestamp = self.initial_data.get("modify_date", "")
            if modify_timestamp:
                 if isinstance(modify_timestamp, (int, float)):
                      mod_dt = datetime.fromtimestamp(modify_timestamp)
                      modify_date_str = mod_dt.strftime("%d-%m-%Y %H:%M")
                 elif isinstance(modify_timestamp, str):
                      mod_dt = datetime.strptime(modify_timestamp, "%Y-%m-%d %H:%M:%S")
                      modify_date_str = mod_dt.strftime("%d-%m-%Y %H:%M")
        except (ValueError, TypeError, OSError): pass # Ignore parsing errors
        self.modified_label.setText(f"Last Modified: {modify_date_str}")

        # Load initial icon
        icon_url = self.initial_data.get("icon_url")
        if icon_url:
            self.start_image_download(icon_url, self.icon_label, ICON_SIZE)
        else:
            self.icon_label.setText("N/A")

    def fetch_full_details(self):
        """Fetches the complete asset details from the API."""
        # TODO: Consider making this asynchronous using a QThread to avoid blocking the UI.
        logging.info(f"Fetching full details for asset {self.asset_id}")
        self.full_asset_data = fetch_asset_details_sync(self.asset_id)

        if not self.full_asset_data:
            logging.error(f"Failed to retrieve details for asset {self.asset_id}")
            self.description_edit.setHtml("<font color='red'>Error retrieving full asset details.</font>")
            self.preview_area.clearPreview("Error loading previews.")
            self.action_button.setText("Error")
            self.action_button.setEnabled(False)
            QMessageBox.critical(self, "Details Error", f"Could not load details for asset ID {self.asset_id}.")
            return

        logging.debug(f"Full details received for {self.asset_id}")
        # Populate remaining fields / potentially overwrite initial data if more accurate
        self.description_edit.setHtml(self.full_asset_data.get("description", "No description available."))

        # *** DEBUG LOG ADDED ***
        logging.debug(f"AssetDetailDialog fetch_full_details: Current self.is_template = {self.is_template}")

        # Update labels that might be more accurate in full details
        self.title_label.setText(f"<b>{self.full_asset_data.get('title', self.initial_data.get('title', self.asset_id))}</b>")
        self.author_label.setText(f"Author: {self.full_asset_data.get('author', '?')} (ID: {self.full_asset_data.get('author_id', '?')})")
        self.license_label.setText(f"License: {self.full_asset_data.get('cost', '?')}")
        self.version_label.setText(f"Version: {self.full_asset_data.get('version_string', '?')} (internal: {self.full_asset_data.get('version', '?')})")
        self.godot_version_label.setText(f"Godot Version: {self.full_asset_data.get('godot_version', '?')}")
        self.category_label.setText(f"Category: {self.full_asset_data.get('category', '?')}")
        self.support_label.setText(f"Support: {self.full_asset_data.get('support_level', '?')}")
        try:
            modify_date_dt = datetime.strptime(self.full_asset_data.get("modify_date", ""), "%Y-%m-%d %H:%M:%S")
            self.modified_label.setText(f"Last Modified: {modify_date_dt.strftime('%d-%m-%Y %H:%M')}")
        except (ValueError, TypeError): self.modified_label.setText("Last Modified: ?")

        # *** DEBUG LOG MOVED ***
        logging.debug(f"AssetDetailDialog fetch_full_details: Action button text set to: '{self.action_button.text()}'")

        # Set action button text and tooltip based on asset type
        if self.is_template:
            self.action_button.setText("📥 Download && Create Project")
            self.action_button.setToolTip("Download this template and create a new local project.")
        else: # It's an extension/addon
            self.action_button.setText("🧩 Download && Install to Selected Project...")
            self.action_button.setToolTip("Download and install this extension into the currently selected project (see 'Projects' tab).")
        self.action_button.setEnabled(True) # Enable the action button now

        # Load preview images and thumbnails
        self.load_previews()

    def load_previews(self):
        """Loads preview thumbnails and sets up the main preview area."""
        if not self.full_asset_data: return
        previews = self.full_asset_data.get("previews", [])
        logging.debug(f"Found {len(previews)} previews for asset {self.asset_id}")

        # Clear previous thumbnails and data
        while self.thumbnail_layout.count():
            item = self.thumbnail_layout.takeAt(0)
            if item and item.widget(): item.widget().deleteLater()
        self.thumbnail_labels.clear()
        self.asset_info.clear()
        self.current_preview_url = None

        if not previews:
            self.preview_area.clearPreview("No previews available.")
            self.thumbnail_scroll_area.setVisible(False)
            return

        self.thumbnail_scroll_area.setVisible(True)
        first_image_url_to_show: Optional[str] = None # Store URL of the first *image* preview

        for i, preview_info in enumerate(previews):
            link_url = preview_info.get("link") # URL of the full resource (image or video page)
            thumb_url = preview_info.get("thumbnail") # URL of the thumbnail image (might be missing)
            preview_type = preview_info.get("type", "image").lower()

            # Determine the URL to use for display (main preview/video link) and thumbnail download
            display_url = link_url if link_url else thumb_url # Prefer link for action
            thumb_download_url = thumb_url if thumb_url else link_url # Prefer thumb for download, fallback to link

            if not display_url: # Skip if no URL is available
                logging.warning(f"Preview {i} skipped: No valid URL found.")
                continue

            # Store info about this preview, keyed by the display_url
            self.asset_info[display_url] = {
                "type": preview_type,
                "thumb_url": thumb_download_url, # URL to download for the thumbnail widget
                "link_url": display_url, # URL to use when clicked (show image or open video)
            }

            # Create thumbnail label
            thumb_label = QLabel("...")
            thumb_label.setFixedSize(THUMBNAIL_SIZE)
            thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb_label.setStyleSheet("background-color:#ccc; border:1px solid #aaa; margin: 2px;")
            thumb_label.setCursor(Qt.CursorShape.PointingHandCursor)
            thumb_label.setProperty("displayUrl", display_url) # Store the URL to show/open on click

            if preview_type == "image":
                thumb_label.setToolTip(f"View image {i+1}")
                thumb_label.mousePressEvent = lambda event, url=display_url: self.show_preview_image(url)
                thumb_label.setProperty("isVideoThumb", False)
                if first_image_url_to_show is None: # Store the first image URL
                    first_image_url_to_show = display_url
            elif preview_type == "video":
                thumb_label.setToolTip(f"Open video {i+1} in browser")
                thumb_label.mousePressEvent = lambda event, url=display_url: self._open_video_url(url)
                thumb_label.setProperty("isVideoThumb", True)
                # Don't show "..." if thumbnail needs download, wait for overlay
                if not thumb_url: thumb_label.setText("")
            else:
                logging.warning(f"Unrecognized preview type: {preview_type}. Skipping.")
                continue

            self.thumbnail_layout.addWidget(thumb_label)
            # Map the URL used for *downloading* the thumb to the label widget
            if thumb_download_url:
                 self.thumbnail_labels[thumb_download_url] = thumb_label
                 # Start download for the thumbnail image
                 self.start_image_download(thumb_download_url, thumb_label, THUMBNAIL_SIZE)
            else:
                 thumb_label.setText("No Thumb") # Indicate missing thumbnail URL


        self.thumbnail_layout.addStretch() # Push thumbnails left

        # Show the first *image* preview initially, or a placeholder
        if first_image_url_to_show:
            self.show_preview_image(first_image_url_to_show)
        elif self.asset_info: # If only videos were found
            self.preview_area.clearPreview("(Select a thumbnail to view)")
        else: # No valid previews at all
            self.preview_area.clearPreview("No valid previews found.")

    def _open_video_url(self, video_url: str):
        """Opens the video URL in the default web browser."""
        if not video_url:
            logging.warning("Attempted to open an empty video URL.")
            return
        logging.info(f"Opening video URL in browser: {video_url}")
        url = QUrl(video_url)
        if not QDesktopServices.openUrl(url):
            logging.error(f"Failed to open video URL: {video_url}")
            QMessageBox.warning(self, "Error Opening Video", f"Could not open the video URL:\n{video_url}")

    def start_image_download(self, url: str, label: QLabel, target_size: QSize):
        """Starts an asynchronous download for a single image (icon, thumbnail, or preview)."""
        if not url:
            label.setText("URL Err")
            label.setStyleSheet("background-color:#fdd;")
            return

        logging.debug(f"Starting image download: {url} for label tooltip='{label.toolTip()}'")
        # Use URL itself as the ID for the downloader in this context
        downloader = IconDownloader(url, url)
        # Connect signals using lambdas to pass necessary context
        downloader.signals.icon_ready.connect(
            lambda img_id, path, lbl=label, sz=target_size, original_url=url:
            self.on_image_ready(lbl, path, sz, original_url)
        )
        downloader.signals.error.connect(
            lambda img_id, err_msg, lbl=label:
            self.on_image_error(lbl, err_msg)
        )
        self.image_downloader_pool.start(downloader)

    @pyqtSlot(QLabel, str, QSize, str)
    def on_image_ready(self, label: QLabel, local_path: str, target_size: QSize, original_url: str):
        """Slot called when an image (icon, thumb, preview) is ready."""
        logging.debug(f"Image ready for tooltip='{label.toolTip()}' url='{original_url}' path='{local_path}'")
        pixmap = QPixmap(local_path)
        if pixmap.isNull():
            logging.warning(f"Loaded pixmap is null for {label.toolTip()} from {local_path}")
            label.setText("Err")
            label.setStyleSheet("background-color:#fdd; border:1px solid red; color: red; qproperty-alignment: AlignCenter;")
            return

        is_main_preview_label = isinstance(label, PreviewLabel) # Check if it's the main preview area
        is_video_thumb_widget = label.property("isVideoThumb") or False # Check if it's a video thumbnail

        final_pixmap = pixmap # Start with the original downloaded pixmap

        # Apply video overlay if it's a video thumbnail label
        if is_video_thumb_widget and not is_main_preview_label:
            logging.debug(f"Adding video overlay to thumbnail: {original_url}")
            final_pixmap = _add_video_overlay(pixmap)

        # Handle the main preview area specifically
        if is_main_preview_label:
            # Check if the currently selected preview corresponds to this downloaded image
            if self.current_preview_url:
                current_asset_info = self.asset_info.get(self.current_preview_url)
                if current_asset_info:
                    # If the current selection is a VIDEO, apply overlay to its THUMBNAIL
                    if current_asset_info["type"] == "video" and original_url == current_asset_info["thumb_url"]:
                        logging.debug(f"Applying video thumbnail with overlay to main preview area for {self.current_preview_url}")
                        final_pixmap = _add_video_overlay(pixmap)
                        label.setVideoPreview(final_pixmap, self.current_preview_url) # Use specialized method
                    # If the current selection is an IMAGE, apply the image directly
                    elif current_asset_info["type"] == "image" and original_url == self.current_preview_url:
                        logging.debug(f"Applying image to main preview area: {original_url}")
                        label.setImagePreview(final_pixmap) # Use specialized method
                    else:
                         logging.debug(f"Image {original_url} downloaded for main preview, but it doesn't match current selection {self.current_preview_url}. Ignoring update.")
                else:
                     logging.warning(f"Cannot determine type for current preview URL {self.current_preview_url} while processing {original_url}")
            else:
                 logging.debug(f"Image {original_url} downloaded for main preview, but no preview is currently selected. Ignoring update.")

        # Handle regular labels (icon or image thumbnails)
        else:
            scaled_pixmap = final_pixmap.scaled(
                target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            label.setPixmap(scaled_pixmap)
            label.setStyleSheet("") # Clear placeholder style
            label.setText("")

    @pyqtSlot(QLabel, str)
    def on_image_error(self, label: QLabel, error_message: str):
        """Slot called if an image download fails."""
        logging.error(f"Image download failed for {label.toolTip()}: {error_message}")
        label.setText("Fail")
        label.setToolTip(f"Failed to load image:\n{error_message}")
        label.setStyleSheet("background-color:#fdd; border:1px solid red; color: red; qproperty-alignment: AlignCenter;")

    @pyqtSlot(str)
    def show_preview_image(self, display_url: str):
        """Shows the preview (image or video placeholder) for the given display URL."""
        logging.info(f"Request to show preview for: {display_url}")
        self.current_preview_url = display_url # Store the URL of the preview to show

        asset_info = self.asset_info.get(display_url)
        if not asset_info:
            logging.error(f"No asset info found for preview URL: {display_url}")
            self.preview_area.clearPreview("Error: Preview data missing.")
            return

        preview_type = asset_info["type"]
        thumb_download_url = asset_info["thumb_url"] # URL of the thumbnail to download

        if preview_type == "image":
            # For images, start download of the main image (link_url)
            logging.debug(f"Preview type is Image. Starting download for main preview: {display_url}")
            self.preview_area.clearPreview("Loading image...") # Show loading text
            self.start_image_download(display_url, self.preview_area, self.preview_area.size())
        elif preview_type == "video":
            # For videos, start download of the THUMBNAIL (thumb_download_url)
            # The on_image_ready handler will apply the overlay and set video state
            logging.debug(f"Preview type is Video. Starting download for thumbnail: {thumb_download_url}")
            self.preview_area.clearPreview("Loading video preview...")
            if thumb_download_url:
                self.start_image_download(thumb_download_url, self.preview_area, self.preview_area.size())
            else:
                # If no thumbnail URL, show placeholder immediately
                logging.warning(f"No thumbnail URL for video {display_url}. Showing placeholder.")
                self.preview_area.clearPreview("(Video - No thumbnail available)")
                # Still set the video URL for clicking
                self.preview_area._video_url_to_open = display_url
                self.preview_area.setCursor(Qt.CursorShape.PointingHandCursor)
                self.preview_area.setToolTip(f"Click to open video:\n{display_url}")
        else:
             logging.warning(f"Unknown preview type '{preview_type}' for URL {display_url}")
             self.preview_area.clearPreview("Unknown preview type.")


    def perform_action(self):
        """Performs the main action (Download Template or Signal Install Extension)."""
        if not self.full_asset_data:
            logging.error("Action button clicked but full asset data is not loaded.")
            return

        if self.is_template:
            self._start_template_download()
        else:
            # Emit signal for the main window to handle extension installation
            logging.info(f"Emitting install_extension_requested signal for ID: {self.asset_id}")
            try:
                asset_id_int = int(self.asset_id)
                self.install_extension_requested.emit(asset_id_int)
                # Optionally close the dialog after emitting the signal
                # self.accept()
            except ValueError:
                 logging.error(f"Invalid asset ID format for signal emission: {self.asset_id}")
                 QMessageBox.critical(self, "Error", "Invalid asset ID encountered.")


    def _start_template_download(self):
        """Handles the process of downloading and extracting a template project."""
        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Template download already in progress.")
            return

        if not self.full_asset_data: # Should be loaded by now, but check again
             QMessageBox.critical(self, "Error", "Asset details not fully loaded.")
             return

        asset_title = self.full_asset_data.get("title", f"template_{self.asset_id}")
        download_url = self.full_asset_data.get("download_url")
        if not download_url:
            logging.info("Template download cancelled: No download URL found.")
            return

        # --- MODIFICA: Chiedi Nome Progetto --- 
        suggested_name = "".join(c if c.isalnum() or c in ["_", "-"] else "_" for c in asset_title).strip("_")
        if not suggested_name: suggested_name = f"template_{self.asset_id}"

        project_name_input, ok = QInputDialog.getText(self, "Nome Progetto",
                                               "Inserisci il nome per il nuovo progetto:",
                                               QLineEdit.EchoMode.Normal,
                                               suggested_name)

        if not ok or not project_name_input or not project_name_input.strip():
            QMessageBox.warning(self, "Warning", "Please enter a valid project name.")
            logging.info("Template creation cancelled: No project name entered.")
            return

        project_name = project_name_input.strip()
        # Sanifica il nome per usarlo come nome cartella
        folder_name = "".join(c if c.isalnum() or c in ["_", "-"] else "_" for c in project_name).strip("_")
        folder_name = folder_name.lower() # Converti in minuscolo
        if not folder_name: folder_name = f"progetto_{self.asset_id}" # Fallback se sanificazione fallisce
        # --- FINE MODIFICA ---

        # --- Get Parent Directory ---
        # Attempt to get DataManager from parent to find default folder
        parent_widget = self.parent()
        data_manager_instance = None
        if hasattr(parent_widget, 'data_manager') and isinstance(parent_widget.data_manager, DataManager):
            data_manager_instance = parent_widget.data_manager

        start_dir = str(Path.home()) # Default to home
        if data_manager_instance:
            default_folder_str = data_manager_instance.get_default_projects_folder()
            if default_folder_str and Path(default_folder_str).is_dir():
                start_dir = default_folder_str
        # --- End Modification ---

        parent_dir_str = QFileDialog.getExistingDirectory(
            self, f"Select Parent Folder for '{project_name}' Project", start_dir # Usa il nome inserito
        )
        if not parent_dir_str:
            logging.info("Template download cancelled: No parent directory selected.")
            return

        # --- MODIFICA: Verifica Conflitto Nome Cartella ---
        parent_dir = Path(parent_dir_str)
        target_project_path = parent_dir / folder_name # Usa il nome sanificato dall'utente

        if target_project_path.exists():
            logging.warning(f"Conflitto nome progetto: La cartella '{folder_name}' esiste già in '{parent_dir_str}'.")
            QMessageBox.warning(self, "Conflitto Nome Progetto",
                                f"La cartella '{folder_name}' esiste già in questa directory.\n"
                                f"Per favore, scegli un nome progetto diverso o una cartella genitore diversa.")
            return
        # --- FINE MODIFICA ---

        self.template_extract_path = target_project_path # Store path for extraction

        # --- Setup UI for Download ---
        self.download_status_frame.setVisible(True)
        self.dl_status_label.setText(f"Downloading '{asset_title}'...")
        self.dl_progress_bar.setValue(0)
        self.dl_progress_bar.setRange(0, 100) # Start determinate
        self.dl_progress_bar.setVisible(True)
        self.dl_cancel_btn.setEnabled(True)
        self.dl_cancel_btn.setVisible(True)
        self.action_button.setEnabled(False) # Disable main action button
        close_button = self.button_box.button(QDialogButtonBox.StandardButton.Close)
        if close_button: close_button.setEnabled(False) # Disable Close button
        QApplication.processEvents()

        # --- Start Download Thread ---
        try:
            # Use system's temporary directory + specific subfolder
            system_temp_dir = Path(tempfile.gettempdir())
            temp_dir = system_temp_dir / "godot_launcher_temp" / "godot_templates"
            temp_dir.mkdir(parents=True, exist_ok=True)
            logging.debug(f"Using temporary download directory for template: {temp_dir}")
        except Exception as e:
            logging.exception("Failed to create temporary download directory for template.")
            QMessageBox.critical(self, "Error", f"Could not create temporary download directory:\n{e}")
            self._reset_template_download_ui() # Reset UI if temp dir fails
            return

        # Use timestamp in temp filename to avoid potential conflicts
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        zip_filename = f"template_{self.asset_id}_{timestamp}.zip"
        zip_save_path = temp_dir / zip_filename

        self.download_thread = DownloadThread(download_url, str(zip_save_path))
        # Connect signals
        self.download_thread.progress.connect(
            lambda p: self.dl_progress_bar.setValue(p) if p >= 0 else self.dl_progress_bar.setRange(0, 0)
        )
        self.download_thread.status_update.connect(
            lambda msg: self.dl_status_label.setText(f"Download: {msg}")
        )
        self.download_thread.finished.connect(self._handle_template_download_finished_dialog)
        self.download_thread.start()

    def _handle_template_download_finished_dialog(self, zip_path_str: Optional[str], error_msg: Optional[str]):
        """Handles template download completion and starts extraction within the dialog."""
        zip_path = Path(zip_path_str) if zip_path_str else None
        asset_title = self.full_asset_data.get("title", f"template_{self.asset_id}") if self.full_asset_data else f"template_{self.asset_id}"

        # Check for download errors
        if error_msg or not zip_path or not zip_path.exists():
            QMessageBox.critical(self, "Download Error", f"Failed to download template '{asset_title}':\n{error_msg or 'Downloaded file not found'}")
            self._reset_template_download_ui()
            if zip_path: self._cleanup_zip(zip_path) # Attempt cleanup even on error
            return

        # --- Start Extraction ---
        self.dl_status_label.setText(f"Extracting '{asset_title}'...")
        self.dl_progress_bar.setRange(0, 0) # Indeterminate for extraction
        self.dl_cancel_btn.setEnabled(False) # Cannot cancel extraction easily
        QApplication.processEvents()

        try:
            if not self.template_extract_path:
                raise IOError("Extraction path is not defined.")

            # Perform extraction
            extract_zip(zip_path, self.template_extract_path, remove_common_prefix=True)

            final_project_name = self.template_extract_path.name
            final_project_path_str = str(self.template_extract_path.resolve())
            logging.info(f"Template downloaded and extracted: '{final_project_name}' at '{final_project_path_str}'")

            # --- Update project.godot with the correct name ---
            project_file = self.template_extract_path / "project.godot"
            if project_file.is_file():
                try:
                    logging.info(f"Updating project name in {project_file} to '{final_project_name}'")
                    content = []
                    found_name = False
                    with open(project_file, "r", encoding="utf-8") as f_read:
                        content = f_read.readlines()

                    with open(project_file, "w", encoding="utf-8") as f_write:
                        for line in content:
                            stripped_line = line.strip()
                            if stripped_line.startswith("config/name"):
                                f_write.write(f'config/name=\"{final_project_name}\"\\n')
                                found_name = True
                            else:
                                f_write.write(line)
                    if not found_name:
                         logging.warning(f"'config/name' line not found in {project_file}. Project name not updated.")

                except Exception as proj_update_err:
                    logging.error(f"Failed to update project name in {project_file}: {proj_update_err}")
                    # Decide if this is critical. Maybe just log a warning?
                    QMessageBox.warning(self, "Project Update Warning", f"Could not update the project name in 'project.godot'.\\nPlease check the file manually.\\n\\nError: {proj_update_err}")
            else:
                logging.warning(f"Could not find 'project.godot' in extracted template at {self.template_extract_path}. Project name not updated.")

            # --- Install Default Extensions (if checkbox is checked) ---
            extensions_installed_names = []
            install_success = True # Assume success unless proven otherwise
            if self.install_defaults_cb.isChecked():
                auto_install_ids = self.data_manager.get_auto_install_extensions()
                if auto_install_ids:
                    logging.info(f"Attempting to auto-install {len(auto_install_ids)} extensions into {self.template_extract_path}")
                    self.dl_status_label.setText(f"Installing default extensions...")
                    self.dl_progress_bar.setRange(-1, -1) # Indeterminate for installation
                    QApplication.processEvents()
                    try:
                        # Call install_extensions_logic
                        # NOTE: Needs 'install_extensions_logic' imported from project_handler
                        # NOTE: Assuming sync operation for simplicity here
                        install_extensions_logic(
                            asset_ids=auto_install_ids,
                            project_path=self.template_extract_path,
                            data_manager=self.data_manager,
                            status_label=None, # Dialog has its own status mechanism
                            progress_bar=None, # Dialog has its own progress bar
                            cancel_button=None # Pass None for the cancel button
                        )
                        # Assuming success if no exception is raised
                        # We can't easily get the names here without modifying install_extensions_logic
                        logging.info("Auto-install logic completed without raising an exception.")
                        # Potentially list installed addons by scanning folder?
                        addons_folder = self.template_extract_path / "addons"
                        if addons_folder.exists():
                            extensions_installed_names = [d.name for d in addons_folder.iterdir() if d.is_dir()]

                    except Exception as install_err:
                        install_success = False
                        logging.exception(f"Error during auto-installation of extensions for {self.template_extract_path.name}")
                        # Show error in dialog status bar?
                        error_details = f"Extension installation error: {install_err}"
                        self.dl_status_label.setText(f"<font color='red'>{error_details}</font>")
                        # Don't show a separate QMessageBox here, let the final status handle it.
                else:
                    logging.info("Auto-install checkbox checked, but no extensions marked for auto-install.")
            else:
                logging.info("Auto-install checkbox not checked, skipping extension installation.")

            # --- Finalize and Emit Signal ---
            if install_success:
                success = True
                final_msg = f"Template '{asset_title}' created as '{final_project_name}'."
                if extensions_installed_names:
                     final_msg += f" Detected addons: {', '.join(extensions_installed_names)}."
                logging.info(f"Emitting template_download_finished: Name='{final_project_name}', Path='{str(self.template_extract_path)}'")
                # Emit signal *after* everything is done (including optional installs)
                self.template_download_finished.emit(final_project_name, str(self.template_extract_path))
            else:
                success = False
                final_msg = "Template creation completed, but error during default extensions installation."

            QMessageBox.information(self, "Success", final_msg)
            self.accept() # Close the dialog successfully

        except (FileNotFoundError, ValueError, IOError, zipfile.BadZipFile, Exception) as e:
            logging.exception(f"Template extraction failed for '{asset_title}' in dialog")
            QMessageBox.critical(self, "Extraction Error", f"Failed to extract template '{asset_title}':\n{e}")
            # Attempt to clean up partially created folder
            if self.template_extract_path and self.template_extract_path.exists():
                try:
                    logging.info(f"Attempting to remove partially created folder: {self.template_extract_path}")
                    shutil.rmtree(self.template_extract_path)
                except OSError as rm_err:
                    logging.warning(f"Failed to remove partial folder {self.template_extract_path}: {rm_err}")
            self._reset_template_download_ui() # Reset UI after error
        finally:
            # Always clean up the downloaded ZIP file
             self._cleanup_zip(zip_path)
             # Reset UI only if not closed successfully
             if not self.result() == QDialog.DialogCode.Accepted:
                  self._reset_template_download_ui()


    def _cancel_template_download(self):
        """Cancels the ongoing template download."""
        if self.download_thread and self.download_thread.isRunning():
            logging.info("Requesting template download cancellation...")
            self.download_thread.stop()
            self.dl_status_label.setText("Cancelling download...")
            self.dl_cancel_btn.setEnabled(False)
            # The finished signal will still fire, triggering cleanup
        else:
            logging.warning("Cancel template download clicked, but no download was active.")

    def _reset_template_download_ui(self):
        """Resets the template download UI elements to their default state."""
        logging.debug("Resetting template download UI in dialog.")
        self.download_status_frame.setVisible(False)
        self.dl_status_label.setText("Ready.")
        self.dl_progress_bar.setValue(0)
        self.dl_progress_bar.setRange(0, 100)
        self.dl_cancel_btn.setEnabled(False)
        # Re-enable main action button and Close button
        self.action_button.setEnabled(True if self.full_asset_data else False)
        close_button = self.button_box.button(QDialogButtonBox.StandardButton.Close)
        if close_button: close_button.setEnabled(True)
        # Clear state variables
        self.download_thread = None
        self.template_extract_path = None

    def _cleanup_zip(self, zip_path: Optional[Path]):
         """Safely deletes the downloaded ZIP file and its temporary directory if empty."""
         if zip_path and zip_path.exists():
             try:
                 logging.info(f"Removing temporary ZIP: {zip_path}")
                 zip_path.unlink()
                 temp_dir = zip_path.parent
                 # Attempt to remove the parent temp directory if it's empty
                 if temp_dir.exists() and not any(temp_dir.iterdir()):
                     temp_dir.rmdir()
                     logging.info(f"Removed empty temporary directory: {temp_dir}")
             except OSError as e:
                 logging.warning(f"Failed to clean up temporary file/directory {zip_path}: {e}")


    def reject(self):
        """Handles dialog closure, ensuring background tasks are stopped."""
        logging.info(f"Closing asset detail dialog for asset {self.asset_id}")
        # Cancel template download if running
        if self.download_thread and self.download_thread.isRunning():
            self._cancel_template_download()
        # Stop image downloads
        self.image_downloader_pool.clear() # Remove queued tasks
        self.image_downloader_pool.waitForDone(100) # Wait briefly for active tasks
        super().reject()


class PreviewLabel(QLabel):
    """
    A QLabel subclass specialized for displaying asset previews (images or video thumbnails)
    and handling clicks to open video URLs.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        """Initializes the PreviewLabel."""
        super().__init__(parent)
        self._video_url_to_open: Optional[str] = None # URL to open if it's a video preview
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(200) # Set a reasonable minimum height
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored) # Allow stretching
        self.clearPreview("Loading preview...") # Initial state

    def setPixmap(self, pixmap: QPixmap):
        """Overrides setPixmap to ensure proper scaling."""
        if pixmap.isNull():
            # Let QLabel handle null pixmap (e.g., clear or show text)
            super().setPixmap(pixmap)
        else:
            # Scale pixmap to fit the label size while keeping aspect ratio
            scaled_pixmap = pixmap.scaled(
                self.size(), # Use current label size for scaling
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            super().setPixmap(scaled_pixmap)

    def setVideoPreview(self, thumbnail_pixmap: QPixmap, video_url: str):
        """Displays a video thumbnail with overlay and sets the URL to open on click."""
        self._video_url_to_open = video_url
        overlay_pixmap = _add_video_overlay(thumbnail_pixmap)
        self.setPixmap(overlay_pixmap) # setPixmap handles scaling
        self.setText("") # Ensure no text is shown over the pixmap
        self.setToolTip(f"Click to open video:\n{video_url}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("") # Clear placeholder style

    def setImagePreview(self, image_pixmap: QPixmap):
        """Displays a regular image preview and resets video state."""
        self._video_url_to_open = None # Not a video
        self.setPixmap(image_pixmap) # setPixmap handles scaling
        self.setText("")
        self.setToolTip("") # Clear video tooltip
        self.unsetCursor()
        self.setStyleSheet("") # Clear placeholder style

    def clearPreview(self, text: str = ""):
        """Clears the preview area, resets state, and optionally shows text."""
        self._video_url_to_open = None
        self.setPixmap(QPixmap()) # Clear existing pixmap
        self.setText(text)
        self.setToolTip("")
        self.unsetCursor()
        # Reset to default placeholder style
        self.setStyleSheet("background-color:#eee; border:1px solid #ccc; color: gray;")

    def mousePressEvent(self, ev: QMouseEvent):
        """Handles left-clicks to open the video URL if set."""
        if ev.button() == Qt.MouseButton.LeftButton and self._video_url_to_open:
            logging.info(f"PreviewLabel clicked, opening video URL: {self._video_url_to_open}")
            url = QUrl(self._video_url_to_open)
            if not QDesktopServices.openUrl(url):
                logging.error(f"Failed to open video URL via QDesktopServices: {self._video_url_to_open}")
                QMessageBox.warning(self, "Error Opening Video", f"Could not open the video URL:\n{self._video_url_to_open}")
        else:
            # Pass other events (e.g., right-clicks) to the base class
            super().mousePressEvent(ev)

    def resizeEvent(self, event):
        """Re-scales the pixmap when the label is resized."""
        # Check if there's a valid pixmap before trying to rescale
        if self.pixmap() and not self.pixmap().isNull():
             # We need the original pixmap to rescale correctly, but QLabel doesn't store it.
             # A possible workaround is to store the original pixmap or path,
             # but for simplicity, we might just re-trigger the download/display logic
             # if perfect scaling on resize is crucial.
             # For now, let's just call the base implementation.
             # If scaling looks bad on resize, this needs refinement.
             # Example refinement: Store original pixmap in a member variable.
             # if hasattr(self, '_original_pixmap') and self._original_pixmap:
             #     self.setPixmap(self._original_pixmap) # This triggers scaling in setPixmap override
             pass
        super().resizeEvent(event)
