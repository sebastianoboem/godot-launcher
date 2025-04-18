# -*- coding: utf-8 -*-
# gui/extensions_tab.py

"""
Tab widget for managing Godot extensions.
Allows searching, viewing, and configuring addons for automatic installation.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, 
    QComboBox, QCheckBox, QFrame, QSizePolicy, QScrollArea, QGridLayout,
    QSpacerItem, QGroupBox, QApplication, QMainWindow, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread, QMetaObject, Q_ARG, QThreadPool, QTimer, QObject
from PyQt6.QtGui import QPixmap, QIcon, QCursor, QClipboard

from data_manager import DataManager
from api_clients import ApiFetchThread, fetch_asset_details_sync
from project_handler import get_godot_version_string
from gui.asset_detail_dialog import AssetDetailDialog
from utils import IconDownloader
from gui.styles import (
    COLORS, 
    LIST_WIDGET_STYLE, 
    CHECKBOX_STYLE,
    GROUP_BOX_STYLE,
    INPUT_STYLE,
    BUTTON_STYLE,
    PRIMARY_BUTTON_STYLE,
    FRAME_STYLE,
    # Specific styles for components
    STATUS_STYLE,
    PAGINATION_STYLE,
    ASSET_TITLE_STYLE,
    ASSET_INFO_STYLE,
    COPY_BUTTON_STYLE,
    ICON_PLACEHOLDER_STYLE,
    CANCEL_BUTTON_STYLE
)

# Fixed size for icons
ICON_SIZE = QSize(64, 64)

# Custom class for clickable frames
class ClickableAssetFrame(QFrame):
    """Clickable frame to represent an asset of the Godot Asset Library."""
    clicked = pyqtSignal()
    
    def mousePressEvent(self, event):
        """Captures mouse clicks on the frame."""
        self.clicked.emit()
        super().mousePressEvent(event)

class ExtensionsTab(QWidget):
    """
    QWidget for the 'Extensions' tab, allowing users to browse, search,
    and select Godot addons/extensions from the Asset Library for auto-installation.
    """
    # Signal emitted when the selection of extensions for auto-install changes
    auto_install_selection_changed = pyqtSignal()
    status_message = pyqtSignal(str, int) # Emitted to show messages in the main window status bar (message, timeout_ms)

    def __init__(self, data_manager: DataManager):
        """
        Initializes the ExtensionsTab.

        Args:
            data_manager: The central DataManager instance.
        """
        super().__init__()
        self.data_manager = data_manager # Store DataManager instance
        self.asset_widgets: Dict[str, Dict[str, QWidget]] = {} # Stores asset widgets {asset_id: {'widget': ClickableAssetFrame, 'checkbox': QCheckBox}}
        self.icon_labels: Dict[str, QLabel] = {} # Stores icon labels by asset ID
        self.thread_pool = QThreadPool() # Thread pool for icon downloads
        self.thread_pool.setMaxThreadCount(4) # Limit concurrent icon downloads
        self.api_thread: Optional[ApiFetchThread] = None # Holds the current API search thread
        self.current_page: int = 0 # Current page number (0-based) for API results
        self.total_pages: int = 0 # Total pages available from the last API search
        self.total_items: int = 0 # Total items available from the last API search
        self.client_side_sort: Optional[str] = None # Flag for client-side sorting (e.g., 'selected')
        
        # Log of selected extensions at startup
        selected_extensions = self.data_manager.get_auto_install_extensions()
        logging.info(f"ExtensionsTab initialized. Selected extensions: {selected_extensions}")
        
        self.init_ui()
        self.search_assets() # Perform initial search on startup

    def init_ui(self):
        """Initializes the user interface elements of the tab."""
        layout = QVBoxLayout(self)
        
        # Title with modern style
        title_label = QLabel("<h2>Explore Extensions / Addons</h2>")
        title_label.setStyleSheet(f"color: {COLORS['text_primary']}; margin-bottom: 5px;")
        layout.addWidget(title_label)
        
        # Subtitle with style
        subtitle_label = QLabel("Check the boxes to include extensions in the installation via the button in the 'Projects' tab.")
        subtitle_label.setStyleSheet(f"color: {COLORS['text_secondary']}; margin-bottom: 10px;")
        layout.addWidget(subtitle_label)

        # --- Filters/Sorting Group ---
        filter_group = QGroupBox("Filter / Sorting")
        filter_group.setStyleSheet(GROUP_BOX_STYLE)
        filter_layout = QHBoxLayout(filter_group)
        
        # Search label
        search_label = QLabel("Search:")
        search_label.setStyleSheet(f"color: {COLORS['text_primary']};")
        filter_layout.addWidget(search_label)
        
        # Search field
        self.search_edit = QLineEdit()
        self.search_edit.setStyleSheet(INPUT_STYLE)
        self.search_edit.setPlaceholderText("e.g., GDScript Formatter, Terrain...")
        filter_layout.addWidget(self.search_edit, 2) # Search takes more space

        # Sort label
        sort_label = QLabel("Sort by:")
        sort_label.setStyleSheet(f"color: {COLORS['text_primary']};")
        filter_layout.addWidget(sort_label)
        
        # Sort combobox
        self.sort_combo = QComboBox()
        self.sort_combo.setStyleSheet(INPUT_STYLE)
        self.sort_combo.addItems([
            "Rating", "License", "Name", "Updated", "Downloads", #"Selected"
        ])
        self.sort_combo.setCurrentText("Rating") # Default sort
        filter_layout.addWidget(self.sort_combo, 1)

        # Support label
        support_label = QLabel("Support:")
        support_label.setStyleSheet(f"color: {COLORS['text_primary']};")
        filter_layout.addWidget(support_label)
        
        # Checkbox with style
        self.support_community_cb = QCheckBox("Community")
        self.support_community_cb.setStyleSheet(CHECKBOX_STYLE)
        self.support_official_cb = QCheckBox("Official")
        self.support_official_cb.setStyleSheet(CHECKBOX_STYLE)
        self.support_testing_cb = QCheckBox("Testing")
        self.support_testing_cb.setStyleSheet(CHECKBOX_STYLE)
        self.support_community_cb.setChecked(True) # Default filters
        self.support_official_cb.setChecked(True)
        self.support_testing_cb.setChecked(False)
        filter_layout.addWidget(self.support_community_cb)
        filter_layout.addWidget(self.support_official_cb)
        filter_layout.addWidget(self.support_testing_cb)

        # New Checkbox to show only selected with style
        self.show_selected_only_cb = QCheckBox("Selected Only")
        self.show_selected_only_cb.setStyleSheet(CHECKBOX_STYLE)
        self.show_selected_only_cb.setToolTip("Filter results to show only extensions currently selected for auto-installation.")
        self.show_selected_only_cb.stateChanged.connect(lambda: self.search_assets(page=0))
        filter_layout.addWidget(self.show_selected_only_cb)

        # Search button with style
        self.search_button = QPushButton("🔍 Search Extensions")
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
        
        self.results_widget = QWidget() # Container for results
        self.results_widget.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        
        self.results_layout = QVBoxLayout(self.results_widget) # Layout for asset items
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.results_layout.setSpacing(5) # Reduced spacing for denser list
        self.scroll_area.setWidget(self.results_widget)
        layout.addWidget(self.scroll_area, 1) # Scroll area takes available vertical space

        # --- Status Bar / Pagination Frame ---
        self.status_frame = QFrame()
        self.status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.status_frame.setStyleSheet(FRAME_STYLE)
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(5, 2, 5, 2)
        
        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        
        self.cancel_search_button = QPushButton("Cancel Search")
        self.cancel_search_button.setStyleSheet(BUTTON_STYLE)
        self.cancel_search_button.setVisible(False)

        # Pagination Controls Widget
        self.pagination_widget = QWidget()
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
        status_layout.addWidget(self.cancel_search_button)
        layout.addWidget(self.status_frame)

        # --- Connect Signals ---
        self.search_button.clicked.connect(lambda: self.search_assets(page=0)) # Search starts from page 0
        self.search_edit.returnPressed.connect(lambda: self.search_assets(page=0))
        self.cancel_search_button.clicked.connect(self.cancel_search)
        self.prev_page_btn.clicked.connect(self.go_to_previous_page)
        self.next_page_btn.clicked.connect(self.go_to_next_page)
        # Trigger search immediately when sort option changes
        self.sort_combo.currentIndexChanged.connect(lambda: self.search_assets(page=0))
        # Also trigger search when support checkboxes change
        self.support_community_cb.stateChanged.connect(lambda: self.search_assets(page=0))
        self.support_official_cb.stateChanged.connect(lambda: self.search_assets(page=0))
        self.support_testing_cb.stateChanged.connect(lambda: self.search_assets(page=0))
        self.show_selected_only_cb.stateChanged.connect(lambda: self.search_assets(page=0))

    def search_assets(self, page: int = 0):
        """Initiates an API search or fetches details for selected extensions."""
        # --- MODIFIED: Selected Filter Handling --- 
        if self.show_selected_only_cb.isChecked():
            logging.info("'Show Selected Only' checked. Fetching selected extension details...")
            # If checkbox is active, don't do normal API search, call the dedicated function
            # Make sure the pagination is handled correctly
            self.current_page = 0 # Reset logical page when showing only selected
            self.total_pages = 1 # Logically there's only one "page" of selected results
            self._fetch_and_display_selected() 
            return # Exit function to not proceed with paginated search
        # --- END MODIFICATION ---

        # If checkbox is NOT active, proceed with normal API search...
        if self.api_thread and self.api_thread.isRunning():
            logging.warning("API search request ignored: Another search is already running.")
            return # Prevent concurrent searches

        self.current_page = page # Set current page

        # Get Godot version filter
        current_godot_path = self.data_manager.get_godot_path()
        godot_version_filter = get_godot_version_string(current_godot_path)

        logging.info(f"Starting extension search - Page: {self.current_page}, Godot Version Filter: {godot_version_filter}")
        self._clear_results() # Clear previous results

        # Get search parameters from UI
        query = self.search_edit.text().strip()
        sort_option = self.sort_combo.currentText()

        # Determine API sort parameter and client-side sort needs
        api_sort_param = "updated" # API default
        self.client_side_sort = None

        # Map UI sort options to API parameters
        sort_mapping = {
            "Rating": "rating",
            "Name": "name",
            "License": "cost",
            "Updated": "updated",
            "Downloads": "downloads",
            # Options requiring client-side reverse/sorting:
            "Selected": "selected", # Special flag for client-side
            "Oldest First": "updated_reverse",
            "Name (Z-A)": "name_reverse",
            "License (Z-A)": "cost_reverse",
        }

        selected_sort_key = sort_mapping.get(sort_option)

        if selected_sort_key in ["selected", "updated_reverse", "name_reverse", "cost_reverse"]:
            # For client-side sorts, use a base API sort (e.g., 'updated')
            # and set the client_side_sort flag.
            api_sort_param = "updated" # Or choose another base like 'rating' or 'name'
            self.client_side_sort = selected_sort_key
            logging.debug(f"Client-side sort requested: '{self.client_side_sort}'. API will use base sort: '{api_sort_param}'.")
        elif selected_sort_key:
            # Direct mapping to API parameter
            api_sort_param = selected_sort_key
        
        logging.debug(f"API sort parameter: {api_sort_param}")

        support = {
            "community": self.support_community_cb.isChecked(),
            "official": self.support_official_cb.isChecked(),
            "testing": self.support_testing_cb.isChecked(),
        }

        # Update UI for searching state
        self.status_label.setText(f"Searching extensions for '{query}' (Page {self.current_page + 1})...")
        self.search_button.setEnabled(False)
        self.search_edit.setEnabled(False)
        self.show_selected_only_cb.setEnabled(False)
        self.cancel_search_button.setVisible(True)
        self.cancel_search_button.setEnabled(True)
        self.prev_page_btn.setEnabled(False)
        self.next_page_btn.setEnabled(False)

        # Dettaglio log per debug
        logging.debug(f"API call with: asset_type=extensions, query='{query}', godot_version={godot_version_filter}, " +
                      f"support_levels={support}, sort_by={api_sort_param}, page={page}")

        # Start the search thread
        try:
            self.api_thread = ApiFetchThread(
                asset_type="extensions",
                query=query,
                godot_version=godot_version_filter,
                category_id=None,
                support_levels=support,
                sort_by=api_sort_param,
                page=page
            )
            self.api_thread.finished.connect(self.on_api_thread_finished)
            self.api_thread.results_fetched.connect(self.on_api_results_fetched)
            self.api_thread.fetch_error.connect(self.on_api_fetch_error)
            self.api_thread.start()
            logging.info("API thread for extensions started successfully")
        except Exception as e:
            logging.exception(f"Error starting API thread: {e}")
            self.status_label.setText(f"<font color='red'>Error starting search: {e}</font>")
            self.search_button.setEnabled(True)
            self.search_edit.setEnabled(True)
            self.show_selected_only_cb.setEnabled(True)
            self.cancel_search_button.setVisible(False)

    def refresh_search_results(self):
        """Initiates a new search starting from page 0 or refreshes selected view."""
        logging.info("ExtensionsTab: Received refresh_search_results command.")
        # --- MODIFIED: Selected Filter Handling --- 
        if self.show_selected_only_cb.isChecked():
            # If showing only selected, just call the dedicated function
            self._fetch_and_display_selected()
        # --- END MODIFICATION ---
        else:
             # Otherwise, proceed with normal API search from page 0
             if self.api_thread and self.api_thread.isRunning():
                 self.cancel_search() # Cancel ongoing search first
             self.search_assets(page=0) # Start new search from page 0

    def on_api_results_fetched(self, result):
        """Slot called when API search results are fetched."""
        try:
            # Verify that the result comes from the current thread
            if QObject.sender(self) != self.api_thread:
                logging.warning("ExtensionsTab: Ignored results from an old or unexpected API thread.")
                return
            
            logging.debug(f"API extension search fetched: {result}")
            page_offset = self.current_page * 20 # Page size is fixed at 20
            assets = result.get("result", [])
            
            if not assets and isinstance(result.get("results"), list):
                # Correction: some methods might use "results" instead of "result"
                assets = result.get("results", [])
                logging.debug("Used 'results' field instead of 'result' in API data")
            
            total_items = result.get("count", 0)
            if total_items == 0:
                total_items = result.get("total_items", 0)  # Support for alternative field names
            
            self.total_items = total_items
            self.total_pages = (total_items + 19) // 20 # Ceiling division for total pages
            
            # Detailed log for debugging
            logging.info(f"Received API results: {len(assets)} items, page {self.current_page+1}/{self.total_pages}, total: {total_items}")
            
            # Update status message
            if len(assets) > 0:
                self.status_label.setText(f"Found {total_items} results. Showing {page_offset+1}-{min(page_offset+len(assets), total_items)}.")
                self.status_label.setStyleSheet(STATUS_STYLE)
            else:
                self.status_label.setText("No results found. Try different search criteria.")
                self._add_placeholder_label("No extensions found with current criteria.")
                return
            
            self._display_assets(assets)
        except Exception as e:
            logging.exception("Error processing API extensions search results")
            self.status_label.setText(f"<font color='red'>Error processing results: {e}</font>")
            self._add_placeholder_label(f"Error processing results:\n{e}")
            # Re-enable UI controls
            self.search_button.setEnabled(True)
            self.search_edit.setEnabled(True)
            self.show_selected_only_cb.setEnabled(True)

    def on_api_fetch_error(self, error_message: str):
        """Handler for API fetch errors."""
        logging.error(f"API fetch error (Extensions): {error_message}")
        self.status_label.setText(f"<font color='red'>Search error: {error_message}</font>")
        self._add_placeholder_label(f"API search error:\n{error_message}")
        self.search_button.setEnabled(True)
        self.search_edit.setEnabled(True)
        self.show_selected_only_cb.setEnabled(True)
        self.cancel_search_button.setVisible(False)

    def on_api_thread_finished(self):
        """Slot called when the API thread completes (success or error)."""
        # Verify that the signal comes from the current thread
        if QObject.sender(self) != self.api_thread:
            logging.warning("ExtensionsTab: Ignored finished signal from an old or unexpected API thread.")
            return
        
        logging.debug("API search thread finished.")
        self.cancel_search_button.setVisible(False)
        self.search_button.setEnabled(True)
        self.search_edit.setEnabled(True)
        self.sort_combo.setEnabled(True)
        self.support_community_cb.setEnabled(True)
        self.support_official_cb.setEnabled(True)
        self.support_testing_cb.setEnabled(True)
        self.show_selected_only_cb.setEnabled(True)
        
        # If there are no results, update the status
        if self.total_items == 0:
            self.status_label.setText("No results found. Try different search criteria.")
        
        # Make sure all controls are restored even in case of errors
        self.api_thread = None  # Remove reference to completed thread
        
        self._update_pagination_controls() # Ensure pagination buttons are correct

    def _update_pagination_controls(self):
        """Updates pagination controls based on current page and total pages."""
        self.pagination_widget.setVisible(self.total_pages > 1)
        
        if self.total_pages <= 1:
            return # Hide controls if there is only one page or none

        # Update pagination style
        self.pagination_widget.setStyleSheet(PAGINATION_STYLE)
        
        # Enable/disable buttons based on current position
        self.prev_page_btn.setEnabled(self.current_page > 0)
        self.next_page_btn.setEnabled(self.current_page < self.total_pages - 1)
        
        # Update current/total page label
        page_text = f"Page {self.current_page + 1} of {self.total_pages}"
        self.page_info_label.setText(page_text)

    def go_to_previous_page(self):
        """Initiates a search for the previous page of results."""
        if self.current_page > 0:
            logging.info("Requesting previous extension page.")
            self.search_assets(page=self.current_page - 1)
        else:
            logging.warning("Attempted to go to previous page from the first page.")

    def go_to_next_page(self):
        """Initiates a search for the next page of results."""
        if self.current_page < self.total_pages - 1:
            logging.info("Requesting next extension page.")
            self.search_assets(page=self.current_page + 1)
        else:
            logging.warning("Attempted to go to next page from the last page.")

    def _clear_results(self):
        """Removes all asset widgets from the results layout."""
        self.asset_widgets.clear()
        self.icon_labels.clear()
        while self.results_layout.count():
            child_item = self.results_layout.takeAt(0)
            if child_item:
                widget = child_item.widget()
                if widget:
                    logging.debug(f"Removing result widget: {widget.objectName() if widget.objectName() else type(widget)}")
                    widget.deleteLater()

    def _add_placeholder_label(self, message: str):
        """Adds a centered placeholder message to the results area."""
        placeholder = QLabel(message)
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setWordWrap(True)
        placeholder.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            background-color: {COLORS["bg_content"]};
            border: 1px dashed {COLORS["border"]};
            border-radius: 8px;
            padding: 30px;
            margin: 20px;
            font-size: 14px;
        """)
        placeholder.setMinimumHeight(150)
        self.results_layout.addWidget(placeholder)
        return placeholder

    def _display_assets(self, assets: list):
        """Displays the assets in the UI, creating individual asset frames for each."""
        if not assets:
            self.status_label.setText("No results found.")
            self._add_placeholder_label("No extensions found with current criteria.")
            return

        # Get the list of currently selected auto-install extensions
        selected_ids_set = set(self.data_manager.get_auto_install_extensions())
        logging.debug(f"Displaying {len(assets)} asset results. Selected IDs: {selected_ids_set}")

        # Handle case where we have a result but no items - shouldn't happen, but...
        if len(assets) == 0:
            logging.warning("Received empty assets list to display.")
            self._add_placeholder_label("No results found.")
            self.status_label.setText("No results found.")
            return
        
        # Style for asset titles
        asset_title_style = f"""
            QLabel {{
                color: {COLORS["text_primary"]};
                font-weight: bold;
                font-size: 13px;
            }}
        """
        
        # Style for asset info
        asset_info_style = f"""
            QLabel {{
                color: {COLORS["text_secondary"]};
                font-size: 11px;
            }}
        """
        
        # Style for ID copy buttons
        copy_button_style = f"""
            QPushButton {{
                background-color: {COLORS["bg_content"]};
                color: {COLORS["text_primary"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                border-color: {COLORS["accent"]};
                color: white;
            }}
            QPushButton:pressed {{
                background-color: {COLORS["accent_hover"]};
            }}
        """
        
        # Style for unloaded icons
        icon_placeholder_style = f"""
            QLabel {{
                background-color: {COLORS["bg_dark"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 4px;
                color: {COLORS["text_secondary"]};
                padding: 2px;
                qproperty-alignment: AlignCenter;
            }}
        """

        for asset in assets:
            try:
                asset_id = asset.get("asset_id")
                if asset_id is None:
                    logging.warning("Asset without an ID found in results. Skipping.")
                    continue

                title = asset.get("title", "Untitled")
                icon_url = asset.get("icon_url", "")

                # Create a clickable frame for the entire asset
                asset_frame = ClickableAssetFrame()
                asset_frame.setFrameShape(QFrame.Shape.StyledPanel)
                asset_frame.setMinimumHeight(120) # Ensure reasonable height
                asset_frame.setCursor(Qt.CursorShape.PointingHandCursor)
                asset_frame.clicked.connect(lambda asset_data=asset: self._show_asset_details(asset_data))

                # Create layout for the asset
                item_layout = QHBoxLayout(asset_frame)
                item_layout.setContentsMargins(5, 5, 5, 5)
                item_layout.setSpacing(10) # Spacing between elements

                # Icon Label (placeholder until icon is downloaded)
                icon_label = QLabel()
                icon_label.setFixedSize(ICON_SIZE)
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon_label.setStyleSheet(ICON_PLACEHOLDER_STYLE)
                icon_label.setText("...") # Placeholder
                item_layout.addWidget(icon_label)
                self.icon_labels[str(asset_id)] = icon_label # Store reference
                if icon_url: self.start_icon_download(asset_id, icon_url)
                else: icon_label.setText("N/A")

                # Auto-Install Checkbox - Ensure its state is correctly set based on the ID
                checkbox = QCheckBox()
                # Converti l'ID in int per il confronto con l'insieme di ID selezionati
                int_asset_id = int(asset_id) if isinstance(asset_id, (int, str)) else asset_id
                is_selected = int_asset_id in selected_ids_set
                logging.debug(f"Asset ID {asset_id} (type: {type(asset_id)}) selected: {is_selected}")
                
                # Block signals during initial setup to avoid unwanted activations
                checkbox.blockSignals(True)
                checkbox.setChecked(is_selected)
                checkbox.blockSignals(False)
                
                checkbox.setToolTip("Select to include in multi-installation\n(and auto-installation for new projects)")
                checkbox.setProperty("asset_id", asset_id) # Store ID on checkbox
                checkbox.stateChanged.connect(self.toggle_auto_install) # Connect state change
                checkbox.setStyleSheet(CHECKBOX_STYLE)
                item_layout.addWidget(checkbox)

                # Text Info Layout
                info_layout = QVBoxLayout()
                info_layout.setSpacing(2) # Compact spacing
                title_label = QLabel(f"<b>{title}</b>")
                title_label.setWordWrap(True)
                title_label.setStyleSheet(ASSET_TITLE_STYLE)
                info_layout.addWidget(title_label)
                
                author_label = QLabel(f"<small>by {asset.get('author','N/A')} (ID:{asset_id})</small>")
                author_label.setStyleSheet(ASSET_INFO_STYLE)
                info_layout.addWidget(author_label)
                
                version_label = QLabel(f"<small>v{asset.get('version_string','?')} ({asset.get('godot_version','?')}) Lic:{asset.get('cost','?')}</small>")
                version_label.setStyleSheet(ASSET_INFO_STYLE)
                info_layout.addWidget(version_label)
                
                category_label = QLabel(f"<small>Cat:{asset.get('category','N/A')} Val:{asset.get('rating','0')}/5⭐</small>")
                category_label.setStyleSheet(ASSET_INFO_STYLE)
                info_layout.addWidget(category_label)

                # Format modification date (similar to TemplatesTab)
                modify_date_str = "?"
                try:
                    modify_timestamp = asset.get("modify_date", "")
                    if modify_timestamp:
                         if isinstance(modify_timestamp, (int, float)):
                              mod_dt = datetime.fromtimestamp(modify_timestamp)
                              modify_date_str = mod_dt.strftime("%d-%m-%y") # Use 2-digit year for space
                         elif isinstance(modify_timestamp, str):
                              mod_dt = datetime.strptime(modify_timestamp, "%Y-%m-%d %H:%M:%S")
                              modify_date_str = mod_dt.strftime("%d-%m-%y")
                except (ValueError, TypeError, OSError): modify_date_str = "?"

                date_label = QLabel(f"<small>Mod:{modify_date_str} Sup:{asset.get('support_level','?')}</small>")
                date_label.setStyleSheet(ASSET_INFO_STYLE)
                info_layout.addWidget(date_label)
                item_layout.addLayout(info_layout, 1) # Info takes remaining space

                # Copy ID Button Layout
                button_layout = QVBoxLayout()
                button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                copy_button = QPushButton("📋 ID")
                copy_button.setToolTip("Copy asset ID to clipboard")
                copy_button.setProperty("asset_id", asset_id)
                copy_button.setFixedWidth(60) # Make button smaller
                copy_button.setStyleSheet(COPY_BUTTON_STYLE)
                # Connect button click directly, preventing propagation to frame
                copy_button.clicked.connect(lambda checked=False, btn=copy_button: self.copy_asset_id_from_button(btn))
                button_layout.addWidget(copy_button)
                item_layout.addLayout(button_layout)

                # Add the complete asset frame to the results layout
                self.results_layout.addWidget(asset_frame)
                # Store references to the frame and checkbox for potential future use
                self.asset_widgets[str(asset_id)] = {"widget": asset_frame, "checkbox": checkbox}

            except Exception as e:
                logging.exception(f"Error displaying extension asset ID {asset.get('asset_id', 'N/A')}")

        logging.debug("Finished displaying extension assets.")

    def _show_asset_details(self, asset_data: dict):
        """Opens the AssetDetailDialog when a ClickableAssetFrame is clicked."""
        # FIX: Use the received asset_data dictionary directly as initial_data
        initial_data = asset_data
        asset_id = initial_data.get("asset_id")

        if asset_id is None:
            logging.error("Could not get asset_id from clicked frame signal data.")
            return

        logging.info(f"Opening details for Extension ID: {asset_id}")
        # Ensure type is set (already done in _display_assets, but good practice)
        initial_data.setdefault("type", "addon")

        # Try to find the main window to use as parent for modality
        main_window = self.window()
        dialog_parent = main_window if isinstance(main_window, QMainWindow) else self

        dialog = AssetDetailDialog(asset_id, initial_data, self.data_manager, dialog_parent)

        # Connect the dialog's install request signal to the main window's handler
        # This allows the main window to coordinate installation with the ProjectsTab
        if isinstance(main_window, QMainWindow) and hasattr(main_window, "handle_install_extension_request"):
            try:
                dialog.install_extension_requested.connect(main_window.handle_install_extension_request)
                logging.debug("Connected install_extension_requested signal to MainWindow handler.")
            except TypeError as e: # Catch potential connection errors
                logging.exception("Error connecting install_extension_requested signal")
        elif isinstance(main_window, QMainWindow):
            logging.error("Could not connect install signal: MainWindow found but missing 'handle_install_extension_request' slot!")
        else:
            logging.error("Could not connect install signal: MainWindow instance not found.")

        dialog.exec() # Show the dialog modally

    def copy_asset_id_from_button(self, button: QPushButton):
        """Wrapper to call copy_asset_id, ensuring the button is treated as the sender."""
        logging.debug("Copy ID button clicked.")
        original_sender_func = self.sender
        self.sender = lambda: button # Temporarily set sender
        try:
            self.copy_asset_id()
        finally:
            self.sender = original_sender_func # Restore sender

    def start_icon_download(self, asset_id: Any, icon_url: str):
        """Starts an asynchronous download task for an asset icon."""
        downloader = IconDownloader(str(asset_id), icon_url)
        downloader.signals.icon_ready.connect(self.on_icon_ready)
        downloader.signals.error.connect(self.on_icon_error)
        self.thread_pool.start(downloader)

    def on_icon_ready(self, asset_id: str, local_path: str):
        """Slot called when an icon is downloaded or retrieved from cache."""
        # Check if the label still exists (results might have been cleared)
        if asset_id in self.icon_labels:
            label = self.icon_labels[asset_id]
            pixmap = QPixmap(local_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                label.setPixmap(scaled_pixmap)
                label.setStyleSheet("") # Clear placeholder style
                label.setText("")
            else:
                logging.warning(f"Could not load QPixmap for icon {asset_id} from {local_path}")
                label.setText("Err")
                label.setStyleSheet("background-color:#fdd; border:1px solid red; color: red; qproperty-alignment: AlignCenter;")
        else:
            logging.debug(f"Icon ready for asset {asset_id}, but label no longer exists.")


    def on_icon_error(self, asset_id: str, error_message: str):
        """Slot called when an icon download fails."""
        if asset_id in self.icon_labels:
            label = self.icon_labels[asset_id]
            label.setText("Fail")
            label.setToolTip(f"Unable to download icon:\n{error_message}")
            label.setStyleSheet(f"""
                background-color: {COLORS["bg_dark"]};
                border: 1px solid {COLORS["error"]};
                color: {COLORS["error"]};
                border-radius: 4px;
                qproperty-alignment: AlignCenter;
            """)
        else:
             logging.debug(f"Icon error for asset {asset_id}, but label no longer exists.")

    def toggle_auto_install(self, state: int):
        """Handles the state change of an auto-install checkbox."""
        checkbox = self.sender()
        if not isinstance(checkbox, QCheckBox): return

        asset_id = checkbox.property("asset_id")
        if asset_id is None: return

        success = False
        action_str = ""
        is_checked = (state == Qt.CheckState.Checked.value)

        try:
            if is_checked:
                # Use DataManager to add the extension ID
                success = self.data_manager.add_auto_install_extension(asset_id)
                action_str = "added to"
            else:
                # Use DataManager to remove the extension ID
                success = self.data_manager.remove_auto_install_extension(asset_id)
                action_str = "removed from"

            if success:
                self.auto_install_selection_changed.emit() # Notify that the list changed
                status_msg = f"Extension ID {asset_id} {action_str} auto-install list."
                logging.info(status_msg)
                self.status_label.setText(status_msg)
                # Clear status message after a delay
                QTimer.singleShot(3000, lambda: self.status_label.setText("Ready.") if self.status_label.text() == status_msg else None)
            else:
                # Should not happen if DataManager logic is correct, but handle defensively
                logging.warning(f"Failed to {action_str} auto-install list for ID {asset_id}.")
                # Revert checkbox state visually if operation failed
                checkbox.blockSignals(True)
                checkbox.setChecked(not is_checked)
                checkbox.blockSignals(False)
                
                # Show detailed message to user
                if is_checked:
                    QMessageBox.warning(self, "Error", f"Unable to add extension ID {asset_id} to auto-install list.")
                else:
                    QMessageBox.warning(self, "Error", f"Unable to remove extension ID {asset_id} from auto-install list. This might be a default extension that cannot be removed.")

        except Exception as e:
             logging.exception(f"Error toggling auto-install for asset ID {asset_id}")
             # Revert checkbox state visually on error
             checkbox.blockSignals(True)
             checkbox.setChecked(not is_checked)
             checkbox.blockSignals(False)
             QMessageBox.critical(self, "Error", f"An unexpected error occurred while updating auto-install list:\n{e}")


    def copy_asset_id(self):
        """Copies the asset ID from the sender button's property to the clipboard."""
        button = self.sender()
        if not isinstance(button, QPushButton): return

        asset_id = button.property("asset_id")
        if asset_id is not None:
            try:
                clipboard = QApplication.clipboard()
                clipboard.setText(str(asset_id))
                self.status_label.setText(f"Asset ID {asset_id} copied to clipboard.")
                # Provide visual feedback on the button
                original_text = button.text()
                button.setText("✅")
                button.setEnabled(False)
                # Restore button after a short delay
                QTimer.singleShot(1500, lambda: (button.setText(original_text), button.setEnabled(True)) if button else None)
            except Exception as e:
                logging.exception(f"Failed to copy asset ID {asset_id} to clipboard.")
                self.status_label.setText(f"<font color='red'>Error copying ID: {e}</font>")
        else:
            logging.warning("Copy ID button clicked, but asset_id property not found.")
            self.status_label.setText("<font color='red'>Could not find Asset ID.</font>")

    def cancel_search(self):
        """Cancels the current API search operation."""
        logging.info("Cancelling extension search...")
        self.cancel_search_button.setVisible(False)
        
        # Customize cancel button
        self.cancel_search_button.setText("Search Cancelled")
        self.cancel_search_button.setEnabled(False)
        self.cancel_search_button.setStyleSheet(CANCEL_BUTTON_STYLE)

    def _fetch_and_display_selected(self):
        """Retrieves details ONLY for selected extensions and displays them."""
        # Cancel any ongoing API search
        if self.api_thread and self.api_thread.isRunning():
            self.cancel_search()
            # It might be necessary to wait briefly or handle the state
            # QTimer.singleShot(100, self._fetch_and_display_selected) # Retry after a delay?
            # return

        self._clear_results() # Clear the results area
        self.pagination_widget.setVisible(False) # Hide pagination
        # Temporarily disable search/filter controls
        self.search_button.setEnabled(False)
        self.search_edit.setEnabled(False)
        self.sort_combo.setEnabled(False)
        self.support_community_cb.setEnabled(False)
        self.support_official_cb.setEnabled(False)
        self.support_testing_cb.setEnabled(False)

        selected_ids = self.data_manager.get_auto_install_extensions()

        if not selected_ids:
            self.status_label.setText("No extensions selected for auto-installation.")
            self._add_placeholder_label("No extensions selected.")
            # Re-enable controls
            self.search_button.setEnabled(True)
            self.search_edit.setEnabled(True)
            self.sort_combo.setEnabled(True)
            self.support_community_cb.setEnabled(True)
            self.support_official_cb.setEnabled(True)
            self.support_testing_cb.setEnabled(True)
            return

        self.status_label.setText(f"Loading details for {len(selected_ids)} selected extensions...")
        QApplication.processEvents() # Update UI

        detailed_assets = []
        errors = []
        # TODO: Consider a QThread if there are many selected extensions to avoid blocking the UI
        for i, asset_id in enumerate(selected_ids):
            self.status_label.setText(f"Loading {i+1}/{len(selected_ids)}: ID {asset_id}...")
            QApplication.processEvents()
            try:
                details = fetch_asset_details_sync(asset_id)
                if details:
                    # Ensure the type is correct for AssetDetailDialog
                    details.setdefault("type", "addon")
                    detailed_assets.append(details)
                else:
                    logging.warning(f"Unable to retrieve details for selected extension ID: {asset_id}")
                    errors.append(f"ID {asset_id}: Details not found")
            except Exception as e:
                logging.exception(f"Error retrieving details for selected extension ID: {asset_id}")
                errors.append(f"ID {asset_id}: API Error ({e})")

        # Re-enable controls before displaying
        self.search_button.setEnabled(True)
        self.search_edit.setEnabled(True)
        self.sort_combo.setEnabled(True)
        self.support_community_cb.setEnabled(True)
        self.support_official_cb.setEnabled(True)
        self.support_testing_cb.setEnabled(True)

        # Display results
        if not detailed_assets:
            error_str = "\n".join(errors)
            self.status_label.setText(f"<font color='red'>Error loading selected details.</font>")
            self._add_placeholder_label(f"Unable to load selected extensions.\n{error_str}")
        else:
             # Display found extensions
             self.status_label.setText(f"Showing {len(detailed_assets)} selected extensions.")
             if errors:
                 self.status_label.setText(f"Showing {len(detailed_assets)} selected extensions (Errors: {len(errors)}). See log.")
                 # We could add a placeholder for errors?
             self._display_assets(detailed_assets)

        # Make sure pagination remains hidden
        self.pagination_widget.setVisible(False)
