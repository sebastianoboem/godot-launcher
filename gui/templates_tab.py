# -*- coding: utf-8 -*-
# gui/templates_tab.py

import logging
import shutil
from datetime import datetime
from pathlib import Path
import time
from typing import Any, Optional, Dict

from PyQt6.QtCore import QObject, QSize, Qt, QThreadPool, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QSpacerItem,
    QSizePolicy,
)
from gui.asset_detail_dialog import AssetDetailDialog
from gui.common_widgets import ClickableAssetFrame
from gui.styles import (  # Import of new styles
    COLORS, BUTTON_STYLE, 
    PRIMARY_BUTTON_STYLE,
    FRAME_STYLE, GROUP_BOX_STYLE,
    CHECKBOX_STYLE, INPUT_STYLE,
    PROGRESS_BAR_STYLE,
)

# Import necessary modules and classes
from api_clients import ApiFetchThread, fetch_asset_details_sync
from data_manager import DataManager # Use the DataManager class
from utils import DownloadThread, IconDownloader, extract_zip, ICON_SIZE, log_and_show_error
from project_handler import get_godot_version_string, ExtensionInstaller, install_extensions_logic # Importa la funzione corretta


class TemplatesTab(QWidget):
    """
    QWidget for the 'Templates' tab, allowing users to browse, search,
    and create new projects from Godot project templates available in the Asset Library.
    """
    # Signal emitted when a project is successfully created from a template
    # Provides the new project's name and its path string
    # DEPRECATED - This signal is now emitted by AssetDetailDialog directly
    # project_created_from_template = pyqtSignal(str, str)

    # Signal emitted when the AssetDetailDialog is shown, passing the dialog instance
    asset_detail_dialog_shown = pyqtSignal(AssetDetailDialog)

    status_message = pyqtSignal(str, int) # Emitted to show messages in the main window status bar (message, timeout_ms)

    def __init__(self, data_manager: DataManager):
        """
        Initializes the TemplatesTab.

        Args:
            data_manager: The central DataManager instance.
        """
        super().__init__()
        self.data_manager = data_manager # Store DataManager instance
        self.asset_widgets: Dict[str, ClickableAssetFrame] = {} # Stores asset frames by ID
        self.icon_labels: Dict[str, QLabel] = {} # Stores icon labels by asset ID
        self.thread_pool = QThreadPool() # Thread pool for icon downloads
        self.thread_pool.setMaxThreadCount(4) # Limit concurrent icon downloads
        self.api_thread: Optional[ApiFetchThread] = None # Holds the current API search thread
        self.download_thread: Optional[DownloadThread] = None # Holds the current template download thread
        self.current_operation_asset_id: Optional[str] = None # ID of asset being downloaded/created
        self.current_project_creation_path: Optional[Path] = None # Path where the new project is being created
        self.current_page: int = 0 # Current page number (0-based) for API results
        self.total_pages: int = 0 # Total pages available from the last API search
        self.total_items: int = 0 # Total items available from the last API search

        self.init_ui()
        self.search_assets() # Perform initial search on startup

    def init_ui(self):
        """Initializes the user interface elements of the tab."""
        layout = QVBoxLayout(self)
        
        # Titolo con stile moderno
        title_label = QLabel("<h2>Explore Project Templates</h2>")
        title_label.setStyleSheet(f"color: {COLORS['text_primary']}; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # --- Filters/Sorting Group ---
        filter_group = QGroupBox("Filter / Sorting")
        filter_group.setStyleSheet(GROUP_BOX_STYLE)
        filter_layout = QHBoxLayout(filter_group)
        
        # Etichetta di ricerca con stile
        filter_layout.addWidget(QLabel("Search:"))
        
        # Campo di ricerca con stile
        self.search_edit = QLineEdit()
        self.search_edit.setStyleSheet(INPUT_STYLE)
        self.search_edit.setPlaceholderText("e.g., Platformer, RPG Kit...")
        filter_layout.addWidget(self.search_edit, 2) # Search takes more space
        
        # Etichetta di ordinamento con stile
        filter_layout.addWidget(QLabel("Sort by:"))
        
        # Combobox di ordinamento con stile
        self.sort_combo = QComboBox()
        self.sort_combo.setStyleSheet(INPUT_STYLE)
        self.sort_combo.addItems(
            ["Relevance", "Recent Update", "Best Rating", "Name (A-Z)"]
        )
        filter_layout.addWidget(self.sort_combo, 1)
        
        # Etichetta supporto con stile
        filter_layout.addWidget(QLabel("Support:"))
        
        # Checkbox con stile
        self.support_community_cb = QCheckBox("Community")
        self.support_community_cb.setStyleSheet(CHECKBOX_STYLE)
        self.support_community_cb.setToolTip("Community Supported")
        self.support_community_cb.setChecked(True)
        
        self.support_official_cb = QCheckBox("Official")
        self.support_official_cb.setStyleSheet(CHECKBOX_STYLE)
        self.support_official_cb.setToolTip("Officially Supported")
        
        self.support_testing_cb = QCheckBox("Testing")
        self.support_testing_cb.setStyleSheet(CHECKBOX_STYLE)
        self.support_testing_cb.setToolTip("Testing / Experimental")
        
        filter_layout.addWidget(self.support_community_cb)
        filter_layout.addWidget(self.support_official_cb)
        filter_layout.addWidget(self.support_testing_cb)
        
        # Bottone di ricerca con stile
        self.search_button = QPushButton("🔍 Search Templates")
        self.search_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        filter_layout.addWidget(self.search_button)
        layout.addWidget(filter_group)

        # --- Results Scroll Area ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.StyledPanel)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {COLORS["bg_content"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 4px;
            }}
        """)
        
        self.results_widget = QWidget() # Container for results layout
        self.results_widget.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        
        self.results_layout = QVBoxLayout(self.results_widget) # Layout to hold asset widgets
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.results_layout.setSpacing(10)
        self.scroll_area.setWidget(self.results_widget)
        layout.addWidget(self.scroll_area, 1) # Scroll area takes available vertical space

        # Add a spacer to push results up if there are few
        spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.results_layout.addSpacerItem(spacer)

        # --- Status Bar / Pagination Frame ---
        self.status_frame = QFrame()
        self.status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.status_frame.setStyleSheet(FRAME_STYLE)
        
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(5, 2, 5, 2)
        
        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(PROGRESS_BAR_STYLE)
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet(BUTTON_STYLE)
        self.cancel_button.setVisible(False)

        # Pagination Controls Widget
        self.pagination_widget = QWidget()
        self.pagination_widget.setStyleSheet(f"background-color: {COLORS['bg_content']};")
        pagination_layout = QHBoxLayout(self.pagination_widget)
        pagination_layout.setContentsMargins(0, 0, 0, 0)
        
        self.prev_page_btn = QPushButton("<< Previous")
        self.prev_page_btn.setStyleSheet(BUTTON_STYLE)
        
        self.next_page_btn = QPushButton("Next >>")
        self.next_page_btn.setStyleSheet(BUTTON_STYLE)
        
        self.page_info_label = QLabel("Page - / -")
        self.page_info_label.setStyleSheet(f"color: {COLORS['text_primary']};")
        
        self.prev_page_btn.setEnabled(False)
        self.next_page_btn.setEnabled(False)
        pagination_layout.addWidget(self.prev_page_btn)
        pagination_layout.addWidget(self.page_info_label, 0, Qt.AlignmentFlag.AlignCenter)
        pagination_layout.addWidget(self.next_page_btn)
        self.pagination_widget.setVisible(False) # Hide initially

        # Add widgets to status layout
        status_layout.addWidget(self.status_label, 1) # Status label takes available space
        status_layout.addWidget(self.pagination_widget)
        status_layout.addWidget(self.progress_bar)
        status_layout.addWidget(self.cancel_button)
        layout.addWidget(self.status_frame)

        # --- Connect Signals ---
        self.search_button.clicked.connect(lambda: self.search_assets(page=0)) # Search starts from page 0
        self.search_edit.returnPressed.connect(lambda: self.search_assets(page=0))
        self.cancel_button.clicked.connect(self.cancel_current_operation)
        self.prev_page_btn.clicked.connect(self.go_to_previous_page)
        self.next_page_btn.clicked.connect(self.go_to_next_page)

    def search_assets(self, page: int = 0):
        """Initiates an API search for project templates based on current filters."""
        if self.api_thread and self.api_thread.isRunning():
            logging.warning("API search request ignored: Another search is already running.")
            return # Prevent concurrent searches

        # Reset page number if starting a new search (page=0)
        self.current_page = page

        # Get Godot version filter from DataManager's default path
        current_godot_path = self.data_manager.get_godot_path()
        godot_version_filter = get_godot_version_string(current_godot_path)

        logging.info(
            f"Starting template search - Page: {self.current_page}, Godot Version Filter: {godot_version_filter}"
        )
        self._clear_results() # Clear previous results

        # Get search parameters from UI
        query = self.search_edit.text().strip()
        sort_map = {
            "Recent Update": "updated",
            "Best Rating": "rating",
            "Name (A-Z)": "name",
            "Relevance": "", # API default
        }
        sort_by = sort_map.get(self.sort_combo.currentText(), "updated") # Default to updated
        support = {
            "community": self.support_community_cb.isChecked(),
            "official": self.support_official_cb.isChecked(),
            "testing": self.support_testing_cb.isChecked(),
        }

        # Update UI for searching state
        self.status_label.setText(f"Searching templates for '{query}' (Page {self.current_page + 1})...")
        self.search_button.setEnabled(False)
        self.pagination_widget.setVisible(False) # Hide pagination during search
        self.cancel_button.setText("Cancel Search")
        self.cancel_button.setVisible(True)
        self.progress_bar.setRange(0, 0) # Indeterminate progress
        self.progress_bar.setVisible(True)
        QApplication.processEvents() # Ensure UI updates

        # Start API fetch thread
        self.api_thread = ApiFetchThread(
            asset_type="project", # Fetch project templates
            query=query,
            support_levels=support,
            sort_by=sort_by,
            page=self.current_page,
            godot_version=godot_version_filter,
        )
        self.api_thread.results_fetched.connect(self.on_api_results_fetched)
        self.api_thread.fetch_error.connect(self.on_api_fetch_error)
        self.api_thread.finished.connect(self.on_api_thread_finished)
        self.api_thread.start()

    def refresh_search_results(self):
        """Initiates a new search starting from page 0 (e.g., called when Godot version changes)."""
        logging.info("TemplatesTab: Received refresh_search_results command.")
        # Cancel any ongoing search before starting a new one
        if self.api_thread and self.api_thread.isRunning():
            self.cancel_current_operation()
            # Give a brief moment for the thread to potentially stop, though not strictly necessary
            # as on_api_results_fetched checks if self.api_thread is the current one.
            # QTimer.singleShot(50, lambda: self.search_assets(page=0)) # Optional delay
            # return
        self.search_assets(page=0) # Start search immediately

    def on_api_results_fetched(self, fetch_data: dict):
        """Handles the results received from the ApiFetchThread."""
        # Check if this result belongs to the *current* API thread instance
        if not self.api_thread or QObject.sender(self) != self.api_thread:
            logging.warning("TemplatesTab: Ignoring results from an old or unexpected API thread.")
            return

        assets = fetch_data.get("results", [])
        self.total_items = fetch_data.get("total_items", 0)
        self.total_pages = fetch_data.get("total_pages", 0)

        logging.info("TemplatesTab - API results received:")
        logging.info(f"  - Assets count: {len(assets)}")
        logging.info(f"  - Current Page (0-based): {self.current_page}")
        logging.info(f"  - Total Pages: {self.total_pages}")
        logging.info(f"  - Total Items: {self.total_items}")

        self._update_pagination_controls() # Update pagination based on new totals

        # Display results or placeholder messages
        if not assets and self.current_page == 0:
            self.status_label.setText(f"No templates found matching your criteria.")
            self._add_placeholder_label("No results found.")
            self.pagination_widget.setVisible(False)
        elif not assets and self.current_page > 0:
            # Should ideally not happen if total_pages is correct, but handle anyway
            self.status_label.setText(f"No templates found on page {self.current_page + 1}/{self.total_pages}.")
            self._add_placeholder_label("No results on this page.")
            self.pagination_widget.setVisible(self.total_pages > 1)
        else:
            # Display found assets
            self.status_label.setText(f"Found {len(assets)} templates (Page {self.current_page + 1}/{self.total_pages}) - Total: {self.total_items}.")
            self._display_assets(assets)
            self.pagination_widget.setVisible(self.total_pages > 1)

    def on_api_fetch_error(self, error_message: str):
        """Handles errors occurred during the API fetch operation."""
        # Check if this error belongs to the *current* API thread instance
        if not self.api_thread or QObject.sender(self) != self.api_thread:
            logging.warning("TemplatesTab: Ignoring error from an old or unexpected API thread.")
            return

        log_and_show_error(
            title="API Error",
            message=f"Failed to fetch templates from Godot Asset Library:\n{error_message}",
            level="warning", # Era warning
            parent=self,
            log_message="Error fetching template assets" # Messaggio log specifico
        )
        self.status_label.setText(f"Error: {error_message}")
        self._clear_results() # Clear results area on error
        self._add_placeholder_label(f"Error fetching templates: {error_message}")

    def on_api_thread_finished(self):
        """Cleans up after the ApiFetchThread finishes (normally or due to error/cancellation)."""
        # Check if this signal is from the *current* thread instance before resetting
        if QObject.sender(self) != self.api_thread:
             logging.warning("TemplatesTab: Ignoring finished signal from an old or unexpected API thread.")
             return

        logging.debug("TemplatesTab - API search thread finished.")
        self.api_thread = None # Clear the thread reference
        # Reset UI elements to idle state
        self.search_button.setEnabled(True)
        self.cancel_button.setVisible(False)
        self.progress_bar.setVisible(False)
        # Update status label only if it wasn't already set by results/error handlers
        current_status = self.status_label.text()
        if not current_status.startswith(("Found", "<font", "No templates")):
            self.status_label.setText("Search complete.")
        self._update_pagination_controls() # Ensure pagination buttons are correctly enabled/disabled

    def _update_pagination_controls(self):
        """Updates the pagination label and button states based on current page and total pages."""
        try:
            # Calculate button enable states
            can_go_prev = self.current_page > 0
            can_go_next = self.current_page < self.total_pages - 1
            # Disable buttons if an API search is active
            is_searching = self.api_thread is not None and self.api_thread.isRunning()

            logging.debug(f"    TemplatesTab Pagination Update:")
            logging.debug(f"      - Widget visible: {self.pagination_widget.isVisible()}")
            logging.debug(f"      - Current Page: {self.current_page}, Total Pages: {self.total_pages}")
            logging.debug(f"      - API Thread running: {is_searching}")

            # Update page info label
            page_display = self.current_page + 1
            total_pages_display = max(self.total_pages, 1) # Show at least 1 page
            self.page_info_label.setText(f"Page {page_display} / {total_pages_display}")

            # Update button enabled state
            self.prev_page_btn.setEnabled(can_go_prev and not is_searching)
            self.next_page_btn.setEnabled(can_go_next and not is_searching)

            logging.debug(f"      - Prev enabled: {self.prev_page_btn.isEnabled()}, Next enabled: {self.next_page_btn.isEnabled()}")

        except Exception as e:
            # Log errors occurring within this UI update function
            logging.exception("Error updating pagination controls (TemplatesTab)")

    def go_to_previous_page(self):
        """Initiates a search for the previous page of results."""
        if self.current_page > 0:
            logging.info("Requesting previous template page.")
            self.search_assets(page=self.current_page - 1)
        else:
            logging.warning("Attempted to go to previous page from the first page.")

    def go_to_next_page(self):
        """Initiates a search for the next page of results."""
        if self.current_page < self.total_pages - 1:
            logging.info("Requesting next template page.")
            self.search_assets(page=self.current_page + 1)
        else:
            logging.warning("Attempted to go to next page from the last page.")

    def _clear_results(self):
        """Removes all asset widgets from the results layout."""
        self.asset_widgets.clear() # Clear widget references
        self.icon_labels.clear() # Clear icon label references
        # Safely remove widgets from layout
        while self.results_layout.count():
            child_item = self.results_layout.takeAt(0)
            if child_item:
                widget = child_item.widget()
                if widget:
                    logging.debug(f"Removing result widget: {widget.objectName() if widget.objectName() else type(widget)}")
                    widget.deleteLater() # Schedule for deletion

    def _add_placeholder_label(self, text: str):
        """Adds a centered placeholder label to the results area."""
        placeholder = QLabel(text)
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_layout.addWidget(placeholder)

    def _display_assets(self, assets: list):
        """Creates and displays widgets for each asset in the results list."""
        self._clear_results() # Ensure area is clear before adding new results
        logging.debug(f"Displaying {len(assets)} template assets...")
        for asset in assets:
            try:
                asset_id = asset.get("asset_id")
                title = asset.get("title", "N/A")
                icon_url = asset.get("icon_url")

                # --- FIX: Ensure asset type is set correctly for templates ---
                asset["type"] = "project"
                # -------------------------------------------------------------

                if not asset_id:
                    logging.warning("Skipping asset display: Missing 'asset_id'.")
                    continue # Skip this asset and proceed to the next

                # Create the clickable frame widget
                asset_frame = ClickableAssetFrame()
                asset_frame.setObjectName(f"asset_widget_{asset_id}")
                # Set asset data on the frame itself
                asset_frame.setAssetData(asset_id, asset)
                # Connect the frame's clicked signal to show details
                asset_frame.clicked.connect(self._show_asset_details)

                item_layout = QHBoxLayout(asset_frame) # Main layout for the asset item

                # Icon Label
                icon_label = QLabel()
                icon_label.setFixedSize(ICON_SIZE)
                icon_label.setStyleSheet(
                    "background-color:#ddd; border:1px solid #aaa; qproperty-alignment:AlignCenter;"
                )
                icon_label.setText("...") # Placeholder text
                item_layout.addWidget(icon_label)
                self.icon_labels[str(asset_id)] = icon_label # Store reference for update
                # Start icon download if URL exists
                if icon_url:
                    self.start_icon_download(asset_id, icon_url)
                else:
                    icon_label.setText("N/A") # No icon available

                # Text Info Layout
                info_layout = QVBoxLayout()
                info_layout.setSpacing(2)

                title_label = QLabel(f"<b>{title}</b>")
                title_label.setWordWrap(True)
                info_layout.addWidget(title_label)
                info_layout.addWidget(QLabel(f"<i>by {asset.get('author','N/A')}</i> <small>(ID:{asset_id})</small>"))
                info_layout.addWidget(QLabel(f"v{asset.get('version_string','?')} ({asset.get('godot_version','?')}) Lic:{asset.get('cost','?')}"))
                info_layout.addWidget(QLabel(f"Cat:{asset.get('category','N/A')} Rat:{asset.get('rating','0')}/5 ⭐"))

                # Format modification date
                modify_date_str = "?"
                try:
                    modify_timestamp = asset.get("modify_date", "")
                    if modify_timestamp: # Check if timestamp exists
                         # Assuming timestamp is seconds since epoch (common in APIs)
                         # If it's a string like "YYYY-MM-DD HH:MM:SS", adjust parsing
                         if isinstance(modify_timestamp, (int, float)):
                              mod_dt = datetime.fromtimestamp(modify_timestamp)
                              modify_date_str = mod_dt.strftime("%d-%m-%Y")
                         elif isinstance(modify_timestamp, str):
                              # Attempt to parse common string format
                              mod_dt = datetime.strptime(modify_timestamp, "%Y-%m-%d %H:%M:%S")
                              modify_date_str = mod_dt.strftime("%d-%m-%Y")
                except (ValueError, TypeError, OSError) as dt_error:
                    logging.warning(f"Could not parse modify_date '{asset.get('modify_date')}' for asset {asset_id}: {dt_error}")
                    modify_date_str = "?" # Fallback

                info_layout.addWidget(QLabel(f"<small>Mod:{modify_date_str} Sup:{asset.get('support_level','?')}</small>"))
                item_layout.addLayout(info_layout, 1) # Info layout takes remaining space

                # Download Button Layout
                button_layout = QVBoxLayout()
                button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                download_button = QPushButton("📥 Download && Create Project...")
                download_button.setProperty("asset_id", asset_id) # Store ID on button
                download_button.setProperty("asset_title", title) # Store title on button
                # Connect button click directly to the download initiation logic
                download_button.clicked.connect(
                    lambda checked=False, data=asset: self._show_asset_details(data)
                )
                button_layout.addWidget(download_button)
                item_layout.addLayout(button_layout) # Add button layout to item

                # Add the complete asset frame to the results layout
                self.results_layout.insertWidget(self.results_layout.count() - 1, asset_frame) # Insert before spacer
                self.asset_widgets[str(asset_id)] = asset_frame # Store reference

            except Exception as e:
                # Log error for the specific asset but continue displaying others
                logging.exception(f"Error displaying asset ID {asset.get('asset_id', 'N/A')}")

        logging.debug("Finished displaying assets.")

    def _show_asset_details(self, asset_data: dict):
        """Opens the AssetDetailDialog for the selected asset."""
        # FIX: Use the received asset_data dictionary directly as initial_data
        initial_data = asset_data
        asset_id = initial_data.get("asset_id")

        if asset_id is None:
            logging.error("Could not get asset_id from clicked frame signal data.")
            return

        asset_id = str(asset_id) # Ensure string ID for consistency
        logging.info(f"Showing details dialog for asset: {asset_id} ({initial_data.get('title')})")
        # Ensure type is set (already done in _display_assets, but good practice)
        initial_data.setdefault("type", "project")

        # Create and show the dialog
        # Pass data_manager to the dialog
        dialog = AssetDetailDialog(asset_id, initial_data, self.data_manager, self) # Pass self as parent

        # Emit the signal to notify MainWindow to connect its slots
        self.asset_detail_dialog_shown.emit(dialog)

        dialog.exec() # Show modally
        logging.info(f"Asset detail dialog closed for asset: {asset_id}")

    def start_icon_download(self, asset_id: Any, icon_url: str):
        """Starts an asynchronous download task for an asset icon."""
        downloader = IconDownloader(str(asset_id), icon_url) # Ensure ID is string for downloader
        downloader.signals.icon_ready.connect(self.on_icon_ready)
        downloader.signals.error.connect(self.on_icon_error)
        # Use the thread pool to manage the download task
        self.thread_pool.start(downloader)

    def on_icon_ready(self, asset_id: str, local_path: str):
        """Slot called when an icon is downloaded or retrieved from cache."""
        logging.debug(f"Icon ready for asset {asset_id} at {local_path}")
        if asset_id in self.icon_labels:
            label = self.icon_labels[asset_id]
            pixmap = QPixmap(local_path)
            if not pixmap.isNull():
                # Scale pixmap smoothly while keeping aspect ratio
                scaled_pixmap = pixmap.scaled(
                    ICON_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                label.setPixmap(scaled_pixmap)
                label.setStyleSheet("") # Remove placeholder style
                label.setText("") # Remove placeholder text
            else:
                # Handle corrupted or invalid image file
                logging.warning(f"Could not load QPixmap for icon {asset_id} from {local_path}")
                label.setText("Err")
                label.setToolTip(f"Error loading icon:\n{local_path}")
                label.setStyleSheet("background-color:#fdd; border:1px solid red; color: red; qproperty-alignment: AlignCenter;") # Error style
        else:
            # This might happen if results were cleared while icon was downloading
            logging.warning(f"Received icon ready signal for asset {asset_id}, but no corresponding label found.")

    def on_icon_error(self, asset_id: str, error_message: str):
        """Handles errors during icon download."""
        # Only log the error, don't show a pop-up for each failed icon
        logging.warning(f"Failed to download icon for asset {asset_id}: {error_message}")
        # Optionally update the label to show a generic error icon or text
        if asset_id in self.icon_labels:
            self.icon_labels[asset_id].setText("(icon error)")
            self.icon_labels[asset_id].setToolTip(f"Icon download failed: {error_message}")
        # Non usare log_and_show_error qui per evitare popup multipli

    def cancel_current_operation(self):
        """Cancels the currently running API search or download thread."""
        if self.api_thread and self.api_thread.isRunning():
            logging.info("Cancelling API search thread...")
            self.api_thread.terminate() # Request termination
            # Optionally wait a very short time, but usually resetting UI is enough
            # self.api_thread.wait(100) # Wait up to 100ms
            self.on_api_thread_finished() # Reset UI immediately
            self.status_label.setText("Search cancelled.")
            self.status_message.emit("Template search cancelled.", 2000)
        elif self.download_thread and self.download_thread.isRunning():
            logging.info("Cancelling template download/creation thread...")
            self.download_thread.terminate()
            # self.download_thread.wait(100)
            self.on_template_download_finished(None, "Download cancelled by user.") # Simulate error finish
            self.status_message.emit("Template download cancelled.", 2000)
        else:
            logging.warning("Cancel button clicked, but no operation was active.")
