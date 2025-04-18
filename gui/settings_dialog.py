# -*- coding: utf-8 -*-
# gui/settings_dialog.py

import logging
import os
import platform
import shutil
import sys
import time
import zipfile
import tempfile
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple

from PyQt6.QtCore import QObject, QSize, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QIcon
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
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
)

# Import necessary modules and classes
from api_clients import GitHubReleasesThread
from data_manager import DataManager, DEFAULT_GODOT_VERSIONS_DIR # Import class and constant
from project_handler import validate_godot_path, get_godot_version_string # Import project_handler
from utils import DownloadThread, extract_zip, log_and_show_error # Importa la funzione helper
from gui.styles import (  # Import of new styles
    BUTTON_STYLE, PRIMARY_BUTTON_STYLE, GROUP_BOX_STYLE, INPUT_STYLE,
    LIST_WIDGET_STYLE, CHECKBOX_STYLE, COLORS
)


class SettingsDialog(QDialog):
    """
    Dialog window for configuring launcher settings, including the default Godot executable path,
    the location for downloaded Godot versions, and downloading new Godot versions.
    """
    # Signal emitted when the default Godot path is changed and saved
    godot_path_changed = pyqtSignal()
    # Signal emitted when theme settings are changed
    theme_changed = pyqtSignal(str, bool)  # theme_name, use_accent_color
    # Removed unused godot_versions_path_changed signal

    def __init__(self, data_manager: DataManager, parent: Optional[QWidget] = None):
        """
        Initializes the SettingsDialog.

        Args:
            data_manager: The central DataManager instance.
            parent: The parent widget.
        """
        super().__init__(parent)
        logging.info("Opening SettingsDialog...")
        self.data_manager = data_manager # Store DataManager instance
        self.setWindowTitle("Launcher Settings")
        self.setMinimumWidth(650)

        # Store initial paths for change detection on accept
        self.initial_godot_path: Optional[str] = self.data_manager.get_godot_path()
        # Store initial path string (or None) for change detection on accept
        self.initial_godot_versions_path_str: Optional[str] = self.data_manager.get_godot_versions_path_str()
        logging.debug(f"Initial Godot versions path string from DataManager: {self.initial_godot_versions_path_str}")

        # Thread management
        self.github_thread: Optional[GitHubReleasesThread] = None
        self.godot_download_thread: Optional[DownloadThread] = None
        self.current_godot_download_info: dict = {} # Stores info about the active download
        self.is_downloading_godot: bool = False # Flag to track download state

        # State variables
        self._versions_path_is_valid: bool = False # Tracks validity of the versions path input
        # Path selected in the 'Installed Versions' combo box (can be None for system PATH)
        self.selected_executable_path: Optional[str] = self.initial_godot_path

        logging.debug("Initializing SettingsDialog UI")
        self.init_ui() # Setup UI elements
        # Initial population and validation
        QTimer.singleShot(0, self.validate_versions_path_display) # Validate versions path on startup
        QTimer.singleShot(100, self.fetch_github_releases) # Fetch available versions from GitHub
        logging.info("SettingsDialog initialized.")

    def init_ui(self):
        """Creates and arranges the UI widgets for the settings dialog."""
        main_layout = QVBoxLayout(self)

        # General Settings Section
        # Startup Group
        startup_group = QGroupBox("Startup")
        startup_group.setStyleSheet(GROUP_BOX_STYLE)
        startup_layout = QVBoxLayout(startup_group)
        
        self.check_updates_startup = QCheckBox("Check for Updates on Startup")
        self.check_updates_startup.setStyleSheet(CHECKBOX_STYLE)
        startup_layout.addWidget(self.check_updates_startup)
        
        self.sync_projects_startup = QCheckBox("Synchronize Projects on Startup")
        self.sync_projects_startup.setStyleSheet(CHECKBOX_STYLE)
        self.sync_projects_startup.setChecked(True)
        startup_layout.addWidget(self.sync_projects_startup)
        
        main_layout.addWidget(startup_group)

        # Engine Settings Section
        # Godot Versions Group
        versions_group = QGroupBox("Godot Versions")
        versions_group.setStyleSheet(GROUP_BOX_STYLE)
        versions_layout = QVBoxLayout(versions_group)

        # Default Godot Path
        godot_path_layout = QHBoxLayout()
        godot_path_layout.addWidget(QLabel("Manual Godot Path (system version):"))
        self.godot_path_edit = QLineEdit()
        self.godot_path_edit.setStyleSheet(INPUT_STYLE)
        self.godot_path_edit.setPlaceholderText("Path to Godot executable")
        godot_path_browse = QPushButton("Browse...")
        godot_path_browse.setStyleSheet(BUTTON_STYLE)
        godot_path_browse.clicked.connect(self.browse_godot_path)
        godot_path_validate = QPushButton("Validate")
        godot_path_validate.setStyleSheet(PRIMARY_BUTTON_STYLE)
        godot_path_validate.clicked.connect(self.validate_godot_path)
        godot_path_layout.addWidget(self.godot_path_edit, 1)
        godot_path_layout.addWidget(godot_path_browse)
        godot_path_layout.addWidget(godot_path_validate)
        versions_layout.addLayout(godot_path_layout)
        
        # Godot Version Status
        self.godot_version_label = QLabel("")
        self.godot_version_label.setStyleSheet(f"font-weight: bold; color: {COLORS['text_primary']};")
        versions_layout.addWidget(self.godot_version_label)
        
        # Versions Download Location (unificato con Downloaded Versions Folder)
        versions_download_layout = QHBoxLayout()
        versions_download_layout.addWidget(QLabel("Godot Downloaded Versions Folder:"))
        self.versions_download_edit = QLineEdit()
        self.versions_download_edit.setStyleSheet(INPUT_STYLE)
        self.versions_download_edit.setPlaceholderText("Path for downloaded Godot versions")
        self.versions_download_edit.textChanged.connect(self.validate_versions_path_display)
        versions_download_browse = QPushButton("Browse...")
        versions_download_browse.setStyleSheet(BUTTON_STYLE)
        versions_download_browse.clicked.connect(self.browse_versions_download)
        versions_download_layout.addWidget(self.versions_download_edit, 1)
        versions_download_layout.addWidget(versions_download_browse)
        versions_layout.addLayout(versions_download_layout)
        
        # Download e gestione versioni
        available_versions_layout = QHBoxLayout()
        available_versions_layout.addWidget(QLabel("Fetched Online Versions:"))
        self.versions_combo = QComboBox()
        self.versions_combo.setStyleSheet(INPUT_STYLE)
        self.versions_combo.currentIndexChanged.connect(self.on_github_version_selected)
        
        self.refresh_versions_btn = QPushButton("Fetch")
        self.refresh_versions_btn.setStyleSheet(BUTTON_STYLE)
        self.refresh_versions_btn.clicked.connect(self.fetch_github_releases)
        
        available_versions_layout.addWidget(self.versions_combo, 1)
        available_versions_layout.addWidget(self.refresh_versions_btn)
        versions_layout.addLayout(available_versions_layout)
        
        download_btn_layout = QHBoxLayout()
        self.download_version_btn = QPushButton("Download Selected Version")
        self.download_version_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.download_version_btn.clicked.connect(self.start_godot_download)
        self.download_version_btn.setEnabled(False)  # Disabilitato finché non viene selezionata una versione
        
        self.cancel_download_btn = QPushButton("Cancel Download")
        self.cancel_download_btn.setStyleSheet(BUTTON_STYLE)
        self.cancel_download_btn.clicked.connect(self.cancel_godot_download)
        self.cancel_download_btn.setVisible(False)  # Nascosto finché non inizia un download
        
        download_btn_layout.addWidget(self.download_version_btn)
        download_btn_layout.addWidget(self.cancel_download_btn)
        versions_layout.addLayout(download_btn_layout)
        
        # Progress indicator
        self.download_status_label = QLabel("Download Status: No download in progress")
        versions_layout.addWidget(self.download_status_label)
        
        self.download_progress_bar = QProgressBar()
        self.download_progress_bar.setVisible(False)
        versions_layout.addWidget(self.download_progress_bar)
        
        # Installed versions section
        installed_versions_layout = QHBoxLayout()
        installed_versions_layout.addWidget(QLabel("Installed Versions:"))
        self.installed_versions_combo = QComboBox()
        self.installed_versions_combo.setStyleSheet(INPUT_STYLE)
        self.installed_versions_combo.currentIndexChanged.connect(self.on_installed_version_selected)
        
        self.rescan_versions_btn = QPushButton("Rescan")
        self.rescan_versions_btn.setStyleSheet(BUTTON_STYLE)
        self.rescan_versions_btn.clicked.connect(self._scan_and_populate_installed_versions)

        installed_versions_layout.addWidget(self.installed_versions_combo, 1)
        installed_versions_layout.addWidget(self.rescan_versions_btn)
        versions_layout.addLayout(installed_versions_layout)
        
        main_layout.addWidget(versions_group)
        
        # Advanced Settings Section
        # Cache Group
        cache_group = QGroupBox("Cache Settings")
        cache_group.setStyleSheet(GROUP_BOX_STYLE)
        cache_layout = QVBoxLayout(cache_group)
        
        cache_location_layout = QHBoxLayout()
        cache_location_layout.addWidget(QLabel("Cache Location:"))
        self.cache_location_edit = QLineEdit()
        self.cache_location_edit.setStyleSheet(INPUT_STYLE)
        self.cache_location_edit.setPlaceholderText("Path for application cache")
        cache_location_browse = QPushButton("Browse...")
        cache_location_browse.setStyleSheet(BUTTON_STYLE)
        cache_location_browse.clicked.connect(self.browse_cache_location)
        cache_location_layout.addWidget(self.cache_location_edit, 1)
        cache_location_layout.addWidget(cache_location_browse)
        cache_layout.addLayout(cache_location_layout)
        
        cache_size_layout = QHBoxLayout()
        cache_size_layout.addWidget(QLabel("Maximum Cache Size (MB):"))
        self.cache_size_spin = QSpinBox()
        self.cache_size_spin.setStyleSheet(INPUT_STYLE)
        self.cache_size_spin.setRange(50, 1000)
        self.cache_size_spin.setValue(200)
        cache_size_layout.addWidget(self.cache_size_spin)
        cache_size_layout.addStretch(1)
        cache_layout.addLayout(cache_size_layout)
        
        clear_cache_button = QPushButton("Clear Cache")
        clear_cache_button.setStyleSheet(BUTTON_STYLE)
        clear_cache_button.clicked.connect(self.clear_cache)
        cache_layout.addWidget(clear_cache_button, 0, Qt.AlignmentFlag.AlignRight)
        
        main_layout.addWidget(cache_group)
        
        # Logging Group
        logging_group = QGroupBox("Logging")
        logging_group.setStyleSheet(GROUP_BOX_STYLE)
        logging_layout = QVBoxLayout(logging_group)
        
        log_level_layout = QHBoxLayout()
        log_level_layout.addWidget(QLabel("Log Level:"))
        self.log_level_combo = QComboBox()
        self.log_level_combo.setStyleSheet(INPUT_STYLE)
        self.log_level_combo.addItems(["Debug", "Info", "Warning", "Error", "Critical"])
        self.log_level_combo.setCurrentIndex(1)  # Info by default
        log_level_layout.addWidget(self.log_level_combo)
        log_level_layout.addStretch(1)
        logging_layout.addLayout(log_level_layout)
        
        self.verbose_logging_checkbox = QCheckBox("Enable Verbose Logging")
        self.verbose_logging_checkbox.setStyleSheet(CHECKBOX_STYLE)
        logging_layout.addWidget(self.verbose_logging_checkbox)
        
        # Aggiunto pulsante per pulire il file di log
        log_actions_layout = QHBoxLayout()
        clear_log_button = QPushButton("Clear Log File")
        clear_log_button.setStyleSheet(BUTTON_STYLE)
        clear_log_button.clicked.connect(self.clear_log_file)
        log_actions_layout.addWidget(clear_log_button)
        log_actions_layout.addStretch(1)
        logging_layout.addLayout(log_actions_layout)
        
        main_layout.addWidget(logging_group)
        
        # Add a spacing to the layout
        main_layout.addSpacing(10)
        
        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        # Applicare stile ai pulsanti
        self.ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        cancel_button = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setStyleSheet(BUTTON_STYLE)
        
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)
        
        # Load settings
        self.load_settings()

    def load_settings(self):
        """Loads the currently saved settings into the UI."""
        # Set up general settings
        self.check_updates_startup.setChecked(self.data_manager.get("check_updates_startup", True))
        self.sync_projects_startup.setChecked(self.data_manager.get("sync_projects_startup", True))
        
        # Set up Godot path
        godot_path = self.data_manager.get_godot_path()
        if godot_path:
            self.godot_path_edit.setText(godot_path)
            self.update_godot_version_label(godot_path)
        
        # Set up versions download location
        versions_download_path = self.data_manager.get("versions_download_path", "")
        if versions_download_path:
            self.versions_download_edit.setText(versions_download_path)
        
        # Carica il percorso delle versioni dal DataManager
        godot_versions_path_str = self.data_manager.get_godot_versions_path_str()
        if godot_versions_path_str:
            self.versions_download_edit.setText(godot_versions_path_str)
        
        # Carica impostazioni della cache
        cache_location = self.data_manager.get("cache_location", "cache")
        self.cache_location_edit.setText(cache_location)
        
        max_cache_size = self.data_manager.get("max_cache_size_mb", 500)
        self.cache_size_spin.setValue(max_cache_size)
        
        # Carica impostazioni di logging
        log_level = self.data_manager.get("log_level", "INFO")
        log_level_map = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
        self.log_level_combo.setCurrentIndex(log_level_map.get(log_level, 1))  # Default a INFO
        
        self.verbose_logging_checkbox.setChecked(self.data_manager.get("verbose_logging", False))
        
        # Avvia immediatamente la scansione delle versioni installate
        self._scan_and_populate_installed_versions()

    def setup_connections(self):
        # Connect buttons to their respective actions
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def validate_versions_path_display(self):
        """Checks if the versions path is valid and sets UI accordingly."""
        path_text = self.versions_download_edit.text().strip()

        if not path_text:
            self._versions_path_is_valid = False
            self.versions_download_edit.setStyleSheet(INPUT_STYLE) # Reset to default style
            return

        path_obj = Path(path_text)

        try:
            # Verify the path exists and is a directory
            if path_obj.exists() and path_obj.is_dir():
                self._versions_path_is_valid = True
                self.versions_download_edit.setStyleSheet(f"{INPUT_STYLE} border: 1px solid {COLORS['success']};")
            else:
                self._versions_path_is_valid = False
                self.versions_download_edit.setStyleSheet(f"{INPUT_STYLE} border: 1px solid {COLORS['error']};")
        except Exception:
            self._versions_path_is_valid = False
            self.versions_download_edit.setStyleSheet(f"{INPUT_STYLE} border: 1px solid {COLORS['error']};")

    def browse_godot_path(self):
        """Apre una finestra di dialogo per selezionare l'eseguibile Godot."""
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Select Godot Executable")
        
        # Filtro appropriato per gli eseguibili in base al sistema operativo
        if os.name == "nt":  # Windows
            file_dialog.setNameFilter("Executables (*.exe);;All Files (*.*)")
        else:  # Linux/Mac
            file_dialog.setNameFilter("All Files (*)")
        
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                path = selected_files[0]
                self.godot_path_edit.setText(path)
                self.update_godot_version_label(path)
    
    def validate_godot_path(self):
        """Valida il percorso dell'eseguibile Godot inserito."""
        path = self.godot_path_edit.text().strip()
        if not path:
            self.godot_version_label.setText("No path provided.")
            self.godot_version_label.setStyleSheet(f"color: {COLORS['warning']};")
            return
        
        valid, version = validate_godot_path(path)
        if valid:
            if version:
                self.godot_version_label.setText(f"Valid Godot executable: {version}")
            else:
                self.godot_version_label.setText("Valid Godot executable")
            self.godot_version_label.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
        else:
            self.godot_version_label.setText("Invalid Godot executable.")
            self.godot_version_label.setStyleSheet(f"color: {COLORS['error']}; font-weight: bold;")
    
    def update_godot_version_label(self, path):
        """
        Updates the label showing the Godot executable version.

        Args:
            path: The path to the Godot executable.
        """
        logging.debug(f"Updating Godot version label for path: {path}")
        try:
            if not path:
                self.godot_version_label.setText("<font color='gray'>No Godot path set</font>")
                return
            version_str = get_godot_version_string(path)
            if version_str:
                self.godot_version_label.setText(f"<font color='{COLORS['success']}'>Godot {version_str} detected</font>")
            else:
                self.godot_version_label.setText(f"<font color='{COLORS['error']}'>Invalid Godot executable or unsupported version</font>")
        except Exception as e:
            logging.exception(f"Error updating Godot version label: {e}")
            self.godot_version_label.setText(f"<font color='{COLORS['error']}'>Error detecting Godot version</font>")

    def browse_versions_download(self):
        """Shows a dialog to select the folder where Godot versions will be downloaded."""
        logging.debug("Browse versions download folder dialog")
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder for Downloaded Godot Versions")
        if folder_path:
            self.versions_download_edit.setText(folder_path)
            self.validate_versions_path_display()
    
    def browse_cache_location(self):
        """Apre una finestra di dialogo per selezionare la posizione della cache."""
        folder_dialog = QFileDialog(self)
        folder_dialog.setWindowTitle("Select Cache Location")
        folder_dialog.setFileMode(QFileDialog.FileMode.Directory)
        
        if folder_dialog.exec():
            selected_folders = folder_dialog.selectedFiles()
            if selected_folders:
                self.cache_location_edit.setText(selected_folders[0])
    
    def clear_cache(self):
        """Cancella i file della cache dopo conferma dell'utente."""
        reply = QMessageBox.question(
            self, 
            "Clear Cache", 
            "Are you sure you want to clear the cache?\nThis will remove all cached icons and temporary files.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                cache_path = self.cache_location_edit.text().strip()
                if not cache_path:
                    cache_path = "cache"  # Default
                
                cache_dir = Path(cache_path)
                if cache_dir.exists():
                    # Implementazione della logica per eliminare i file della cache
                    files_deleted = 0
                    total_size_cleaned = 0
                    
                    # Memorizza la struttura delle directory prima di eliminare
                    dir_structure = []
                    for root, dirs, files in os.walk(cache_dir):
                        # Salva il percorso relativo alla cache_dir
                        rel_path = Path(root).relative_to(cache_dir)
                        if str(rel_path) != '.':  # Ignora la directory principale
                            dir_structure.append(rel_path)
                    
                    # Elimina tutti i file
                    for root, dirs, files in os.walk(cache_dir):
                        for file in files:
                            file_path = Path(root) / file
                            try:
                                file_size = file_path.stat().st_size
                                file_path.unlink()  # Elimina il file
                                files_deleted += 1
                                total_size_cleaned += file_size
                                logging.debug(f"Deleted cache file: {file_path}")
                            except Exception as file_error:
                                logging.warning(f"Failed to delete cache file {file_path}: {file_error}")
                    
                    # Assiurati che le directory esistano ancora (potrebbero essere state eliminate indirettamente)
                    cache_dir.mkdir(exist_ok=True)  # Ricrea la directory principale se necessario
                    for rel_dir in dir_structure:
                        subdir = cache_dir / rel_dir
                        subdir.mkdir(exist_ok=True, parents=True)
                        logging.debug(f"Ensured cache subdirectory: {subdir}")
                    
                    # Ricrea specificamente la directory delle icone se era presente
                    icons_dir = cache_dir / "icons"
                    icons_dir.mkdir(exist_ok=True, parents=True)
                    
                    # Converti la dimensione totale in un formato leggibile
                    size_mb = total_size_cleaned / (1024 * 1024)
                    
                    QMessageBox.information(
                        self, 
                        "Cache Cleared", 
                        f"Cache has been successfully cleared.\n{files_deleted} files removed ({size_mb:.2f} MB freed)."
                    )
                    logging.info(f"Cache cleared: {files_deleted} files, {size_mb:.2f} MB")
                else:
                    # Se la directory non esiste, creala
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    icons_dir = cache_dir / "icons"
                    icons_dir.mkdir(exist_ok=True)
                    QMessageBox.information(self, "Info", "Cache directory did not exist and has been created.")
                    logging.info(f"Created cache directory at {cache_dir}")
            except Exception as e:
                logging.error(f"Error clearing cache: {e}")
                QMessageBox.warning(self, "Error", f"Failed to clear cache: {e}")

    def accept(self) -> None:
        """Salva le impostazioni e chiude la finestra di dialogo."""
        try:
            # Salva le impostazioni generali (senza tema)
            self.data_manager._data["check_updates_startup"] = self.check_updates_startup.isChecked()
            self.data_manager._data["sync_projects_startup"] = self.sync_projects_startup.isChecked()
            
            # Salva il percorso Godot (prelevando il valore dalla combo box se disponibile)
            selected_index = self.installed_versions_combo.currentIndex()
            if selected_index >= 0:
                selected_path = self.installed_versions_combo.itemData(selected_index)
                if selected_path is not None:
                    self.data_manager.set_godot_path(selected_path)
                    godot_path = selected_path  # Per evitare di sovrascrivere con il testo dell'edit box
                else:
                    godot_path = self.godot_path_edit.text().strip()
                    if godot_path:
                        self.data_manager.set_godot_path(godot_path)
            else:
                godot_path = self.godot_path_edit.text().strip()
                if godot_path:
                    self.data_manager.set_godot_path(godot_path)
            
            # Salva il percorso di download delle versioni (unificato)
            versions_download_path = self.versions_download_edit.text().strip()
            if versions_download_path:
                # Salva sia in versions_download_path che in godot_versions_path_key
                self.data_manager._data["versions_download_path"] = versions_download_path
                self.data_manager.set_godot_versions_path(versions_download_path)
            
            # Salva le impostazioni della cache
            self.data_manager._data["cache_location"] = self.cache_location_edit.text().strip()
            self.data_manager._data["max_cache_size_mb"] = self.cache_size_spin.value()
            
            # Salva le impostazioni di logging
            log_level_map = {0: "DEBUG", 1: "INFO", 2: "WARNING", 3: "ERROR", 4: "CRITICAL"}
            self.data_manager._data["log_level"] = log_level_map[self.log_level_combo.currentIndex()]
            self.data_manager._data["verbose_logging"] = self.verbose_logging_checkbox.isChecked()
            
            # Salva le modifiche al file JSON
            self.data_manager.save_data()
            
            # Chiudi la finestra di dialogo
            super().accept()
        except Exception as e:
            logging.error(f"Error saving settings: {e}")
            QMessageBox.warning(self, "Settings Error", f"Error saving settings: {e}")

    def reject(self):
        """Handles dialog rejection (Cancel button or closing)."""
        logging.info("SettingsDialog rejected/cancelled.")
        # Cancel any ongoing download before closing
        if self.is_downloading_godot:
            self.cancel_godot_download()
        super().reject() # Close the dialog

    def fetch_github_releases(self):
        """Fetches the list of Godot releases from GitHub API."""
        logging.info("Fetching GitHub releases...")
        if self.github_thread and self.github_thread.isRunning():
            logging.warning("GitHub fetch already in progress.")
            # Optionally update status or just return
            # self.download_status_label.setText("Download Status: Refreshing list...")
            return

        # Update UI to indicate loading state
        self.versions_combo.clear()
        self.versions_combo.addItem("Loading...")
        self.versions_combo.setEnabled(False)
        self.download_version_btn.setEnabled(False)
        self.refresh_versions_btn.setEnabled(False) # Disable refresh while refreshing
        self.download_status_label.setText("Download Status: Contacting GitHub API...")

        # Start the background thread
        self.github_thread = GitHubReleasesThread()
        self.github_thread.releases_fetched.connect(self.on_releases_fetched)
        self.github_thread.fetch_error.connect(self.on_releases_fetch_error)
        self.github_thread.finished.connect(self.on_releases_thread_finished)
        self.github_thread.start()

    def on_releases_fetched(self, releases: list):
        """Populates the versions combo box with fetched GitHub releases."""
        logging.info(f"Received {len(releases)} releases from GitHub.")
        self.versions_combo.clear()
        if not releases:
            self.versions_combo.addItem("No releases found.")
            self.download_status_label.setText("Download Status: No releases found on GitHub.")
            return

        added_count = 0
        # Filter for stable or rc releases and add them to the combo box
        for release in releases:
            tag = release.get("tag_name")
            # Simple check for stability markers in tag name
            if tag and ("stable" in tag or "rc" in tag):
                self.versions_combo.addItem(tag, userData=release) # Store full release data
                added_count += 1

        if added_count > 0:
            self.versions_combo.setEnabled(True)
            self.download_status_label.setText(f"Download Status: Select a version ({added_count} found).")
            self.on_github_version_selected() # Update download button state
        else:
            self.versions_combo.addItem("No stable/RC releases found.")
            self.download_status_label.setText("Download Status: No stable/RC releases found.")

    def on_releases_fetch_error(self, error_msg: str):
        """Handles errors during the GitHub releases fetch."""
        log_and_show_error(
            title="GitHub Fetch Error",
            message=f"Could not fetch Godot releases from GitHub:\n{error_msg}",
            level="warning", # Was warning
            parent=self,
            log_message="Error fetching GitHub releases" # Specific log message
        )
        self.versions_combo.clear()
        self.versions_combo.addItem("Error fetching releases")
        self.versions_combo.setEnabled(False)
        self.download_version_btn.setEnabled(False)
        self.refresh_versions_btn.setEnabled(True) # Allow retry

    def on_releases_thread_finished(self):
        """Cleans up after the GitHub fetch thread finishes."""
        logging.debug("GitHub releases fetch thread finished.")
        self.github_thread = None
        self.refresh_versions_btn.setEnabled(True) # Re-enable refresh button

    def on_github_version_selected(self):
        """Enables/disables the download button based on the selected GitHub version."""
        release_data = self.versions_combo.currentData()
        # Enable download only if valid data is selected and not currently downloading
        can_download = isinstance(release_data, dict) and not self.is_downloading_godot
        logging.debug(f"GitHub version selection changed. Can download: {can_download}")
        self.download_version_btn.setEnabled(can_download)

    def check_overall_validity(self):
        """Checks all input fields and updates the OK button state."""
        # Enable the OK button if everything is valid
        self.ok_button.setEnabled(True)
        # This is a simple implementation - you could add more validation if needed

    def _scan_and_populate_installed_versions(self):
        """
        Scans the versions download directory for installed Godot versions and populates the dropdown.
        Uses the structure: versions_folder/version_tag/godot_executable
        """
        logging.info("Scanning for installed Godot versions...")
        self.installed_versions_combo.clear()
        versions_path_str = self.versions_download_edit.text().strip()
        
        # Add "Use system Godot" option which corresponds to None
        self.installed_versions_combo.addItem("Use system Godot", None)
        
        if not versions_path_str or not Path(versions_path_str).exists():
            logging.debug(f"No valid versions path configured or directory does not exist: {versions_path_str}")
            return
            
        versions_path = Path(versions_path_str)
        
        try:
            # Look for version subdirectories
            count = 0
            for version_dir in versions_path.glob("*"):
                if not version_dir.is_dir():
                    continue
                    
                version_tag = version_dir.name
                exec_path = self.find_executable_in_folder(version_dir)
                
                if exec_path:
                    display_name = f"{version_tag} ({exec_path.name})"
                    self.installed_versions_combo.addItem(display_name, str(exec_path))
                    count += 1
                    logging.debug(f"Found version: {display_name} at {exec_path}")
            
            if count > 0:
                logging.info(f"Found {count} installed Godot versions")
            else:
                logging.info("No installed Godot versions found")
                
        except Exception as e:
            logging.error(f"Error scanning for installed versions: {e}")
            
        # Set current selection to match the default path if possible
        current_godot_path = self.data_manager.get_godot_path()
        if current_godot_path:
            for i in range(self.installed_versions_combo.count()):
                item_path = self.installed_versions_combo.itemData(i)
                if item_path == current_godot_path:
                    self.installed_versions_combo.setCurrentIndex(i)
                    break

    def _find_download_asset(self, release_data: dict) -> Tuple[Optional[dict], Optional[str]]:
        """
        Finds the appropriate download asset for the current OS and architecture
        within the release data.

        Args:
            release_data: The dictionary containing release information from GitHub API.

        Returns:
            A tuple containing (asset_dict, asset_filename) if found, or (None, error_message) if not found.
        """
        assets = release_data.get("assets", [])
        if not assets:
            return None, "No assets available for this release"
            
        # Stampa gli asset disponibili per debug
        for asset in assets:
            name = asset.get("name", "")
            logging.debug(f"Available asset: {name}")
            
        os_name = platform.system().lower()
        arch = platform.machine().lower()
        
        # Per Windows ci sono vari formati possibili
        if os_name == "windows":
            # Cerca prima il formato più comune
            patterns = [
                "_win64.exe.zip",       # Formato standard dalla 4.x+
                "_win64.zip",           # Formato alternativo
                "_windows_64.exe.zip",  # Possibile formato alternativo
                ".windows.64.exe.zip",  # Formato più vecchio
                "_win32.exe.zip",       # Fallback per 32 bit se necessario
            ]
            
            # Se siamo su architettura a 32 bit, inverti l'ordine di priorità
            if "64" not in arch:
                patterns.reverse()
                
            # Cerca il primo asset che corrisponde a uno dei pattern
            for pattern in patterns:
                for asset in assets:
                    name = asset.get("name", "").lower()
                    if name.endswith(pattern):
                        return asset, name
        
        # Per Linux
        elif os_name == "linux":
            patterns = []
            if "64" in arch or "amd64" in arch:
                patterns = ["_linux_x86_64.zip", "_linux.x86_64.zip", "_linux_64.zip"]
            elif "aarch64" in arch or "arm64" in arch:
                patterns = ["_linux_arm64.zip", "_linux.arm64.zip"]
            # Aggiungere altri pattern per altre architetture se necessario
                
            for pattern in patterns:
                for asset in assets:
                    name = asset.get("name", "").lower()
                    if name.endswith(pattern):
                        return asset, name
        
        # Per macOS
        elif os_name == "darwin":
            patterns = []
            if "arm64" in arch or "aarch64" in arch:  # Apple Silicon
                patterns = ["_macos_arm64.zip", "_macos.arm64.zip", "_macos.universal.zip"]
            else:  # Intel
                patterns = ["_macos_x86_64.zip", "_macos.x86_64.zip", "_macos.universal.zip"]
                
            # Cerca il primo asset che corrisponde a uno dei pattern
            for pattern in patterns:
                for asset in assets:
                    name = asset.get("name", "").lower()
                    if name.endswith(pattern):
                        return asset, name
        
        # Se nessuna corrispondenza esatta, cerca qualsiasi file che contenga sia l'OS che l'architettura
        os_keywords = {
            "windows": ["win", "windows"],
            "linux": ["linux", "x11"],
            "darwin": ["macos", "osx", "mac"]
        }
        
        arch_keywords = {
            "x86_64": ["64", "x86_64", "amd64"],
            "i386": ["32", "x86", "i386"],
            "aarch64": ["arm64", "aarch64", "arm"]
        }
        
        current_os_keywords = os_keywords.get(os_name, [os_name])
        
        current_arch = "x86_64"
        if "64" not in arch and ("i386" in arch or "x86" in arch):
            current_arch = "i386"
        elif "aarch64" in arch or "arm64" in arch:
            current_arch = "aarch64"
            
        current_arch_keywords = arch_keywords.get(current_arch, [])
        
        # Ricerca generica
        for asset in assets:
            name = asset.get("name", "").lower()
            if any(kw in name for kw in current_os_keywords) and any(kw in name for kw in current_arch_keywords) and name.endswith(".zip"):
                logging.info(f"Found compatible asset via generic search: {name}")
                return asset, name
        
        # Se non è stato trovato nulla, mostra cosa stavamo cercando per aiutare il debug
        os_patterns = ", ".join(current_os_keywords)
        arch_patterns = ", ".join(current_arch_keywords)
        return None, f"No compatible download for {os_name} ({os_patterns}) with architecture {arch} ({arch_patterns})"

    def start_godot_download(self):
        """Initiates the download and extraction of the selected Godot version."""
        # Check if versions path is set and valid
        versions_path_str = self.versions_download_edit.text().strip()
        if not self._versions_path_is_valid or not versions_path_str:
            log_and_show_error(
                "Invalid Directory",
                "Please set a valid versions download directory before downloading.",
                level="warning",
                parent=self
            )
            return
        
        # Ensure the directory exists
        versions_path = Path(versions_path_str)
        versions_path.mkdir(parents=True, exist_ok=True)
        logging.info(f"Ensured versions directory exists: {versions_path}")
        
        # Verify that a version is selected in the combo box
        index = self.versions_combo.currentIndex()
        if index < 0 or not self.versions_combo.count():
            log_and_show_error(
                "No Version Selected",
                "Please select a Godot version to download.",
                level="warning",
                parent=self
            )
            return
        
        # Get the release data from the combo box
        release_data = self.versions_combo.currentData()
        if not release_data or not isinstance(release_data, dict):
            log_and_show_error(
                "Invalid Version",
                "Selected version information is invalid.",
                level="warning",
                parent=self
            )
            return
            
        # Get the version tag from the selected item
        version_tag = release_data.get("tag_name", "unknown-version")
        
        # Find the download asset for this OS
        asset, filename = self._find_download_asset(release_data)
        if not asset or not filename:
            log_and_show_error(
                "Download Not Available",
                f"No compatible download available for {version_tag} on your platform.",
                level="warning",
                parent=self
            )
            return
        
        download_url = asset.get("browser_download_url", "")
        if not download_url:
            log_and_show_error(
                "Download Error",
                "Could not determine download URL.",
                level="error",
                parent=self
            )
            return
        
        logging.info(f"Attempting to download Godot version: {version_tag}")
        
        # Create a temporary directory for the download
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix=f"godot_dl_{version_tag}_"))
            temp_path = temp_dir / filename
            
            logging.info(f"Downloading '{filename}' to temporary location: {temp_path}")
            
            # Set download state
            self.is_downloading_godot = True
            self.current_godot_download_info = {
                "version_tag": version_tag,
                "temp_path": temp_path, 
                "extract_dir": versions_path,
                "download_url": download_url
            }
            
            # Update UI state
            self.download_status_label.setText(f"Download Status: Starting download of {version_tag}...")
            self.download_version_btn.setVisible(False)
            self.cancel_download_btn.setVisible(True)
            self.download_progress_bar.setValue(0)
            self.download_progress_bar.setVisible(True)
            
            # Disable certain controls during download
            self.versions_combo.setEnabled(False)
            self.refresh_versions_btn.setEnabled(False)
            self.versions_download_edit.setEnabled(False)
            
            # Disabilitare il pulsante Browse per il percorso di download
            browse_btn = next((btn for btn in self.versions_download_edit.parent().findChildren(QPushButton) 
                         if "Browse" in btn.text()), None)
            if browse_btn:
                browse_btn.setEnabled(False)
                
            self.ok_button.setEnabled(False) # Disable OK during download
            
            # Set up the download thread
            self.godot_download_thread = DownloadThread(download_url, str(temp_path))
            self.godot_download_thread.progress.connect(self._update_godot_download_progress)
            self.godot_download_thread.finished.connect(self.on_godot_download_finished)
            
            # Start the download thread
            self.godot_download_thread.start()
            
        except Exception as e:
            # Reset download state
            self.is_downloading_godot = False
            self._reset_godot_download_ui()
            
            error_msg = f"Failed to start download: {e}"
            logging.error(error_msg)
            log_and_show_error(
                "Download Error", 
                error_msg,
                level="error",
                parent=self
            )

    def _update_godot_download_progress(self, value: int):
        """Updates the download progress bar."""
        if self.is_downloading_godot:
            if value == -1: # Indeterminate
                if self.download_progress_bar.maximum() != 0:
                    self.download_progress_bar.setRange(0, 0)
            else: # Determinate
                if self.download_progress_bar.maximum() == 0:
                    self.download_progress_bar.setRange(0, 100)
                self.download_progress_bar.setValue(value)

    def on_godot_download_finished(self, zip_path_str: Optional[str], error_msg: Optional[str]):
        """
        Callback triggered when the Godot download thread finishes.
        
        Args:
            zip_path_str: Path string to the downloaded ZIP file if successful, None otherwise.
            error_msg: Error message if the download failed, None if successful.
        """
        logging.debug(f"Godot download thread finished. Error: {error_msg}, Path: {zip_path_str}")
        
        if error_msg:
            # Handle download failure
            logging.error(f"Godot download failed: {error_msg}")
            self.download_status_label.setText(f"Download Status: Failed - {error_msg}")
            self._reset_godot_download_ui()
            log_and_show_error(
                "Download Failed",
                f"Failed to download Godot: {error_msg}",
                level="error",
                parent=self
            )
            return
            
        if not zip_path_str or not Path(zip_path_str).exists():
            # Handle invalid downloaded file
            logging.error("Godot download completed but ZIP file doesn't exist")
            self.download_status_label.setText("Download Status: Failed - ZIP file missing")
            self._reset_godot_download_ui()
            log_and_show_error(
                "Download Error",
                "Download completed but the ZIP file is missing.",
                level="error",
                parent=self
            )
            return
            
        # Download successful, proceed with extraction
        try:
            download_info = self.current_godot_download_info
            if not download_info:
                raise ValueError("Download info lost during download operation")
                
            zip_path = Path(zip_path_str)
            extract_to = download_info.get("extract_dir")
            version_tag = download_info.get("version_tag", "unknown")
            
            if not extract_to:
                raise ValueError("Extract directory information missing")
                
            self.download_status_label.setText("Download Status: Download successful, extracting...")
            
            # Perform extraction in the right directory structure
            self._perform_extraction(zip_path, extract_to, version_tag)
            
        except Exception as e:
            # Handle extraction setup failure
            error_msg = f"Failed to process download: {e}"
            logging.error(error_msg)
            self.download_status_label.setText(f"Download Status: Extraction setup failed - {e}")
            self._reset_godot_download_ui()
            log_and_show_error(
                "Extraction Error",
                error_msg,
                level="error",
                parent=self
            )

    def _perform_extraction(self, zip_path: Path, extract_to: Path, version_tag: str):
        """
        Handles the extraction of a downloaded Godot ZIP file.
        
        Args:
            zip_path: Path to the downloaded ZIP file
            extract_to: Directory path where extraction should occur
            version_tag: Version tag (e.g., 'v4.2.1-stable')
        """
        logging.info(f"Extracting Godot ZIP: {zip_path}")
        self.download_status_label.setText("Download Status: Extracting...")
        
        # Create version-specific directory
        version_dir = extract_to / version_tag
        
        try:
            # Ensure the directory exists
            version_dir.mkdir(parents=True, exist_ok=True)
            logging.info(f"Created version directory: {version_dir}")
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for zipinfo in zip_ref.infolist():
                    if "__MACOSX" in zipinfo.filename or zipinfo.filename.startswith("."):
                        # Skip macOS metadata and hidden files
                        continue
                        
                    # Extract file directly to the version directory
                    filename = os.path.basename(zipinfo.filename)
                    
                    # Skip if it's a directory entry
                    if not filename:
                        continue
                        
                    # Use the original filename as-is to preserve naming convention
                    extract_path = version_dir / filename
                    
                    # Extract the file
                    with zip_ref.open(zipinfo) as source, open(extract_path, 'wb') as target:
                        shutil.copyfileobj(source, target)
                        
                    # Make it executable if it's an actual executable (on non-Windows platforms)
                    if sys.platform != "win32" and (
                        filename.endswith(".exe") or 
                        not filename.endswith((".txt", ".md", ".pdf"))
                    ):
                        try:
                            extract_path.chmod(extract_path.stat().st_mode | 0o111)  # Add executable bit
                        except Exception as chmod_err:
                            logging.warning(f"Failed to make {extract_path} executable: {chmod_err}")
                    
                    logging.debug(f"Extracted: {extract_path}")
            
            # Verify executable exists
            exe_path = self.find_executable_in_folder(version_dir)
            if exe_path:
                self.download_status_label.setText(f"Download Status: Extraction complete. Found executable at {exe_path.name}")
                logging.info(f"Successfully extracted Godot {version_tag} to {version_dir}")
                
                # Immediately update installed versions list
                self._scan_and_populate_installed_versions()
                
                # Show success message
                QMessageBox.information(
                    self,
                    "Download Complete",
                    f"Successfully downloaded and extracted Godot {version_tag}.\n\nExecutable: {exe_path.name}"
                )
            else:
                self.download_status_label.setText(f"Download Status: Extraction complete, but no executable found in {version_dir}")
                logging.warning(f"No executable found in extracted directory: {version_dir}")
                
                # Show warning
                QMessageBox.warning(
                    self,
                    "Extraction Warning",
                    f"Godot {version_tag} extracted, but no executable was found.\n\nCheck the contents of: {version_dir}"
                )
        
        except (zipfile.BadZipFile, IOError, OSError) as e:
            error_msg = f"Error extracting ZIP file: {e}"
            logging.error(error_msg)
            self.download_status_label.setText(f"Download Status: {error_msg}")
            
            # Attempt to clean up the failed extraction
            try:
                if version_dir.exists():
                    shutil.rmtree(version_dir)
                    logging.info(f"Cleaned up failed extraction directory: {version_dir}")
            except Exception as cleanup_err:
                logging.warning(f"Failed to clean up directory after extraction error: {cleanup_err}")
            
            # Show error message
            QMessageBox.critical(
                self,
                "Extraction Failed",
                f"Failed to extract Godot {version_tag}.\n\nError: {e}"
            )
        
        except Exception as e:
            error_msg = f"Unexpected error during extraction: {e}"
            logging.exception(error_msg)
            self.download_status_label.setText(f"Download Status: {error_msg}")
            
            # Show error message
            QMessageBox.critical(
                self,
                "Extraction Error",
                f"An unexpected error occurred while extracting Godot {version_tag}.\n\nError: {e}"
            )
            
        finally:
            # Clean up the downloaded ZIP file
            try:
                if zip_path.exists():
                    zip_path.unlink()
                    logging.debug(f"Cleaned up temporary ZIP file: {zip_path}")
                
                # Try to remove the temporary directory if empty
                temp_dir = zip_path.parent
                if temp_dir.exists() and not any(temp_dir.iterdir()):
                    temp_dir.rmdir()
                    logging.debug(f"Removed empty temporary directory: {temp_dir}")
            except Exception as e:
                logging.warning(f"Failed to clean up temporary files: {e}")
            
            # Reset UI
            self._reset_godot_download_ui()
            self.download_progress_bar.setVisible(False)

    def _cleanup_zip(self, zip_path: Path):
        """Attempts to delete the downloaded ZIP file."""
        if zip_path and zip_path.is_file():
            try:
                logging.info(f"Attempting to remove downloaded ZIP file: {zip_path}")
                zip_path.unlink()
                logging.info(f"Successfully removed ZIP file: {zip_path}")
            except OSError as e:
                logging.warning(f"Failed to remove ZIP file {zip_path}: {e}")
        else:
            logging.warning(f"ZIP file path not valid or file does not exist: {zip_path}")

    @staticmethod
    def find_executable_in_folder(folder_path: Path) -> Optional[Path]:
        """
        Finds a Godot executable in the given folder.
        
        Args:
            folder_path: Path to the folder to search in.
        
        Returns:
            Path to the executable if found, None otherwise.
        """
        if not folder_path.exists() or not folder_path.is_dir():
            logging.warning(f"Cannot search for executable in non-existent directory: {folder_path}")
            return None
        
        logging.debug(f"Searching for Godot executable in {folder_path}")
        
        # Patterns per sistemi operativi diversi
        if sys.platform == "win32":
            # Su Windows cerchiamo prima la versione non console
            patterns = [
                r"Godot.*\.exe$",  # Standard Godot exe, priorità più alta
                r"godot.*\.exe$",  # Variante con 'g' minuscola
                r".*\.exe$"        # Qualsiasi exe come ultima risorsa
            ]
            # Escludi file con "console" nel nome
            exclude_patterns = [r".*console.*\.exe$"]
        elif sys.platform == "darwin":
            patterns = [
                r"Godot.*\.app$",    # Standard Godot app bundle
                r"godot.*\.app$",    # Variante con 'g' minuscola
                r"Godot$",           # Binary eseguibile senza estensione
                r"godot$"            # Binary con 'g' minuscola
            ]
            exclude_patterns = []    # Non ci sono versioni console su macOS
        else:  # Linux, etc.
            patterns = [
                r"Godot.*$",         # Standard Godot binary
                r"godot.*$"          # Variante con 'g' minuscola
            ]
            exclude_patterns = []    # Non ci sono versioni console specifiche su Linux
        
        # Prima cerca file che corrispondono ai pattern ma non sono console
        for pattern in patterns:
            for file_path in folder_path.glob("*"):
                if file_path.is_file() and re.match(pattern, file_path.name, re.IGNORECASE):
                    # Verifica che non sia un file da escludere
                    should_exclude = any(
                        re.match(excl, file_path.name, re.IGNORECASE) 
                        for excl in exclude_patterns
                    )
                    if not should_exclude:
                        logging.info(f"Found Godot executable: {file_path}")
                        return file_path
        
        # Se non trova un file non-console, accetta anche le versioni console su Windows
        if sys.platform == "win32":
            for file_path in folder_path.glob("*console*.exe"):
                if file_path.is_file():
                    logging.info(f"Found Godot console executable: {file_path}")
                    return file_path
        
        logging.warning(f"No Godot executable found in {folder_path}")
        return None

    def cancel_godot_download(self):
        """Cancels the currently active Godot download."""
        logging.info("Requesting Godot download cancellation.")
        if self.is_downloading_godot and self.godot_download_thread and self.godot_download_thread.isRunning():
            logging.info("Stopping Godot download thread...")
            self.godot_download_thread.stop()
            self.download_status_label.setText("Download Status: Cancelling...")
            self.cancel_download_btn.setEnabled(False) # Disable button while cancelling
            # The finished signal will still fire, triggering cleanup in on_godot_download_finished
        else:
            logging.warning("Cancel download clicked, but no active Godot download found.")

    def _reset_godot_download_ui(self):
        """Resets the UI elements after a download is completed or cancelled."""
        logging.debug("Resetting Godot download UI elements")
        
        # Reset state variables
        self.is_downloading_godot = False
        self.current_godot_download_info = {}
        
        # Reset thread reference (thread is already terminated by this point)
        self.godot_download_thread = None
        
        # Reset UI elements
        self.download_version_btn.setVisible(True)
        self.download_version_btn.setEnabled(True)
        self.cancel_download_btn.setVisible(False)
        
        self.versions_combo.setEnabled(True)
        self.refresh_versions_btn.setEnabled(True)
        self.versions_download_edit.setEnabled(True)
        
        # Abilitare il pulsante Browse per il percorso di download
        browse_btn = next((btn for btn in self.versions_download_edit.parent().findChildren(QPushButton) 
                      if "Browse" in btn.text()), None)
        if browse_btn:
            browse_btn.setEnabled(True)
            
        self.installed_versions_combo.setEnabled(True)
        self.rescan_versions_btn.setEnabled(True)
        
        # Re-enable the OK button
        if hasattr(self, 'ok_button') and self.ok_button:
            self.ok_button.setEnabled(True)
            
        # Reset download progress
        self.download_progress_bar.setValue(0)
        self.download_progress_bar.setVisible(False)

    def clear_log_file(self):
        """Elimina il file di log dell'applicazione dopo conferma dell'utente."""
        reply = QMessageBox.question(
            self, 
            "Clear Log File", 
            "Are you sure you want to clear the log file?\nThis will remove all application logs.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                log_file_path = Path("launcher.log")
                
                if log_file_path.exists():
                    # Tenta di eliminare il file
                    try:
                        log_file_path.unlink()
                        QMessageBox.information(self, "Log Cleared", "Log file has been successfully cleared.")
                        # Ricrea un file di log vuoto per permettere al logger di continuare a funzionare
                        with open(log_file_path, "w", encoding="utf-8") as f:
                            f.write("")
                        logging.info("Log file has been cleared and recreated")
                    except PermissionError:
                        # Se il file è in uso dal logger, troncalo invece di eliminarlo
                        with open(log_file_path, "w", encoding="utf-8") as f:
                            f.write("")
                        QMessageBox.information(self, "Log Cleared", "Log file has been successfully cleared.")
                        logging.info("Log file has been truncated (cleared)")
                else:
                    QMessageBox.information(self, "Info", "Log file does not exist.")
            except Exception as e:
                logging.error(f"Error clearing log file: {e}")
                QMessageBox.warning(self, "Error", f"Failed to clear log file: {e}")

    def on_installed_version_selected(self):
        """Aggiorna il percorso di Godot quando viene selezionata una versione installata."""
        selected_path = self.installed_versions_combo.currentData()
        # Aggiorna il campo di testo del percorso Godot
        if selected_path is not None:
            self.godot_path_edit.setText(selected_path)
            self.update_godot_version_label(selected_path)
        # Se è selezionato "Use system Godot", manteniamo il valore esistente
