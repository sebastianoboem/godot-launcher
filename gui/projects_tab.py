# -*- coding: utf-8 -*-
# gui/projects_tab.py

import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List, Tuple

from PyQt6.QtCore import QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

# Import DataManager and necessary functions from other modules
from data_manager import DataManager # Use the DataManager class
from project_handler import (
    create_project_structure,
    install_extensions_logic,
    launch_project_editor,
    launch_project_run,
    synchronize_projects_with_default_folder,
    validate_godot_path,
    get_project_name_from_file,
    get_godot_executable_for_path,
    scan_projects_folder,
    get_godot_version_string,
    ExtensionInstaller,
)
from gui.new_project_dialog import NewProjectDialog
from gui.styles import (  # Import of new styles
    BUTTON_STYLE, PRIMARY_BUTTON_STYLE, INPUT_STYLE,
    LIST_WIDGET_STYLE, ITEM_SELECTED_STYLE,
    FRAME_STYLE, GROUP_BOX_STYLE, COLORS,
    SPLITTER_STYLE, PROGRESS_BAR_STYLE, TITLE_LABEL_STYLE,
    DANGER_BUTTON_STYLE
)
from validators import is_valid_url # Usa import assoluto
# from utils import cancel_process_tree # Rimosso, funzione non trovata/usata


class ProjectsTab(QWidget):
    """
    QWidget representing the 'Projects' tab in the main application window.
    Manages listing, creating, importing, launching, and removing Godot projects.
    Also handles the default projects folder setting and synchronization.
    """
    project_list_changed = pyqtSignal() # Emitted when the project list is modified
    status_message = pyqtSignal(str, int) # Emitted to show messages in the main window status bar (message, timeout_ms)

    def __init__(self, data_manager: DataManager):
        """
        Initializes the ProjectsTab.

        Args:
            data_manager: The central DataManager instance for accessing application data.
        """
        super().__init__()
        self.data_manager = data_manager # Store the DataManager instance
        self.current_project_path: Optional[Path] = None # Path of the currently selected project
        self.auto_installer_cancel_func: Optional[callable] = None # Function to cancel project creation/auto-install
        self.multi_install_cancel_func: Optional[callable] = None # Function to cancel multi-extension install
        self.init_ui()
        self.refresh_project_list_display() # Initial population of the list

    def init_ui(self):
        """Initializes the user interface elements of the tab."""
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        # Apply QSplitter style
        splitter.setStyleSheet(SPLITTER_STYLE)

        # --- Left Panel (Project List and Folder Settings) ---
        left_widget = QWidget()
        left_widget.setStyleSheet(f"background-color: {COLORS['bg_content']};")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Default Projects Folder GroupBox
        pfg = QGroupBox("Default Projects Folder:")
        pfg.setStyleSheet(GROUP_BOX_STYLE)
        pfl = QVBoxLayout(pfg)
        hpf = QHBoxLayout()
        # Use DataManager to get the initial path
        self.pfe = QLineEdit(self.data_manager.get_default_projects_folder() or "")
        self.pfe.setPlaceholderText("e.g., C:\\Users\\YourName\\GodotProjects")
        self.pfe.setStyleSheet(INPUT_STYLE)
        self.pfe.textChanged.connect(self.validate_projects_folder_display)
        self.bpb = QPushButton("Browse...")
        self.bpb.setStyleSheet(BUTTON_STYLE)
        self.spb_save = QPushButton("Save Path")
        self.spb_save.setStyleSheet(PRIMARY_BUTTON_STYLE)
        hpf.addWidget(QLabel("Path:"))
        hpf.addWidget(self.pfe, 1) # Line edit takes available space
        hpf.addWidget(self.bpb)
        hpf.addWidget(self.spb_save)
        pfl.addLayout(hpf)
        self.pfsl = QLabel("") # Status label for path validation
        pfl.addWidget(self.pfsl)
        info_label = QLabel("<small>Scanned on startup. Use 'Synchronize' to update manually.</small>")
        info_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        pfl.addWidget(info_label)
        left_layout.addWidget(pfg)

        # Registered Projects List
        projects_label = QLabel("<b>Registered Projects:</b>")
        projects_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12pt; margin-top: 10px;")
        left_layout.addWidget(projects_label)
        self.plw = QListWidget() # project_list_widget
        self.plw.setStyleSheet(LIST_WIDGET_STYLE)
        self.plw.itemSelectionChanged.connect(self.on_project_selection_changed)
        self.plw.itemDoubleClicked.connect(self.launch_selected_project)
        left_layout.addWidget(self.plw, 1) # List takes available vertical space

        # Project Action Buttons (New, Import, Sync)
        lbl = QHBoxLayout()
        self.npb = QPushButton("➕ New") # new_project_button
        self.npb.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.ipb = QPushButton("📥 Import") # import_project_button
        self.ipb.setStyleSheet(BUTTON_STYLE)
        self.spb_sync = QPushButton("🔄 Synchronize") # sync_projects_button
        self.spb_sync.setStyleSheet(BUTTON_STYLE)
        lbl.addWidget(self.npb)
        lbl.addWidget(self.ipb)
        lbl.addWidget(self.spb_sync)
        left_layout.addLayout(lbl)
        splitter.addWidget(left_widget)

        # --- Right Panel (Selected Project Details and Actions) ---
        rw = QFrame() # right_widget
        rw.setFrameShape(QFrame.Shape.StyledPanel)
        rw.setStyleSheet(FRAME_STYLE)
        rl = QVBoxLayout(rw) # right_layout
        rl.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Project Name and Path Labels
        self.pnl = QLabel("<i>Select a project...</i>") # project_name_label
        self.pnl.setStyleSheet(TITLE_LABEL_STYLE)
        rl.addWidget(self.pnl)
        self.ppl = QLabel("") # project_path_label
        self.ppl.setWordWrap(True)
        self.ppl.setStyleSheet(f"color: {COLORS['text_secondary']}; margin-bottom: 10px; border: 0px;")
        rl.addWidget(self.ppl)
        rl.addSpacing(15)

        # Selected Project Action Buttons (Launch, Open Folder, Remove)
        abl = QHBoxLayout() # action_button_layout
        self.lb = QPushButton("🚀 Launch Editor") # launch_button (renamed for clarity)
        self.lb.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.rb = QPushButton("▶️ Run Project") # run_button (added)
        self.rb.setStyleSheet(BUTTON_STYLE)
        self.ofb = QPushButton("📂 Open Folder") # open_folder_button
        self.ofb.setStyleSheet(BUTTON_STYLE)
        self.rmb = QPushButton("❌ Remove") # remove_button
        self.rmb.setStyleSheet(DANGER_BUTTON_STYLE)
        self.lb.setEnabled(False)
        self.rb.setEnabled(False) # Added
        self.ofb.setEnabled(False)
        self.rmb.setEnabled(False)
        abl.addWidget(self.lb)
        abl.addWidget(self.rb) # Added
        abl.addWidget(self.ofb)
        abl.addStretch()
        abl.addWidget(self.rmb)
        rl.addLayout(abl)
        rl.addSpacing(20)

        # Install Selected Extensions GroupBox
        self.isg = QGroupBox("Install Selected Extensions") # install_selected_groupbox
        self.isg.setStyleSheet(GROUP_BOX_STYLE)
        isl = QVBoxLayout(self.isg) # install_selected_layout
        self.isil = QLabel(
            "Install extensions selected in the 'Extensions' tab into the current project."
        ) # install_selected_info_label
        self.isil.setWordWrap(True)
        self.isil.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10pt; border: 0px;")
        isl.addWidget(self.isil)
        self.isb = QPushButton("📥 Install Selected") # install_selected_button
        self.isb.setStyleSheet(PRIMARY_BUTTON_STYLE)
        isl.addWidget(self.isb)
        self.misl = QLabel("") # multi_install_status_label
        self.misl.setWordWrap(True)
        self.misl.setVisible(False)
        isl.addWidget(self.misl)
        self.mipb = QProgressBar() # multi_install_progress_bar
        self.mipb.setStyleSheet(PROGRESS_BAR_STYLE)
        self.mipb.setVisible(False)
        self.mipb.setTextVisible(False)
        isl.addWidget(self.mipb)
        self.micb = QPushButton("Cancel") # multi_install_cancel_button
        self.micb.setStyleSheet(BUTTON_STYLE)
        self.micb.setVisible(False)
        isl.addWidget(self.micb, 0, Qt.AlignmentFlag.AlignRight)
        self.isg.setEnabled(False) # Disabled initially
        rl.addWidget(self.isg)
        rl.addStretch() # Push elements to the top
        splitter.addWidget(rw)

        # Configure Splitter
        splitter.setSizes([350, 450]) # Initial sizes for left and right panels
        main_layout.addWidget(splitter)

        # --- Status Bar Frame (for project creation/auto-install) ---
        self.sbf = QFrame() # status_bar_frame
        self.sbf.setFrameShape(QFrame.Shape.StyledPanel)
        self.sbf.setStyleSheet(FRAME_STYLE)
        sbl_ = QHBoxLayout(self.sbf) # status_bar_layout_internal
        sbl_.setContentsMargins(5, 2, 5, 2)
        self.sbl = QLabel("") # status_bar_label
        self.sbp = QProgressBar() # status_bar_progress
        self.sbp.setStyleSheet(PROGRESS_BAR_STYLE)
        self.sbp.setTextVisible(False)
        self.sbc = QPushButton("Cancel Creation") # status_bar_cancel_button
        self.sbc.setStyleSheet(BUTTON_STYLE)
        sbl_.addWidget(self.sbl, 1)
        sbl_.addWidget(self.sbp)
        sbl_.addWidget(self.sbc)
        self.sbf.setVisible(False) # Hidden initially
        main_layout.addWidget(self.sbf)

        # --- Connect Signals ---
        self.npb.clicked.connect(self.show_create_new_project_dialog)
        self.ipb.clicked.connect(self.import_project)
        self.spb_sync.clicked.connect(self.sync_and_refresh)
        self.lb.clicked.connect(self.launch_selected_project)
        self.rb.clicked.connect(self.run_selected_project)
        self.rmb.clicked.connect(self.remove_selected_project)
        self.ofb.clicked.connect(self.open_selected_project_folder)
        self.bpb.clicked.connect(self.browse_for_projects_folder)
        self.spb_save.clicked.connect(self.save_default_projects_folder_path)
        self.sbc.clicked.connect(self.cancel_project_creation_or_auto_install)
        self.isb.clicked.connect(self.start_selected_extensions_installation)
        self.micb.clicked.connect(self.cancel_selected_extensions_installation)

        # Initial validation of the projects folder path display
        self.validate_projects_folder_display()

    def browse_for_projects_folder(self):
        """Opens a dialog to select the default projects folder."""
        current_path = self.pfe.text()
        start_dir = current_path if Path(current_path).is_dir() else str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self, "Select Default Projects Folder", start_dir
        )
        if folder:
            self.pfe.setText(folder) # Update the line edit

    def validate_projects_folder_display(self) -> bool:
        """Validates the path in the projects folder line edit and updates UI feedback."""
        path_str = self.pfe.text().strip()
        style = ""
        status_text = ""
        is_valid = False
        can_sync = False

        if not path_str:
            status_text = "<font color='gray'>No folder set.</font>"
            is_valid = True # Empty is considered valid for saving (means 'unset')
        else:
            try:
                p = Path(path_str)
                if p.is_dir():
                    status_text = "<font color='green'>Valid.</font>"
                    style = "border: 1px solid green;"
                    is_valid = True
                    can_sync = True
                else:
                    status_text = "<font color='red'>Path is not a valid directory.</font>"
                    style = "border: 1px solid red;"
            except Exception as e: # Catch potential Path errors for invalid syntax
                 status_text = f"<font color='red'>Invalid path syntax: {e}</font>"
                 style = "border: 1px solid red;"

        self.pfsl.setText(status_text)
        self.spb_save.setEnabled(is_valid) # Can save if path is valid (or empty)
        self.spb_sync.setEnabled(can_sync) # Can only sync if path is a valid directory
        return is_valid

    def save_default_projects_folder_path(self):
        """Saves the validated default projects folder path using DataManager."""
        path_str = self.pfe.text().strip()
        if self.validate_projects_folder_display(): # Re-validate before saving
            try:
                old_path = self.data_manager.get_default_projects_folder()
                new_path = path_str if path_str else None # Store None if empty
                # Use DataManager to save the path
                self.data_manager.set_default_projects_folder(new_path)
                QMessageBox.information(self, "Saved", "Default projects folder path updated.")
                # If the path changed and is now valid, trigger a sync
                if old_path != new_path and new_path:
                    self.sync_and_refresh()
            except Exception as e:
                logging.exception("Failed to save default projects folder path.")
                QMessageBox.critical(self, "Error", f"Failed to save path:\n{e}")
        else:
            QMessageBox.warning(self, "Invalid Path", "The specified path is not valid.")

    def sync_and_refresh(self):
        """Synchronizes the project list with the default folder and refreshes the display."""
        logging.info("Manual project synchronization requested...")
        # Pass DataManager to the synchronization function
        updated = synchronize_projects_with_default_folder(self.data_manager)
        self.refresh_project_list_display() # Update the UI list
        msg = "Project list synchronized." + (
            " (No changes detected)" if not updated else ""
        )
        QMessageBox.information(self, "Synchronize", msg)

    def refresh_project_list_display(self):
        """Clears and repopulates the project list widget based on DataManager data."""
        logging.debug("Refreshing project list UI")
        # Store selection before clearing
        selected_item_path = None
        current_item = self.plw.currentItem()
        if current_item:
            selected_item_path = current_item.data(Qt.ItemDataRole.UserRole)

        self.plw.clear()
        # Use DataManager to get the current projects
        projects = self.data_manager.get_projects()

        if not projects:
            item = QListWidgetItem("No registered projects.")
            item.setFlags(Qt.ItemFlag.NoItemFlags) # Make it unselectable
            self.plw.addItem(item)
        else:
            # Sort projects by name for consistent display
            for project_name, path_str in sorted(projects.items()):
                item = QListWidgetItem(project_name)
                item.setData(Qt.ItemDataRole.UserRole, path_str) # Store path in item data
                tooltip_text = f"Name: {project_name}\nPath: {path_str}"
                try:
                    proj_path = Path(path_str)
                    folder_name = proj_path.name
                    tooltip_text += f"\nFolder: {folder_name}"
                    # Check if project path is valid and exists
                    if (
                        not proj_path.exists()
                        or not (proj_path / "project.godot").is_file()
                    ):
                        item.setForeground(Qt.GlobalColor.gray) # Gray out invalid entries
                        tooltip_text += "\n(WARNING: Path missing or invalid!)"
                except Exception as e: # Catch errors resolving path
                    item.setForeground(Qt.GlobalColor.red)
                    tooltip_text += f"\n(ERROR: Invalid path - {e})"

                item.setToolTip(tooltip_text)
                self.plw.addItem(item)
                # Restore selection if this item was previously selected
                if path_str == selected_item_path:
                    self.plw.setCurrentItem(item)

        # If no item is selected after refresh (e.g., previous selection was removed), select the first one if list is not empty
        if not self.plw.currentItem() and self.plw.count() > 0 and self.plw.item(0).flags() != Qt.ItemFlag.NoItemFlags:
            self.plw.setCurrentRow(0)

        # Update the right panel based on the current selection (or lack thereof)
        self.on_project_selection_changed()
        self.project_list_changed.emit() # Notify other parts of the app

    def on_project_selection_changed(self):
        """Updates the right panel details based on the selected project in the list."""
        current_item = self.plw.currentItem()
        has_valid_selection = False
        project_is_valid_and_exists = False
        self.current_project_path = None # Reset current path

        if current_item and current_item.flags() != Qt.ItemFlag.NoItemFlags: # Check if it's a real item
            project_name = current_item.text()
            path_str = current_item.data(Qt.ItemDataRole.UserRole)
            has_valid_selection = True
            self.pnl.setText(project_name) # Update name label

            if path_str:
                try:
                    proj_path = Path(path_str)
                    folder_name = proj_path.name
                    # Display path and folder name
                    self.ppl.setText(f"📍 {path_str}\n   (Folder: {folder_name})")
                    # Check if the project path is valid
                    if proj_path.is_dir() and (proj_path / "project.godot").is_file():
                        project_is_valid_and_exists = True
                        self.current_project_path = proj_path # Store valid path
                    else:
                        # Indicate invalid path
                        self.ppl.setText(
                            f"📍 <font color='red'>{path_str} (Missing/Invalid)</font>\n   (Folder: {folder_name})"
                        )
                        self.ppl.setStyleSheet("color: red;")
                except Exception as e:
                    logging.error(f"Error processing path for project '{project_name}': {e}")
                    self.ppl.setText(f"<font color='red'>Error processing path: {e}</font>")
            else:
                # Path data is missing
                self.ppl.setText("<font color='red'>Path not defined</font>")
        else:
            # No valid project selected
            self.pnl.setText("<i>No project selected</i>")
            self.ppl.setText("")

        # Enable/disable action buttons based on selection validity
        self.lb.setEnabled(project_is_valid_and_exists)
        self.rb.setEnabled(project_is_valid_and_exists)
        self.ofb.setEnabled(has_valid_selection and self.current_project_path is not None)
        self.rmb.setEnabled(has_valid_selection)
        # Enable/disable extension installation groupbox
        self.isg.setEnabled(project_is_valid_and_exists)
        # Enable install button only if project is valid and no other install is running
        self.isb.setEnabled(project_is_valid_and_exists and self.multi_install_cancel_func is None)

    def show_create_new_project_dialog(self):
        """Shows the custom dialog for creating a new Godot project."""
        logging.info("Opening create new project dialog...")
        # Pass the DataManager instance to the dialog
        dialog = NewProjectDialog(self.data_manager, self)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            details = dialog.get_project_details()
            if details:
                project_name = details["name"]
                project_path = details["path"]
                renderer = details["renderer"]
                include_extensions = details["include_extensions"]
                edit_now = details["edit_now"]
                logging.info(
                    f"New project dialog accepted. Name: {project_name}, Path: {project_path}, "
                    f"Renderer: {renderer}, Include Ext: {include_extensions}, Edit Now: {edit_now}"
                )
                # Pass the new options to the creation method
                self.start_project_creation(
                    project_path, project_name, renderer, include_extensions, edit_now
                )
            else:
                # This case should ideally not happen if accept() validates
                logging.error("New project dialog accepted but details were invalid.")
                QMessageBox.critical(self, "Error", "Could not retrieve valid project details.")
        else:
            logging.info("New project dialog cancelled.")

    def start_project_creation(self, project_path: Path, project_name: str, renderer: str,
                                 include_extensions: bool, edit_now: bool):
        """Handles the process of creating project structure and optionally auto-installing extensions."""
        logging.info(f"Starting creation for project '{project_name}' at '{project_path}' with renderer '{renderer}'")
        # Disable controls and show status bar
        self.set_controls_enabled(False)
        self.sbf.setVisible(True)
        self.sbl.setText(f"Creating '{project_name}' structure...")
        self.sbp.setRange(0, 100) # Progress bar for creation steps
        self.sbp.setValue(5)
        self.sbc.setVisible(True)
        self.sbc.setEnabled(False) # Cannot cancel structure creation itself easily
        self.auto_installer_cancel_func = None # Reset cancel function
        QApplication.processEvents()

        # Get Godot path from DataManager
        active_godot_path = self.data_manager.get_godot_path()
        # Validate Godot path before proceeding (needed for version detection in create_project_structure)
        if not active_godot_path or not validate_godot_path(active_godot_path):
             logging.warning("Cannot create project: Default Godot path is not set or invalid.")
             QMessageBox.warning(self, "Error", "Default Godot path is not set or invalid.\nPlease set it in the Settings tab.")
             self.reset_creation_ui()
             self.set_controls_enabled(True) # Re-enable controls after error
             return

        # Create the basic project structure
        if not create_project_structure(project_path, project_name, active_godot_path, renderer):
            # Error message is shown by create_project_structure
            self.reset_creation_ui()
            self.set_controls_enabled(True) # Re-enable controls after failure
            return # Exit if structure creation fails

        # Add project to list and update UI (using DataManager)
        self.sbl.setText("Project structure created.")
        self.sbp.setValue(10)
        QApplication.processEvents()
        self.data_manager.add_project(project_name, str(project_path))
        self.refresh_project_list_display()
        # Select the newly created project in the list
        items = self.plw.findItems(project_name, Qt.MatchFlag.MatchExactly)
        if items: self.plw.setCurrentItem(items[0])
        self.current_project_path = project_path # Update current path

        # Auto-install extensions (using DataManager to get IDs)
        # Check the include_extensions flag passed from the dialog
        if include_extensions:
            auto_install_ids = self.data_manager.get_auto_install_extensions()
            if auto_install_ids:
                logging.info(f"Starting auto-installation for {len(auto_install_ids)} extensions.")
                self.sbl.setText(f"Installing {len(auto_install_ids)} auto-selected extensions...")
                self.sbp.setValue(15)
                self.sbc.setEnabled(True) # Allow cancelling the auto-install part
                QApplication.processEvents()

                # Define callbacks for the installation logic
                def progress_callback(percent: int):
                    if self.sbf.isVisible(): # Check if UI is still relevant
                        if percent >= 0:
                            self.sbp.setRange(0, 100)
                            # Scale auto-install progress (0-100) to the remaining progress bar space (15-100)
                            self.sbp.setValue(15 + int(percent * 0.85))
                        else:
                            self.sbp.setRange(0, 0) # Indeterminate

                def status_callback(message: str):
                    if self.sbf.isVisible(): self.sbl.setText(message)

                def finished_callback(success: bool, final_message: str):
                    logging.info(f"Project creation auto-install FINISHED. Success: {success}, Message: {final_message}")
                    title = "Project Created" if success else "Creation/Install Error"
                    msg = f"Project '{project_name}' created.\n"
                    if not auto_install_ids: # Should not happen if we are here, but safe check
                        msg += "No auto-install extensions were configured."
                    elif success:
                        msg += "Auto-selected extensions installed successfully."
                    else:
                        msg += f"Errors during auto-installation:\n{final_message}"

                    if success: QMessageBox.information(self, title, msg)
                    else: QMessageBox.warning(self, title, msg)

                    # Reset UI and explicitly re-enable controls
                    logging.debug("Calling reset_creation_ui from finished_callback...")
                    self.reset_creation_ui()
                    logging.debug("Calling set_controls_enabled(True) from finished_callback...")
                    self.set_controls_enabled(True) # Ensure controls are re-enabled

                    # Launch editor if requested
                    if edit_now:
                        QTimer.singleShot(100, self.launch_selected_project) # Launch after a short delay

                # Start the installation logic, passing the DataManager
                self.auto_installer_cancel_func = install_extensions_logic(
                    auto_install_ids, project_path, self.data_manager,
                    self.sbl, self.sbp, self.sbc, finished_callback
                )
                # If install_extensions_logic returns None immediately (e.g., no valid IDs), call finished_callback
                if not self.auto_installer_cancel_func:
                    logging.info("No extensions to auto-install (install_extensions_logic returned None).")
                    # Need to call the defined finished_callback here as well
                    finished_callback(True, "No extensions configured for auto-install.")
            else:
                 # No auto-install extensions configured in DataManager
                 logging.info("No auto-install extensions configured in DataManager.")
                 QMessageBox.information(self, "Project Created", f"Project '{project_name}' created successfully.")
                 self.reset_creation_ui() # Reset UI
                 self.set_controls_enabled(True) # Re-enable controls
                 # Launch editor if requested
                 if edit_now:
                     QTimer.singleShot(100, self.launch_selected_project)

        else:
            # User chose not to include extensions
            logging.info("User chose not to include default extensions.")
            QMessageBox.information(self, "Project Created", f"Project '{project_name}' created successfully.")
            self.reset_creation_ui() # Reset UI
            self.set_controls_enabled(True) # Re-enable controls
            # Launch editor if requested
            if edit_now:
                QTimer.singleShot(100, self.launch_selected_project) # Launch after a short delay

    def reset_creation_ui(self):
        """Resets the UI elements related to project creation/auto-install status."""
        logging.debug("Resetting project creation status UI")
        self.sbf.setVisible(False)
        self.sbl.clear()
        self.sbp.setValue(0)
        self.sbp.setRange(0, 100) # Reset range
        self.sbc.setEnabled(False)
        self.auto_installer_cancel_func = None
        # Do not re-enable controls here; it's handled by the finished_callback or error handling paths
        # Update button states based on current selection instead
        self.on_project_selection_changed()

    def set_controls_enabled(self, enabled: bool):
        """Enables or disables the main controls in the Projects tab."""
        logging.debug(f"Setting ProjectsTab controls enabled={enabled}")
        # Left panel controls
        self.plw.setEnabled(enabled)
        self.npb.setEnabled(enabled)
        self.ipb.setEnabled(enabled)
        self.spb_sync.setEnabled(enabled and self.validate_projects_folder_display() and bool(self.pfe.text().strip())) # Sync only if path valid
        self.pfe.setEnabled(enabled)
        self.bpb.setEnabled(enabled)
        self.spb_save.setEnabled(enabled and self.validate_projects_folder_display()) # Save only if path valid/empty

        # Right panel controls are handled by on_project_selection_changed based on list state
        if enabled:
            self.on_project_selection_changed()
        else:
            # Explicitly disable right panel buttons when overall controls are disabled
            self.lb.setEnabled(False)
            self.rb.setEnabled(False)
            self.ofb.setEnabled(False)
            self.rmb.setEnabled(False)
            self.isg.setEnabled(False)
            self.isb.setEnabled(False)


    def cancel_project_creation_or_auto_install(self):
        """Cancels the ongoing auto-installation process during project creation."""
        if self.auto_installer_cancel_func:
            logging.info("Requesting cancellation of project creation's auto-install phase.")
            reply = QMessageBox.question(
                self,
                "Cancel Auto-Install?",
                "Cancel the automatic installation of extensions for the new project?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                logging.info("Cancellation confirmed by user.")
                self.sbc.setEnabled(False) # Disable cancel button immediately
                self.sbl.setText("Cancelling auto-install...")
                self.auto_installer_cancel_func() # Call the cancel function
                # The finished_callback will handle UI reset and re-enabling controls
            else:
                logging.info("Cancellation aborted by user.")
        else:
            logging.warning("No cancel function available (project creation/auto-install not running or not cancellable).")

    def import_project(self):
        """Imports an existing Godot project folder."""
        logging.info("Starting project import process.")
        # Use DataManager to get the starting directory for the dialog
        start_dir = self.data_manager.get_default_projects_folder() or str(Path.home())
        project_dir = QFileDialog.getExistingDirectory(self, "Import Existing Godot Project Folder", start_dir)

        if not project_dir:
            logging.info("Project import cancelled by user.")
            return

        path = Path(project_dir)
        project_name = get_project_name_from_file(path)

        if not project_name:
            logging.warning(f"Import failed: Could not read project name from {path / 'project.godot'}")
            QMessageBox.warning(self, "Import Error", f"Could not read project name from 'project.godot' in the selected folder:\n{path}")
            return

        path_str = str(path.resolve())
        # Use DataManager to get existing projects
        stored_projects = self.data_manager.get_projects()

        # Check if this exact path is already registered
        existing_name_for_path = None
        for name, stored_path_str in stored_projects.items():
            try:
                if Path(stored_path_str).resolve() == path.resolve():
                    existing_name_for_path = name
                    break
            except Exception:
                pass # Ignore errors resolving potentially invalid stored paths

        if existing_name_for_path:
            # Path is already registered
            if existing_name_for_path == project_name:
                # Name also matches, inform user it's already there
                logging.info(f"Project '{project_name}' at path '{path}' is already registered.")
                QMessageBox.information(self, "Already Registered", f"The project '{project_name}' at this location is already in the list.")
            else:
                # Path matches, but name in project.godot is different from stored name
                logging.warning(f"Path '{path}' already registered as '{existing_name_for_path}', but project file name is '{project_name}'.")
                reply = QMessageBox.question(
                    self,
                    "Path Exists, Name Mismatch",
                    f"This project path is already registered as '{existing_name_for_path}'.\n"
                    f"The 'project.godot' file indicates the name is '{project_name}'.\n\n"
                    f"Update the registered name to '{project_name}'?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    logging.info(f"Updating registered name from '{existing_name_for_path}' to '{project_name}'.")
                    # Use DataManager to remove old and add new entry
                    self.data_manager.remove_project(existing_name_for_path)
                    self.data_manager.add_project(project_name, path_str)
                    self.refresh_project_list_display()
                    QMessageBox.information(self, "Name Updated", f"Project name updated to '{project_name}'.")
                else:
                    logging.info("Name update cancelled by user.")
                    return # Do nothing further
            # Select the existing/updated item
            items = self.plw.findItems(project_name, Qt.MatchFlag.MatchExactly)
            if items: self.plw.setCurrentItem(items[0])
            return # End import process

        # Path is not registered, check if the name is already used by another path
        if project_name in stored_projects:
            logging.warning(f"Project name '{project_name}' is already registered for a different path: {stored_projects[project_name]}.")
            reply = QMessageBox.question(
                self,
                "Duplicate Project Name",
                f"A different project is already registered with the name '{project_name}'.\n\n"
                f"Overwrite the existing entry with this new project path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No, # Default to No
            )
            if reply == QMessageBox.StandardButton.No:
                logging.info("Import cancelled due to duplicate name conflict.")
                return # Cancel import

        # Add the new project using DataManager
        logging.info(f"Adding/Overwriting project '{project_name}' with path '{path_str}'")
        self.data_manager.add_project(project_name, path_str)
        self.refresh_project_list_display()
        QMessageBox.information(self, "Project Imported", f"Project '{project_name}' was successfully added/updated.")
        # Select the newly added item
        items = self.plw.findItems(project_name, Qt.MatchFlag.MatchExactly)
        if items: self.plw.setCurrentItem(items[0])

    def launch_selected_project(self):
        """Launches the Godot editor for the currently selected project."""
        if not self.lb.isEnabled() or not self.current_project_path:
            logging.warning("Launch attempt without a valid project selected.")
            QMessageBox.warning(self, "Launch Error", "Please select a valid project from the list.")
            return

        # Get Godot path from DataManager
        godot_path = self.data_manager.get_godot_path()
        if not godot_path or not validate_godot_path(godot_path):
            logging.error("Cannot launch project: Default Godot path is missing or invalid.")
            QMessageBox.critical(self, "Launch Error", "The default Godot executable path is missing or invalid.\nPlease set it in the Settings tab.")
            return

        # Launch the editor
        launch_project_editor(self.current_project_path, godot_path)

    def run_selected_project(self):
        """Runs the currently selected project directly."""
        if not self.rb.isEnabled() or not self.current_project_path:
            logging.warning("Run attempt without a valid project selected.")
            QMessageBox.warning(self, "Run Error", "Please select a valid project from the list.")
            return

        # Get Godot path from DataManager
        godot_path = self.data_manager.get_godot_path()
        if not godot_path or not validate_godot_path(godot_path):
            logging.error("Cannot run project: Default Godot path is missing or invalid.")
            QMessageBox.critical(self, "Run Error", "The default Godot executable path is missing or invalid.\nPlease set it in the Settings tab.")
            return

        # Run the project
        launch_project_run(self.current_project_path, godot_path)

    def remove_selected_project(self):
        """Removes the selected project from the list (does not delete files)."""
        current_item = self.plw.currentItem()
        if not current_item or current_item.flags() == Qt.ItemFlag.NoItemFlags:
            logging.warning("Remove attempt without a project selected.")
            QMessageBox.warning(self, "Remove Error", "Please select a project to remove.")
            return

        project_name = current_item.text()
        path_str = current_item.data(Qt.ItemDataRole.UserRole)
        logging.info(f"Requesting removal of project '{project_name}' ({path_str})")

        reply = QMessageBox.question(
            self,
            "Remove Project?",
            f"Remove '{project_name}' from the list?\n\n(This will NOT delete the project files from your disk.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No, # Default to No
        )

        if reply == QMessageBox.StandardButton.Yes:
            logging.info("Removal confirmed.")
            # Use DataManager to remove the project
            if self.data_manager.remove_project(project_name):
                logging.info(f"Project '{project_name}' removed successfully.")
                self.refresh_project_list_display() # Update the list UI
            else:
                # Should not happen if item was selected, but handle defensively
                logging.error(f"Removal failed: Project name '{project_name}' not found in DataManager.")
                QMessageBox.warning(self, "Remove Error", f"Could not find project '{project_name}' in the data to remove it.")
        else:
            logging.info("Removal cancelled by user.")

    def open_selected_project_folder(self):
        """Opens the folder containing the selected project in the system's file explorer."""
        if not self.current_project_path:
            logging.warning("Attempt to open folder without a project selected.")
            QMessageBox.warning(self, "Error", "Please select a project first.")
            return

        logging.info(f"Attempting to open project folder: {self.current_project_path}")
        try:
            # Use QDesktopServices for cross-platform compatibility
            url = QUrl.fromLocalFile(str(self.current_project_path))
            success = QDesktopServices.openUrl(url)
            if not success:
                logging.error("QDesktopServices.openUrl failed to open the folder.")
                # Provide a more specific error if possible, otherwise generic
                raise OSError("System could not open the specified folder path.")
            logging.info("Open folder command sent successfully.")
        except Exception as e:
            logging.exception("Failed to open project folder.")
            QMessageBox.critical(self, "Error Opening Folder", f"Could not open the project folder:\n{e}")

    def start_selected_extensions_installation(self):
        """Starts the installation process for extensions marked for auto-install."""
        if not self.isg.isEnabled() or not self.current_project_path:
            logging.warning("Attempt to install selected extensions without a valid project.")
            QMessageBox.warning(self, "Error", "Please select a valid project first.")
            return

        # Get extension IDs from DataManager (using the auto-install list for this button)
        # TODO: This seems wrong. This button should likely install extensions selected
        #       in the Extensions tab, not the auto-install list. This needs clarification
        #       or renaming/repurposing of the button/logic.
        #       Assuming for now it *should* use the auto-install list based on current code.
        extension_ids = self.data_manager.get_auto_install_extensions()

        if not extension_ids:
            logging.info("No extensions marked for auto-install (or selected).")
            QMessageBox.information(self, "No Extensions", "There are no extensions currently marked for installation.")
            return

        # Prevent starting if another installation is already running
        if self.multi_install_cancel_func is not None:
            logging.warning("Attempted to start multi-install while another is running.")
            QMessageBox.warning(self, "Busy", "Another extension installation process is already running.")
            return
        if self.auto_installer_cancel_func is not None:
            logging.warning("Attempted to start multi-install during project creation.")
            QMessageBox.warning(self, "Busy", "Project creation/auto-install is currently in progress.")
            return

        project_name = self.pnl.text() # Get current project name from label
        logging.info(f"Requesting installation of {len(extension_ids)} extensions into project '{project_name}'")

        reply = QMessageBox.question(
            self,
            "Confirm Installation",
            f"Install {len(extension_ids)} selected extensions into '{project_name}'?\n\n"
            f"(Existing addons with the same name might be overwritten)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.No:
            logging.info("Extension installation cancelled by user.")
            return

        # --- Setup UI for Installation ---
        self.set_controls_enabled(False) # Disable main controls
        self.isb.setEnabled(False) # Disable the install button itself
        self.misl.setVisible(True)
        self.misl.setText("Starting installation...")
        self.mipb.setVisible(True)
        self.micb.setVisible(True)
        self.micb.setEnabled(True)
        QApplication.processEvents() # Update UI

        # --- Define Finished Callback ---
        def finished_callback(success: bool, message: str):
            title = "Installation Completed" if success else "Installation Error"
            logging.info(f"Multi-extension installation finished callback: Success={success}, Msg={message}")
            if success:
                QMessageBox.information(self, title, message)
            else:
                QMessageBox.warning(self, title, message)
            self._reset_multi_install_ui() # Reset UI elements

        # --- Start Installation Logic ---
        # Pass DataManager to install_extensions_logic
        self.multi_install_cancel_func = install_extensions_logic(
            extension_ids,
            self.current_project_path,
            self.data_manager,
            self.misl, # Status label
            self.mipb, # Progress bar
            self.micb, # Cancel button
            finished_callback, # Finished callback
        )

        # Handle case where install_extensions_logic returns None immediately (no valid IDs)
        if not self.multi_install_cancel_func:
            logging.info("install_extensions_logic returned None (no valid extensions?).")
            finished_callback(True, "No valid extensions to install.")

    def start_single_extension_installation(self, asset_id: int):
        """
        Starts the installation process for a single extension identified by asset_id.
        
        Args:
            asset_id: The ID of the extension to install
        """
        if not self.current_project_path:
            logging.warning(f"Attempt to install extension {asset_id} without a valid project.")
            QMessageBox.warning(self, "Error", "Please select a valid project first.")
            return

        # Prevent starting if another installation is already running
        if self.multi_install_cancel_func is not None:
            logging.warning("Attempted to start single extension install while another is running.")
            QMessageBox.warning(self, "Busy", "Another extension installation process is already running.")
            return
        if self.auto_installer_cancel_func is not None:
            logging.warning("Attempted to start single extension install during project creation.")
            QMessageBox.warning(self, "Busy", "Project creation/auto-install is currently in progress.")
            return

        # Get the project name from the UI
        project_name = self.pnl.text()
        
        # Fetch extension details to get the name
        try:
            from api_clients import fetch_asset_details_sync
            extension_details = fetch_asset_details_sync(asset_id)
            extension_name = extension_details.get('title', f"Extension #{asset_id}")
        except Exception as e:
            logging.error(f"Failed to fetch details for extension {asset_id}: {e}")
            extension_name = f"Extension #{asset_id}"
        
        logging.info(f"Requesting installation of extension '{extension_name}' (ID: {asset_id}) into project '{project_name}'")

        # Ask for confirmation
        reply = QMessageBox.question(
            self,
            "Confirm Installation",
            f"Install extension '{extension_name}' into '{project_name}'?\n\n"
            f"(Existing addons with the same name might be overwritten)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.No:
            logging.info("Extension installation cancelled by user.")
            return

        # --- Setup UI for Installation ---
        self.set_controls_enabled(False) # Disable main controls
        self.isb.setEnabled(False) # Disable the install button itself
        self.misl.setVisible(True)
        self.misl.setText("Starting installation...")
        self.mipb.setVisible(True)
        self.micb.setVisible(True)
        self.micb.setEnabled(True)
        QApplication.processEvents() # Update UI

        # --- Define Finished Callback ---
        def finished_callback(success: bool, message: str):
            title = "Installation Completed" if success else "Installation Error"
            logging.info(f"Single extension installation finished callback: Success={success}, Msg={message}")
            if success:
                QMessageBox.information(self, title, message)
            else:
                QMessageBox.warning(self, title, message)
            self._reset_multi_install_ui() # Reset UI elements

        # --- Start Installation Logic ---
        # Pass DataManager to install_extensions_logic with a single extension ID
        self.multi_install_cancel_func = install_extensions_logic(
            [asset_id],  # Pass a list with the single asset ID
            self.current_project_path,
            self.data_manager,
            self.misl, # Status label
            self.mipb, # Progress bar
            self.micb, # Cancel button
            finished_callback, # Finished callback
        )

        # Handle case where install_extensions_logic returns None immediately (no valid ID)
        if not self.multi_install_cancel_func:
            logging.info(f"install_extensions_logic returned None for project '{project_name}'")
            finished_callback(False, f"Could not install extension: invalid ID ({asset_id}).")
            
    def start_multi_project_extension_installation(self, asset_id: int, projects: List[Tuple[str, Path]]):
        """
        Starts the process of installing an extension across multiple projects.
        
        Args:
            asset_id: ID of the extension to install
            projects: List of tuples (project_name, path) of projects where to install the extension
        """
        if not projects:
            logging.warning(f"Attempt to install extension {asset_id} without any projects.")
            QMessageBox.warning(self, "Error", "No project selected for installation.")
            return
            
        # Prevent starting if another installation is already running
        if self.multi_install_cancel_func is not None:
            logging.warning("Attempted to start multi-project extension install while another is running.")
            QMessageBox.warning(self, "Busy", "Another installation process is already running.")
            return
        if self.auto_installer_cancel_func is not None:
            logging.warning("Attempted to start multi-project extension install during project creation.")
            QMessageBox.warning(self, "Busy", "Project creation/auto-installation is currently in progress.")
            return
            
        # Fetch extension details to get the name
        try:
            from api_clients import fetch_asset_details_sync
            extension_details = fetch_asset_details_sync(asset_id)
            extension_name = extension_details.get('title', f"Extension #{asset_id}")
        except Exception as e:
            logging.error(f"Failed to fetch details for extension {asset_id}: {e}")
            extension_name = f"Extension #{asset_id}"
            
        project_names = [name for name, _ in projects]
        projects_str = ", ".join(project_names)
        
        logging.info(f"Requesting installation of extension '{extension_name}' (ID: {asset_id}) into {len(projects)} projects: {projects_str}")
        
        # --- Setup UI for Installation ---
        self.set_controls_enabled(False)  # Disable main controls
        self.isb.setEnabled(False)  # Disable the install button itself
        self.misl.setVisible(True)
        self.misl.setText(f"Preparing installation of '{extension_name}' in {len(projects)} projects...")
        self.mipb.setVisible(True)
        self.mipb.setValue(0)
        self.micb.setVisible(True)
        self.micb.setEnabled(True)
        QApplication.processEvents()  # Update UI
        
        # Variables to track installation status
        remaining_projects = projects.copy()
        completed_projects = []
        failed_projects = []
        current_project_idx = 0
        total_projects = len(projects)
        
        # --- Function to show final results ---
        def show_final_results():
            # Reset UI before showing the message
            self._reset_multi_install_ui()
            
            # Prepare the summary message
            if not failed_projects:
                # All projects completed successfully
                title = "Installation Completed"
                if len(completed_projects) == 1:
                    message = f"Extension '{extension_name}' successfully installed in project '{completed_projects[0][0]}'."
                else:
                    message = f"Extension '{extension_name}' successfully installed in {len(completed_projects)} projects."
                QMessageBox.information(self, title, message)
            else:
                # There were errors in some projects
                title = "Installation Completed with Errors"
                message = f"Extension '{extension_name}' successfully installed in {len(completed_projects)} out of {total_projects} projects.\n\n"
                message += "Projects with errors:\n"
                for project_name, error_msg in failed_projects:
                    message += f"- {project_name}: {error_msg}\n"
                QMessageBox.warning(self, title, message)
        
        # --- Project completion callback ---
        def project_finished_callback(success: bool, message: str):
            nonlocal current_project_idx, remaining_projects
            
            project_name, project_path = remaining_projects.pop(0)
            
            if success:
                logging.info(f"Extension installation successful in project '{project_name}'")
                completed_projects.append((project_name, project_path))
            else:
                logging.error(f"Extension installation failed in project '{project_name}': {message}")
                failed_projects.append((project_name, message))
                
            # If there are more projects to process, continue with the next one
            if remaining_projects:
                current_project_idx += 1
                self.mipb.setValue(int((current_project_idx / total_projects) * 100))
                QApplication.processEvents()
                
                # Start installation for the next project
                next_project = remaining_projects[0]
                process_next_project(next_project[1])
            else:
                # All projects have been processed, show summary
                show_final_results()
        
        # --- Wrapper class to adapt widgets to callback functions ---
        class StatusLabelAdapter(QLabel):
            def __init__(self, parent, project_idx, project_name, total, callback_label):
                super().__init__(parent)
                self.project_idx = project_idx
                self.project_name = project_name
                self.total = total
                self.callback_label = callback_label
                
            def setText(self, text):
                # Update the main status label with current project indication
                prefix = f"Project {self.project_idx+1}/{self.total} '{self.project_name}': "
                self.callback_label.setText(prefix + text)
                QApplication.processEvents()
        
        class ProgressBarAdapter(QProgressBar):
            def __init__(self, parent, project_idx, total, callback_progress):
                super().__init__(parent)
                self.project_idx = project_idx
                self.total = total
                self.callback_progress = callback_progress
                
            def setValue(self, value):
                if value >= 0:
                    # Calculate overall progress
                    project_portion = 100.0 / self.total
                    overall_percent = (self.project_idx * project_portion) + (value * project_portion / 100.0)
                    self.callback_progress.setValue(int(overall_percent))
                    self.callback_progress.setTextVisible(True)
                    self.callback_progress.setFormat(f"Project {self.project_idx+1}/{self.total}: {value}%")
                    QApplication.processEvents()
        
        # --- Function to start installation in the next project ---
        def process_next_project(project_path: Path):
            # Update UI for the new project
            project_name = projects[current_project_idx][0]
            self.misl.setText(f"Installing in '{project_name}' ({current_project_idx+1}/{total_projects})...")
            self.mipb.setValue(int((current_project_idx / total_projects) * 100))
            QApplication.processEvents()
            
            # Create widget adapters
            status_adapter = StatusLabelAdapter(self, current_project_idx, project_name, total_projects, self.misl)
            progress_adapter = ProgressBarAdapter(self, current_project_idx, total_projects, self.mipb)
            
            # Start installation for this project
            self.multi_install_cancel_func = install_extensions_logic(
                [asset_id],  # Pass a list with the single asset ID
                project_path,
                self.data_manager,
                status_adapter,  # Adapted widget that updates the main label
                progress_adapter,  # Adapted widget that updates the main progress bar
                self.micb,  # Cancel button
                project_finished_callback,  # Finished callback for this project
            )
            
            # Handle case where install_extensions_logic returns None
            if not self.multi_install_cancel_func:
                logging.info(f"install_extensions_logic returned None for project '{project_name}'")
                project_finished_callback(False, f"Unable to install extension: Invalid ID ({asset_id}).")
        
        # --- Start installation for the first project ---
        if remaining_projects:
            # Initialize UI for the entire operation
            self.misl.setText("Preparing installation...")
            self.mipb.setValue(0)
            self.mipb.setFormat("")
            QApplication.processEvents()
            
            # Start with the first project
            process_next_project(remaining_projects[0][1])
        else:
            # No projects to process
            self.misl.setText("No projects to process.")
            self.micb.setEnabled(False)
            self.remove_multi_install_dialog(success=False, message="No projects to process.")
    
    def remove_multi_install_dialog(self, success: bool = True, message: str = ""):
        """Removes the multi-installation dialog and restores normal UI."""
        # Remove multi-install components
        if hasattr(self, 'misl'):
            self.misl.deleteLater()
            delattr(self, 'misl')
        
        if hasattr(self, 'mipb'):
            self.mipb.deleteLater()
            delattr(self, 'mipb')
        
        if hasattr(self, 'micb'):
            self.micb.deleteLater()
            delattr(self, 'micb')
        
        if hasattr(self, 'miw'):
            self.miw.deleteLater()
            delattr(self, 'miw')
        
        # Reset the asset list selection
        if success:
            self.assets_list.clearSelection()
            
        # Reset the cancel function
        if hasattr(self, 'multi_install_cancel_func'):
            self.multi_install_cancel_func = None
            
        # Reenable all UI elements
        self.setEnabled(True)
        
        # Show message if provided
        if message:
            if success:
                QMessageBox.information(self, "Installation Completed", message)
            else:
                QMessageBox.warning(self, "Installation Failed", message)

    def cancel_selected_extensions_installation(self):
        """Cancels the current installation of extensions if running."""
        try:
            if self.installer_thread and self.installer_thread.isRunning():
                logging.info("Cancelling extension installation thread...")
                self.installer_thread.terminate()
                self._reset_multi_install_ui()
                self.status_message.emit("Installation cancelled.", 3000)
            else:
                logging.warning("No selected extensions installation process is currently running to be cancelled.")
        except Exception as e:
            logging.exception(f"Error cancelling extension installation: {e}")
            self._reset_multi_install_ui()

    def _reset_multi_install_ui(self):
        """Restores the UI elements used to display multi-extension installation progress."""
        logging.debug("Restoring interface elements for multi-installation.")
        self.misl.setVisible(False)
        self.misl.clear()
        self.mipb.setVisible(False)
        self.mipb.setValue(0)
        self.micb.setVisible(False)
        self.micb.setEnabled(False)
        self.multi_install_cancel_func = None # Clear the cancel function reference
        self.set_controls_enabled(True) # Re-enable main controls
        # Re-enable the install button based on current state (managed by set_controls_enabled -> on_project_selection_changed)

    def add_and_select_project(self, name: str, path_str: str):
        """Aggiunge un progetto utilizzando DataManager e lo seleziona nella lista."""
        logging.info(f"ProjectsTab: Aggiunta del progetto '{name}' in '{path_str}' e selezione.")
        # Usa DataManager per aggiungere il progetto
        self.data_manager.add_project(name, path_str)
        self.refresh_project_list_display() # Aggiorna la lista
        # Trova e seleziona l'elemento appena aggiunto
        items = self.plw.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self.plw.setCurrentItem(items[0])
            self.plw.scrollToItem(items[0]) # Assicura che sia visibile
