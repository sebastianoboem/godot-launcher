# -*- coding: utf-8 -*-
# gui/project_selection_dialog.py

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QDialogButtonBox,
    QAbstractItemView,
    QMessageBox,
)

from data_manager import DataManager
from gui.styles import (  # Import of new styles
    BUTTON_STYLE,
    PRIMARY_BUTTON_STYLE,
    DIALOG_STYLE,
    INPUT_STYLE,
    LIST_WIDGET_STYLE,
    CHECKBOX_STYLE,
    COLORS
)


class ProjectSelectionDialog(QDialog):
    """
    Dialog that allows the user to select one or more projects for extension installation.
    Shows a list of projects with checkboxes to allow multiple selections.
    """

    def __init__(self, data_manager: DataManager, asset_id: int, asset_name: str, parent=None):
        """
        Initializes the project selection dialog.

        Args:
            data_manager: DataManager instance to access project data
            asset_id: ID of the extension to install
            asset_name: Name of the extension to install
            parent: Parent widget
        """
        super().__init__(parent)
        self.data_manager = data_manager
        self.asset_id = asset_id
        self.asset_name = asset_name
        self.selected_projects: List[Tuple[str, Path]] = []  # [(project_name, path), ...]
        self.setWindowTitle("Select Projects for Installation")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.setStyleSheet(DIALOG_STYLE)  # Apply dialog style
        self.init_ui()
        self.populate_projects_list()

    def init_ui(self):
        """Initializes the dialog user interface."""
        layout = QVBoxLayout(self)

        # Title and information label
        title_label = QLabel(f"<h3>Install '{self.asset_name}'</h3>")
        title_label.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(title_label)
        
        info_label = QLabel(
            "Select the projects where you want to install this extension. "
            "Existing addons with the same name might be overwritten."
        )
        info_label.setStyleSheet(f"color: {COLORS['text_secondary']}; margin-bottom: 10px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Project list with checkboxes
        self.projects_list = QListWidget()
        self.projects_list.setStyleSheet(LIST_WIDGET_STYLE)
        self.projects_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.projects_list, 1)  # Takes available space

        # Selection instructions label
        select_label = QLabel(
            "Check the boxes next to the projects where you want to install the extension."
        )
        select_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-style: italic;")
        select_label.setWordWrap(True)
        layout.addWidget(select_label)

        # Quick selection buttons
        selection_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setStyleSheet(BUTTON_STYLE)
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.setStyleSheet(BUTTON_STYLE)
        selection_layout.addWidget(self.select_all_btn)
        selection_layout.addWidget(self.deselect_all_btn)
        selection_layout.addStretch()
        layout.addLayout(selection_layout)

        # Confirm/cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        
        ok_button.setText("Install")
        ok_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        
        cancel_button.setText("Cancel")
        cancel_button.setStyleSheet(BUTTON_STYLE)
        
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Connect signals
        self.select_all_btn.clicked.connect(self.select_all_projects)
        self.deselect_all_btn.clicked.connect(self.deselect_all_projects)

    def populate_projects_list(self):
        """Populates the project list from the DataManager."""
        projects = self.data_manager.get_projects()
        
        if not projects:
            # No projects available
            item = QListWidgetItem("No projects available.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)  # Not selectable
            item.setForeground(Qt.GlobalColor.gray)
            self.projects_list.addItem(item)
            self.select_all_btn.setEnabled(False)
            self.deselect_all_btn.setEnabled(False)
            return

        # Sort projects by name
        sorted_projects = sorted(projects.items())
        
        for project_name, path_str in sorted_projects:
            item = QListWidgetItem()
            self.projects_list.addItem(item)
            
            # Create checkbox with project name
            checkbox = QCheckBox(project_name)
            checkbox.setStyleSheet(CHECKBOX_STYLE)
            
            # Verify that the path is valid
            try:
                proj_path = Path(path_str)
                is_valid = proj_path.is_dir() and (proj_path / "project.godot").is_file()
                
                if not is_valid:
                    checkbox.setEnabled(False)
                    checkbox.setText(f"{project_name} (invalid path)")
            except Exception as e:
                logging.error(f"Error validating project path '{project_name}': {e}")
                checkbox.setEnabled(False)
                checkbox.setText(f"{project_name} (invalid path)")
            
            # Store the path as item data
            item.setData(Qt.ItemDataRole.UserRole, path_str)
            
            # Set custom widget for the item
            self.projects_list.setItemWidget(item, checkbox)

    def select_all_projects(self):
        """Selects all valid projects in the list."""
        for i in range(self.projects_list.count()):
            item = self.projects_list.item(i)
            widget = self.projects_list.itemWidget(item)
            if isinstance(widget, QCheckBox) and widget.isEnabled():
                widget.setChecked(True)

    def deselect_all_projects(self):
        """Deselects all projects in the list."""
        for i in range(self.projects_list.count()):
            item = self.projects_list.item(i)
            widget = self.projects_list.itemWidget(item)
            if isinstance(widget, QCheckBox):
                widget.setChecked(False)

    def accept(self):
        """Handles dialog acceptance, checking that at least one project is selected."""
        self.selected_projects = []
        
        for i in range(self.projects_list.count()):
            item = self.projects_list.item(i)
            widget = self.projects_list.itemWidget(item)
            if isinstance(widget, QCheckBox) and widget.isChecked():
                project_name = widget.text()
                path_str = item.data(Qt.ItemDataRole.UserRole)
                try:
                    self.selected_projects.append((project_name, Path(path_str)))
                except Exception as e:
                    logging.error(f"Error converting path '{path_str}' to Path: {e}")
        
        if not self.selected_projects:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("No Project Selected")
            msg_box.setText("Select at least one project to install the extension.")
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            
            # Apply styles to message box
            msg_box.setStyleSheet(DIALOG_STYLE)
            ok_button = msg_box.button(QMessageBox.StandardButton.Ok)
            ok_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
            
            msg_box.exec()
            return
        
        super().accept()

    def get_selected_projects(self) -> List[Tuple[str, Path]]:
        """
        Returns the list of selected projects.
        
        Returns:
            List of tuples (project_name, path)
        """
        return self.selected_projects 