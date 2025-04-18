# -*- coding: utf-8 -*-
# gui/new_project_dialog.py

import logging
import os
import re
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpacerItem,
    QSizePolicy,
    QVBoxLayout,
    QAbstractButton,
    QWidget,
)

# Import DataManager
from data_manager import DataManager # Import the class


class NewProjectDialog(QDialog):
    """Custom dialog for creating a new Godot project."""

    def __init__(self, data_manager: DataManager, parent: Optional[QWidget] = None):
        """
        Initializes the NewProjectDialog.

        Args:
            data_manager: The central DataManager instance.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.data_manager = data_manager # Store DataManager instance
        self.setWindowTitle("Create New Godot Project")
        self.setMinimumWidth(550)

        # Attributes to store selected values
        self.project_name: str = ""
        # Use DataManager to get the initial parent path, fallback to home
        self.parent_path: str = self.data_manager.get_default_projects_folder() or str(Path.home())
        self.final_project_path: Optional[Path] = None # The calculated full path for the new project
        self.selected_renderer: str = "forward_plus" # Default renderer
        self.include_extensions: bool = bool(self.data_manager.get_auto_install_extensions()) # Default based on DataManager
        self.edit_now: bool = True # Default to True
        # self.version_control: str = "None" # Default VCS (currently commented out)

        # Setup UI
        self._init_ui()
        self._connect_signals()

        # Update and validate the initial path display
        self._update_final_path()

    def _init_ui(self):
        """Creates and arranges the UI widgets."""
        main_layout = QVBoxLayout(self)

        # --- Project Name and Path ---
        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        self.name_edit = QLineEdit("New Godot Project") # Default project name
        self.name_edit.setPlaceholderText("Name of your project")
        form_layout.addRow("Project Name:", self.name_edit)

        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit(self.parent_path)
        self.path_edit.setPlaceholderText("Select the parent folder")
        self.path_edit.setReadOnly(True) # Only shows the selected parent path
        self.browse_path_btn = QPushButton("Browse...")
        self.browse_path_btn.setToolTip("Select the folder that will contain the new project folder.")
        path_layout.addWidget(self.path_edit, 1)
        path_layout.addWidget(self.browse_path_btn)
        form_layout.addRow("Parent Folder:", path_layout)

        # Label to display the final calculated project path
        self.final_path_label = QLabel("...")
        self.final_path_label.setWordWrap(True)
        self.final_path_label.setStyleSheet("font-size: 9pt; color: gray;")
        form_layout.addRow("Final Project Path:", self.final_path_label)

        main_layout.addLayout(form_layout)

        # Status label for path validation feedback
        main_layout.addSpacing(5)
        self.path_status_label = QLabel("...")
        self.path_status_label.setStyleSheet("font-size: 9pt; color: gray;")
        main_layout.addWidget(self.path_status_label)

        main_layout.addSpacing(15)

        # --- Renderer Selection ---
        renderer_group = QGroupBox("Renderer")
        renderer_layout = QVBoxLayout(renderer_group)
        self.renderer_button_group = QButtonGroup(self) # Group for radio buttons
        self.rb_forward = QRadioButton("Forward+ (Desktop, High-end Graphics)")
        self.rb_mobile = QRadioButton("Mobile (Mobile/Web, Balanced)")
        self.rb_compat = QRadioButton("Compatibility (OpenGL, Max Compatibility)")

        # Associate string values with buttons for easier identification
        self.renderer_button_group.addButton(self.rb_forward)
        self.rb_forward.setProperty("renderer_name", "forward_plus")
        self.renderer_button_group.addButton(self.rb_mobile)
        self.rb_mobile.setProperty("renderer_name", "mobile")
        self.renderer_button_group.addButton(self.rb_compat)
        self.rb_compat.setProperty("renderer_name", "gl_compatibility")

        renderer_layout.addWidget(self.rb_forward)
        renderer_layout.addWidget(self.rb_mobile)
        renderer_layout.addWidget(self.rb_compat)

        # Set initial check based on the default
        if self.selected_renderer == "mobile":
            self.rb_mobile.setChecked(True)
        elif self.selected_renderer == "gl_compatibility":
            self.rb_compat.setChecked(True)
        else: # Default to Forward+
            self.rb_forward.setChecked(True)
            self.selected_renderer = "forward_plus" # Ensure consistency

        main_layout.addWidget(renderer_group)
        main_layout.addSpacing(10)

        # --- Options ---
        options_layout = QVBoxLayout() # Changed to QVBoxLayout for stacking checkboxes
        # Include Default Extensions Checkbox
        num_extensions = len(self.data_manager.get_auto_install_extensions())
        self.include_extensions_checkbox = QCheckBox(f"Include {num_extensions} Default Extension(s)")
        self.include_extensions_checkbox.setChecked(self.include_extensions)
        self.include_extensions_checkbox.setToolTip(f"Automatically install the {num_extensions} extension(s) marked for auto-install.")
        self.include_extensions_checkbox.setEnabled(num_extensions > 0) # Only enable if there are extensions
        options_layout.addWidget(self.include_extensions_checkbox)

        # Edit Project Now Checkbox
        self.edit_now_checkbox = QCheckBox("Edit Project After Creation")
        self.edit_now_checkbox.setChecked(self.edit_now)
        self.edit_now_checkbox.setToolTip("Automatically open the Godot editor for the new project after it is created.")
        options_layout.addWidget(self.edit_now_checkbox)

        main_layout.addLayout(options_layout)
        main_layout.addSpacing(15) # Add spacing after options

        # --- Version Control (Optional - Currently Commented Out) ---
        # vcs_layout = QHBoxLayout()
        # vcs_layout.addWidget(QLabel("Version Control Metadata:"))
        # self.vcs_combo = QComboBox()
        # self.vcs_combo.addItems(["None", "Git"])
        # vcs_layout.addWidget(self.vcs_combo)
        # vcs_layout.addStretch()
        # main_layout.addLayout(vcs_layout)

        main_layout.addStretch() # Push buttons to the bottom

        # --- OK/Cancel Buttons ---
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.create_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.create_button.setText("Create Folder & Open") # Set OK button text
        self.create_button.setEnabled(False) # Disabled initially until valid
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def _connect_signals(self):
        """Connects UI element signals to appropriate slots."""
        self.name_edit.textChanged.connect(self._update_final_path)
        self.browse_path_btn.clicked.connect(self._browse_parent_path)
        # Connect renderer selection change
        self.renderer_button_group.buttonClicked.connect(self._renderer_changed)
        # Connect VCS change if uncommented
        # self.vcs_combo.currentTextChanged.connect(self._vcs_changed)
        # Connect checkbox changes
        self.include_extensions_checkbox.stateChanged.connect(self._include_extensions_changed)
        self.edit_now_checkbox.stateChanged.connect(self._edit_now_changed)

    @pyqtSlot(QAbstractButton)
    def _renderer_changed(self, button: QAbstractButton):
        """Updates the selected renderer when a radio button is clicked."""
        if button:
            renderer_name = button.property("renderer_name")
            if renderer_name:
                self.selected_renderer = renderer_name
                logging.debug(f"Selected renderer: {self.selected_renderer}")
            else:
                # This should not happen if properties are set correctly
                logging.warning("Renderer radio button clicked without 'renderer_name' property.")

    def _browse_parent_path(self):
        """Opens a dialog to select the parent folder for the new project."""
        current_parent = self.parent_path
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Parent Folder", # Dialog title
            current_parent, # Starting directory
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if selected_dir and selected_dir != self.parent_path:
            self.parent_path = selected_dir
            self.path_edit.setText(selected_dir) # Update read-only line edit
            self._update_final_path() # Update final path display and validation

    def _update_final_path(self):
        """Updates the final project path based on name and parent, then validates."""
        self.project_name = self.name_edit.text().strip()
        parent = Path(self.parent_path)

        if not self.project_name:
            self.final_project_path = None
            self.final_path_label.setText("<font color='orange'>Please enter a project name.</font>")
            self._validate_path() # Still validate to disable OK button
            return

        # --- Generate a safe folder name from the project name ---
        folder_name_base = self.project_name.lower()
        # Replace whitespace with underscores
        folder_name_base = re.sub(r"\s+", "_", folder_name_base)
        # Remove characters not suitable for folder names (allow letters, numbers, underscore, hyphen)
        folder_name_base = re.sub(r"[^\w\-]+", "", folder_name_base)
        # Remove leading/trailing underscores or hyphens
        folder_name = folder_name_base.strip("_-")
        # Fallback if the name becomes empty after sanitization
        if not folder_name:
            folder_name = "new_godot_project"
        logging.debug(f"Project name: '{self.project_name}' -> Generated folder name: '{folder_name}'")

        # Construct the final path using the generated folder name
        try:
            self.final_project_path = parent / folder_name
            # Display both the final path and the original project name
            self.final_path_label.setText(f"{self.final_project_path}\n(Project Name: '{self.project_name}')")
            self.final_path_label.setStyleSheet("font-size: 9pt; color: gray;")
        except Exception as e: # Catch potential errors creating the Path object
            logging.warning(f"Error constructing final path: {e}")
            self.final_project_path = None
            self.final_path_label.setText("<font color='red'>Invalid project name or parent folder.</font>")
            self.final_path_label.setStyleSheet("font-size: 9pt; color: red;")

        self._validate_path() # Validate the generated path

    def _validate_path(self) -> bool:
        """Validates the project name and the final calculated path."""
        is_valid = False
        status_text = ""
        text_color = "red" # Default to error color
        folder_name = ""

        # 1. Validate Project Name (User Input)
        if not self.project_name:
            status_text = "Project name cannot be empty."
        # Check for invalid characters in the *project name* itself (might be used elsewhere)
        elif any(c in '<>:"/\\|?*' for c in self.project_name):
            status_text = "Project name contains invalid characters."
        # Check if project name is already registered (using DataManager)
        elif self.project_name in self.data_manager.get_projects():
            status_text = f"A project named '{self.project_name}' is already registered."
            text_color = "orange" # Warning color for existing name

        # 2. Validate Final Path (Generated Folder Name + Parent Path)
        elif self.final_project_path is None:
            # This occurs if parent_path was invalid during _update_final_path
            status_text = "Invalid parent folder selected."
        elif self.final_project_path.exists():
            # The calculated folder name already exists in the parent directory
            folder_name = self.final_project_path.name
            status_text = f"Folder '{folder_name}' already exists in '{self.parent_path}'."
            text_color = "orange" # Warning color for existing folder
        elif not self.final_project_path.parent.is_dir():
             # Parent directory check (should be redundant if browse dialog worked, but safe)
             status_text = "Selected parent folder is not a valid directory."
        else:
            # All checks passed
            folder_name = self.final_project_path.name
            status_text = f"Will create folder '{folder_name}'."
            text_color = "green"
            is_valid = True

        # Update status label and OK button state
        self.path_status_label.setText(f"<font color='{text_color}'>{status_text}</font>")
        self.create_button.setEnabled(is_valid)
        return is_valid

    # Optional slots for handling VCS changes (if uncommented in UI)
    # def _vcs_changed(self, text):
    #     self.version_control = text
    #     logging.debug(f"Selected version control: {self.version_control}")

    def get_project_details(self) -> Optional[dict]:
        """Returns the selected project details if valid, otherwise None."""
        if self._validate_path():
            return {
                "name": self.project_name,
                "path": self.final_project_path,
                "renderer": self.selected_renderer,
                "include_extensions": self.include_extensions,
                "edit_now": self.edit_now,
                # "vcs": self.version_control # Include if VCS is uncommented
            }
        return None

    # Add slots for checkbox changes
    @pyqtSlot(int)
    def _include_extensions_changed(self, state: int):
        self.include_extensions = state == Qt.CheckState.Checked.value
        logging.debug(f"Include extensions set to: {self.include_extensions}")

    @pyqtSlot(int)
    def _edit_now_changed(self, state: int):
        self.edit_now = state == Qt.CheckState.Checked.value
        logging.debug(f"Edit now set to: {self.edit_now}")

    def accept(self):
        """Overrides accept to perform final validation before closing."""
        if self._validate_path(): # Perform final validation
            logging.info(f"Create project dialog accepted. Name: '{self.project_name}', Path: '{self.final_project_path}', Renderer: '{self.selected_renderer}'")
            super().accept() # Close dialog with Accepted code
        else:
            logging.warning("Attempted to accept invalid new project dialog.")
            # Status label should already indicate the error
            QMessageBox.warning(self, "Validation Error", "Please correct the indicated errors before creating the project.")

    def reject(self):
        """Handles dialog rejection (Cancel button or closing)."""
        logging.info("Create new project dialog cancelled.")
        super().reject() # Close dialog with Rejected code
