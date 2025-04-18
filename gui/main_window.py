# -*- coding: utf-8 -*-
# gui/main_window.py

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSlot  # Added QSize
from PyQt6.QtGui import QFont, QIcon, QAction  # Added QIcon and QAction
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QButtonGroup,
    QStyle,
    QAbstractButton,
    QStatusBar,
    QSpacerItem,
    QSizePolicy,
    QDialog,
)

# Import GUI classes and DataManager
from data_manager import DataManager # Use the DataManager class
from gui.asset_detail_dialog import AssetDetailDialog # Import the dialog
from gui.projects_tab import ProjectsTab
from gui.settings_dialog import SettingsDialog
from gui.templates_tab import TemplatesTab
from gui.extensions_tab import ExtensionsTab
from gui.project_selection_dialog import ProjectSelectionDialog
from gui.styles import (  # Import of new styles
    MAIN_STYLE,
    NAV_BUTTON_STYLE,
    BUTTON_STYLE,
    PRIMARY_BUTTON_STYLE,
    COLORS
)
from project_handler import synchronize_projects_with_default_folder
from utils import get_icon # Added for icon loading

# --- Constants ---
WINDOW_TITLE = "Godot Launcher"


class MainWindow(QMainWindow):
    """
    The main application window, containing the navigation and page content.
    Uses a QStackedWidget managed by custom navigation buttons instead of QTabWidget.
    """
    def __init__(self, data_manager: DataManager, parent: Optional[QWidget] = None):
        """
        Initializes the MainWindow.

        Args:
            data_manager: The central DataManager instance.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.data_manager = data_manager # Store reference to DataManager
        logging.info("Initializing MainWindow...")
        self.setWindowTitle(WINDOW_TITLE)
        self.setGeometry(100, 100, 1050, 750) # Initial position and size
        
        # Create a status bar before initializing the UI
        self.statusBar_widget = QStatusBar()
        self.setStatusBar(self.statusBar_widget)
        
        # Apply the main style (dark theme)
        self.setStyleSheet(MAIN_STYLE)
        
        self.init_ui()
        logging.info("MainWindow initialized.")

    def init_ui(self):
        """Initializes the main window UI using a QStackedWidget and custom navigation."""
        logging.debug("Initializing MainWindow UI with StackedWidget")
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(0) # No space between nav bar and stack

        # --- Top Bar (Settings Button) ---
        top_bar_layout = QHBoxLayout()
        top_bar_layout.addStretch(1) # Push button to the right
        self.settings_btn = QToolButton()
        self.settings_btn.setText("⚙️") # Gear icon
        font = self.settings_btn.font()
        font.setPointSize(14) # Make icon larger
        self.settings_btn.setFont(font)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.clicked.connect(self.open_settings_dialog)
        # Settings button style
        self.settings_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: transparent;
                border: none;
                color: {COLORS["text_primary"]};
            }}
            QToolButton:hover {{
                background-color: {COLORS["muted"]};
                border-radius: 4px;
            }}
        """)
        top_bar_layout.addWidget(self.settings_btn)
        self.main_layout.addLayout(top_bar_layout)

        # --- Custom Navigation Bar ---
        navigation_layout = QHBoxLayout()
        navigation_layout.setContentsMargins(10, 5, 10, 5)
        navigation_layout.setSpacing(10) # Increased space between buttons
        self.nav_button_group = QButtonGroup(self)
        self.nav_button_group.setExclusive(True)

        # Navigation panel with darker background
        nav_panel = QWidget()
        nav_panel.setStyleSheet(f"background-color: {COLORS['bg_dark']}; border-radius: 8px;")
        nav_panel_layout = QHBoxLayout(nav_panel)
        nav_panel_layout.setContentsMargins(10, 10, 10, 10)
        nav_panel_layout.setSpacing(5)

        # Navigation Buttons (Tabs)
        # Use standard Qt icons for a more integrated look
        style = self.style()
        icon_proj = style.standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon)
        icon_tmpl = style.standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
        # Use puzzle icon for Extensions
        icon_ext = style.standardIcon(QStyle.StandardPixmap.SP_FileDialogListView) # Puzzle icon

        self.btn_projects = QPushButton(icon_proj, " Projects")
        self.btn_templates = QPushButton(icon_tmpl, " Templates")
        self.btn_extensions = QPushButton(icon_ext, " Extensions")

        buttons = [self.btn_projects, self.btn_templates, self.btn_extensions]

        # Configure and add buttons to the navigation layout
        nav_panel_layout.addStretch(1) # Added stretch on the left to center buttons
        for i, btn in enumerate(buttons):
            btn.setCheckable(True)
            btn.setStyleSheet(NAV_BUTTON_STYLE)
            btn.setIconSize(QSize(22, 22)) # Increased icon size
            self.nav_button_group.addButton(btn, i)
            nav_panel_layout.addWidget(btn)
        nav_panel_layout.addStretch(1) # Stretch on the right to center buttons

        self.nav_button_group.buttonClicked.connect(self._change_page)
        
        navigation_layout.addWidget(nav_panel)
        self.main_layout.addLayout(navigation_layout)

        # --- QStackedWidget for Pages ---
        self.stacked_widget = QStackedWidget()
        # Style for the page container
        self.stacked_widget.setStyleSheet(f"""
            QStackedWidget {{
                background-color: {COLORS['bg_content']};
                border-radius: 8px;
                padding: 10px;
            }}
        """)

        logging.debug("Creating Tab instances (now Pages)...")
        # Pass the DataManager instance to child widgets (pages)
        self.projects_tab = ProjectsTab(self.data_manager)
        self.templates_tab = TemplatesTab(self.data_manager)
        self.extensions_tab = ExtensionsTab(self.data_manager)

        # Add pages to the stack IN THE SAME ORDER as the buttons
        pages = [self.projects_tab, self.templates_tab, self.extensions_tab]
        for page_widget in pages:
            self.stacked_widget.addWidget(page_widget)

        self.main_layout.addWidget(self.stacked_widget, 1) # Stack takes remaining space

        # Select the first page/button on startup
        self.btn_projects.setChecked(True)
        self.stacked_widget.setCurrentIndex(0)

        # --- Inter-Tab/Dialog Connections ---
        logging.debug("Connecting signals between Pages/Dialogs...")
        # When a project is created from a template, notify the projects tab
        # REMOVED: self.templates_tab.project_created_from_template.connect(
        #    self.projects_tab.add_and_select_project
        # )
        # The signal is now emitted by AssetDetailDialog and handled by MainWindow

        # Connect the signal from TemplatesTab that indicates a detail dialog needs connection
        self.templates_tab.asset_detail_dialog_shown.connect(self.connect_asset_detail_signals)

        # When the auto-install selection changes, potentially update Projects tab UI (if needed)
        # self.extensions_tab.auto_install_selection_changed.connect(self.projects_tab.update_install_button_state) # Example

        # --- Status Bar ---
        # Use the status bar already created in __init__
        self.statusBar_widget.showMessage("Ready.", 3000) # Initial message, disappears after 3s
        
        # Style for the status bar
        self.statusBar_widget.setStyleSheet(f"""
            QStatusBar {{
                background-color: {COLORS['bg_dark']};
                color: {COLORS['text_secondary']};
                border-top: 1px solid {COLORS['border']};
                padding: 2px;
            }}
        """)

        # Example: Connect a signal from a tab to update status bar
        self.projects_tab.status_message.connect(self.show_status_message)
        self.extensions_tab.status_message.connect(self.show_status_message)
        self.templates_tab.status_message.connect(self.show_status_message)

        logging.debug("Finished MainWindow UI creation (StackedWidget)")

    @pyqtSlot(AssetDetailDialog) # Expect an AssetDetailDialog instance
    def connect_asset_detail_signals(self, dialog: AssetDetailDialog):
        """Connects signals from the AssetDetailDialog instance to MainWindow slots."""
        logging.debug(f"Connecting signals for AssetDetailDialog (Asset ID: {dialog.asset_id})")
        # Connect the template creation signal
        dialog.template_download_finished.connect(self.handle_template_project_created)
        # Connect the extension installation request signal
        dialog.install_extension_requested.connect(self.handle_install_extension_request)
        # Disconnect when the dialog is finished using a lambda to avoid self-disconnection issues
        # Store the connection to allow explicit disconnection if needed
        try:
            # Use a direct connection
            dialog.finished.connect(self.on_asset_detail_dialog_finished)
        except Exception as e:
            logging.error(f"Error connecting finished signal for dialog {dialog.asset_id}: {e}")

    @pyqtSlot(int) # Argument is the result code from QDialog.finished
    def on_asset_detail_dialog_finished(self, result: int):
        """Slot called when an AssetDetailDialog finishes (accepted or rejected)."""
        sender_dialog = self.sender()
        if isinstance(sender_dialog, AssetDetailDialog):
            logging.debug(f"AssetDetailDialog (ID: {sender_dialog.asset_id}) finished with result: {result}. Attempting to disconnect signals.")
            # We don't need to manually disconnect other signals here,
            # Qt handles signal disconnection when the sender object (dialog) is deleted.
            # The dialog should be deleted shortly after finished is emitted.
            # If we needed manual disconnection (e.g., dialog is reused), we'd do it here.
            # self.disconnect_asset_detail_signals(sender_dialog) # Not strictly necessary usually
            pass # Signals should disconnect automatically when dialog is deleted
        else:
            logging.warning("on_asset_detail_dialog_finished called by unexpected sender type.")

    @pyqtSlot(str, str)
    def handle_template_project_created(self, project_name: str, project_path: str):
        """Handles the signal emitted when a project is successfully created from a template."""
        logging.info(f"MainWindow: Received template_download_finished signal. Project: '{project_name}', Path: '{project_path}'")
        self.show_status_message(f"Project '{project_name}' created successfully from template!", 5000)

        # Add the project to DataManager
        try:
            logging.debug(f"Adding new template project '{project_name}' at {project_path} to DataManager.")
            self.data_manager.add_project(project_name, project_path)
            # Optionally save immediately, though usually saved on exit
            # self.data_manager.save_data()
        except Exception as e:
            logging.error(f"Failed to add project '{project_name}' to DataManager: {e}", exc_info=True)
            # Show a non-critical error, the project exists on disk but isn't tracked
            self.show_status_message(f"Error adding '{project_name}' to project list. Please restart or add manually.", 8000)

        # Update the ProjectsTab
        self.projects_tab.add_and_select_project(project_name, project_path)
        # Switch to the projects tab to show the result
        self.stacked_widget.setCurrentWidget(self.projects_tab)
        self.btn_projects.setChecked(True)

    @pyqtSlot(QAbstractButton)
    def _change_page(self, clicked_button: QAbstractButton):
        """Switches the visible page in the QStackedWidget based on the clicked navigation button."""
        # Get the ID associated with the clicked button
        button_id = self.nav_button_group.id(clicked_button)
        logging.info(f"Page change requested to button ID: {button_id} ({clicked_button.text()})")
        if button_id != -1: # Check if the ID is valid
            self.stacked_widget.setCurrentIndex(button_id)
        else:
            # This should not happen if buttons are correctly added to the group
            logging.warning(f"Received click from button not belonging to the group: {clicked_button}")

    def open_settings_dialog(self):
        """Opens the settings dialog window."""
        logging.info("Opening Settings Dialog from MainWindow...")
        # Create a new instance each time or reuse a single instance?
        # Creating new ensures fresh state, but might be less efficient if opened frequently.
        # Reusing requires careful state management within SettingsDialog if needed.
        # Let's create a new one each time for simplicity.
        dialog = SettingsDialog(self.data_manager, self) # Pass DataManager and parent
        # Connect signal *before* showing the dialog
        dialog.godot_path_changed.connect(self.update_status_godot_path)
        dialog.exec() # Show modally
        logging.info("Settings Dialog closed.")

    def update_status_godot_path(self):
        """Updates the status bar when the Godot path changes via settings."""
        godot_path = self.data_manager.get_godot_path()
        if godot_path:
            self.show_status_message(f"Default Godot path updated: {godot_path}", 5000)
        else:
            self.show_status_message("Default Godot path cleared (will use system PATH).", 5000)

    def show_status_message(self, message: str, timeout: int = 3000):
        """Displays a message in the status bar."""
        logging.debug(f"Status update: {message} (timeout: {timeout}ms)")
        if hasattr(self, 'statusBar_widget'):
            self.statusBar_widget.showMessage(message, timeout)

    @pyqtSlot(int)
    def handle_install_extension_request(self, asset_id: int):
        """Handles the request to install an extension, usually emitted from AssetDetailDialog."""
        logging.info(f"MainWindow: Received install request for extension ID {asset_id}")
        
        # Get extension details
        try:
            from api_clients import fetch_asset_details_sync
            extension_details = fetch_asset_details_sync(asset_id)
            extension_name = extension_details.get('title', f"Extension #{asset_id}")
        except Exception as e:
            logging.error(f"Failed to fetch details for extension {asset_id}: {e}")
            extension_name = f"Extension #{asset_id}"
            
        # Check if there are projects available in the DataManager
        projects = self.data_manager.get_projects()
        if not projects:
            logging.warning("Extension install requested, but no projects are available.")
            QMessageBox.warning(
                self, 
                "No Projects Available", 
                "Before installing an extension, you must create or import at least one project."
            )
            return
            
        # Import the project selection dialog
        from gui.project_selection_dialog import ProjectSelectionDialog
        
        # Show the project selection dialog
        dialog = ProjectSelectionDialog(self.data_manager, asset_id, extension_name, self)
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            # Get selected projects
            selected_projects = dialog.get_selected_projects()
            
            if not selected_projects:
                # This should not happen since the dialog already checks this condition
                logging.warning("No projects were selected in the dialog.")
                return
                
            # Delegate installation to ProjectsTab for the selected projects
            self.projects_tab.start_multi_project_extension_installation(asset_id, selected_projects)
        else:
            logging.info(f"User cancelled installation of extension ID {asset_id}")
            
    def closeEvent(self, event):
        """Handles the application close event, checking for ongoing operations."""
        logging.info("Application close requested...")

        # Check if any background operations are running in the tabs
        template_op_running = (self.templates_tab.download_thread and self.templates_tab.download_thread.isRunning()) or \
                              (self.templates_tab.api_thread and self.templates_tab.api_thread.isRunning())
        project_creation_running = self.projects_tab.auto_installer_cancel_func is not None
        project_install_running = self.projects_tab.multi_install_cancel_func is not None

        if template_op_running or project_creation_running or project_install_running:
            ops_in_progress = []
            if template_op_running: ops_in_progress.append("Template Download/Search")
            if project_creation_running: ops_in_progress.append("Project Creation/Auto-Install")
            if project_install_running: ops_in_progress.append("Extension Installation")

            logging.warning(f"Attempting to close with operations in progress: {ops_in_progress}")
            reply = QMessageBox.question(
                self, "Exit Confirmation",
                f"Operations are in progress:\n- {'\n- '.join(ops_in_progress)}\n\nExit and cancel these operations?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No, # Default to No
            )

            if reply == QMessageBox.StandardButton.No:
                logging.info("Application close cancelled by user.")
                event.ignore() # Prevent closing
                return
            else:
                logging.info("Cancelling ongoing operations before closing...")
                # Trigger cancellation functions in respective tabs
                if template_op_running: self.templates_tab.cancel_current_operation()
                if project_creation_running: self.projects_tab.cancel_project_creation_or_auto_install()
                if project_install_running: self.projects_tab.cancel_selected_extensions_installation()
                # Allow event loop to process cancellations briefly? Might not be necessary.
                self.perform_final_save_and_accept(event) # Proceed with saving and closing
        else:
            # No operations running, proceed directly to save and close
            self.perform_final_save_and_accept(event)

    def perform_final_save_and_accept(self, event):
        """Performs the final data save and accepts the close event."""
        logging.info("Saving final application data...")
        try:
            # Use the save_data method of the DataManager instance
            self.data_manager.save_data()
            logging.info("Application data saved. Closing application.")
            event.accept() # Allow the window to close
        except Exception as e:
             logging.exception("Critical error during final data save!")
             QMessageBox.critical(self, "Save Error", f"Could not save application data on exit:\n{e}")
             # Should we still close? Maybe ask the user? For now, accept the close event anyway.
             event.accept()
