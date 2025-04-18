# -*- coding: utf-8 -*-
# project_handler.py

import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile # Added
from pathlib import Path
import re
from typing import Dict, List, Optional, Set
import requests

from PyQt6.QtCore import QCoreApplication, QThread, QObject, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QApplication

# Import necessary modules and classes
from data_manager import DataManager # Use the DataManager class
from utils import (
    DownloadThread,
    extract_zip,
)  # Per ExtensionInstaller e install_extensions_logic
from api_clients import fetch_asset_details_sync  # Per ExtensionInstaller

# Constants
DEFAULT_ICON_NAME = "icon.svg"
GODOT_ICON_URL = "https://raw.githubusercontent.com/godotengine/godot/master/icon.svg" # Official Godot icon URL


# --- Godot Path Validation and Launching Functions ---
def browse_godot_executable(parent_widget, current_path=""):
    """Opens a file dialog to select a Godot executable or .app bundle."""
    if sys.platform == "win32":
        filter_str = "Godot Executable (*.exe);;All files (*)"
        start_dir = Path(current_path).parent if current_path else "C:\\"
    elif sys.platform == "darwin":
        filter_str = "Godot Application (*.app);;All files (*)"
        start_dir = Path(current_path).parent if current_path else "/Applications"
    else: # Linux, etc.
        filter_str = "All files (*)"
        start_dir = Path(current_path).parent if current_path else "/usr/bin"

    filepath, _ = QFileDialog.getOpenFileName(
        parent_widget, "Select Godot Executable/App", str(start_dir), filter_str
    )
    return filepath if filepath else None


def validate_godot_path(path_str: Optional[str]) -> tuple[bool, Optional[str]]:
    """
    Validates if the given path points to a potentially valid Godot executable or .app bundle.
    Checks for existence and executable permissions (where applicable).
    Returns a tuple (is_valid, version_string) where:
    - is_valid: True if path exists and is executable (or None/empty - considered valid as 'not set')
    - version_string: String with the version if valid and available, None otherwise
    """
    if not path_str:
        return True, None
    path_obj = Path(path_str)
    if sys.platform == "darwin" and path_obj.is_dir() and path_str.endswith(".app"):
        exec1 = path_obj / "Contents/MacOS/Godot"
        # Check inside macOS .app bundle
        exec1 = path_obj / "Contents/MacOS/Godot"
        exec2 = path_obj / "Contents/MacOS/Godot_mono" # Check for mono version too
        is_valid = (exec1.is_file() and os.access(exec1, os.X_OK)) or \
                   (exec2.is_file() and os.access(exec2, os.X_OK))
        if not is_valid:
            logging.warning(f"Invalid or non-executable .app bundle: {path_obj}")
            return is_valid, None
        return is_valid, get_godot_version_string(path_str)
    elif path_obj.is_file():
        # Check if it's a file and executable (or on Windows where os.X_OK might not be reliable)
        is_exec = os.access(path_obj, os.X_OK) or sys.platform == "win32"
        if not is_exec:
            logging.warning(f"File is not executable: {path_obj}")
            return is_exec, None
        return is_exec, get_godot_version_string(path_str)
    else:
        logging.warning(f"Invalid Godot path (not a file or valid .app): {path_obj}")
        return False, None


def get_godot_executable_for_path(godot_engine_path_str: Optional[str]) -> Optional[str]:
    """
    Given a path string (which might be a .app bundle on macOS), returns the actual
    path to the executable binary inside it, or the path itself if it's already an executable file.
    Returns None if the path is invalid or the executable cannot be found.
    """
    if not godot_engine_path_str:
        return None
    path_obj = Path(godot_engine_path_str)
    if (
        sys.platform == "darwin"
        and path_obj.is_dir()
        and godot_engine_path_str.endswith(".app")
    ):
        exec1 = path_obj / "Contents/MacOS/Godot"
        exec2 = path_obj / "Contents/MacOS/Godot_mono"
        if exec1.is_file() and os.access(exec1, os.X_OK):
            return str(exec1)
        # Check for standard and mono executables within the .app bundle
        exec1 = path_obj / "Contents/MacOS/Godot"
        exec2 = path_obj / "Contents/MacOS/Godot_mono"
        if exec1.is_file() and os.access(exec1, os.X_OK):
            return str(exec1)
        if exec2.is_file() and os.access(exec2, os.X_OK):
            return str(exec2)
        logging.warning(f"Executable not found inside .app bundle: {path_obj}")
        return None
    elif path_obj.is_file() and (os.access(path_obj, os.X_OK) or sys.platform == "win32"):
        # If it's a file and executable (or on Windows)
        return str(path_obj)
    else:
        logging.warning(f"Path is not a valid executable file or .app bundle: {godot_engine_path_str}")
        return None


def launch_project_editor(project_path: Path, godot_engine_path: str) -> bool:
    """
    Launches the Godot editor for the specified project using the given Godot engine path.

    Args:
        project_path: Path object for the project directory.
        godot_engine_path: Path string for the Godot executable or .app bundle.

    Returns:
        True if the launch command was successfully initiated, False otherwise.
    """
    proj_path_obj = Path(project_path)
    godot_exe = get_godot_executable_for_path(godot_engine_path)
    if not godot_exe:
        logging.error(f"Invalid Godot path for launch: {godot_engine_path}")
        QMessageBox.critical(
            None, "Error", f"Invalid Godot path:\n{godot_engine_path}"
        )
        return False

    # Check if project.godot exists
    if not (proj_path_obj / "project.godot").is_file():
        logging.error(f"'project.godot' not found in {proj_path_obj}")
        QMessageBox.critical(
            None, "Error", f"'project.godot' not found in:\n{proj_path_obj}"
        )
        return False

    # Construct and execute the command
    try:
        cmd = [godot_exe, "--editor", "--path", str(proj_path_obj)]
        logging.info(f"Launching Godot: {' '.join(cmd)}")
        # Use Popen for non-blocking launch
        proc = subprocess.Popen(cmd, cwd=str(proj_path_obj))
        logging.info(f"Godot process started (PID: {proc.pid})")
        return True
    except Exception as e:
        logging.exception("Failed to launch Godot editor")
        QMessageBox.critical(None, "Error", f"Failed to launch Godot:\n{e}")
        return False


def launch_project_run(project_path: Path, godot_engine_path: str) -> bool:
    """
    Launches the specified project directly (runs the game/application).

    Args:
        project_path: Path object for the project directory.
        godot_engine_path: Path string for the Godot executable or .app bundle.

    Returns:
        True if the launch command was successfully initiated, False otherwise.
    """
    proj_path_obj = Path(project_path)
    godot_exe = get_godot_executable_for_path(godot_engine_path)
    if not godot_exe:
        logging.error(f"Invalid Godot path for run: {godot_engine_path}")
        QMessageBox.critical(
            None, "Error", f"Invalid Godot path:\n{godot_engine_path}"
        )
        return False

    # Check if project path exists (project.godot check is less critical for running)
    if not proj_path_obj.is_dir():
        logging.error(f"Project directory not found: {proj_path_obj}")
        QMessageBox.critical(
            None, "Error", f"Project directory not found:\n{proj_path_obj}"
        )
        return False

    # Construct and execute the command (no --editor flag)
    try:
        cmd = [godot_exe, "--path", str(proj_path_obj)]
        logging.info(f"Running Godot project: {' '.join(cmd)}")
        # Use Popen for non-blocking launch
        proc = subprocess.Popen(cmd, cwd=str(proj_path_obj))
        logging.info(f"Godot project process started (PID: {proc.pid})")
        return True
    except Exception as e:
        logging.exception("Failed to run Godot project")
        QMessageBox.critical(None, "Error", f"Failed to run project:\n{e}")
        return False


# --- Project Management Functions ---
def get_project_name_from_file(project_path: Path) -> Optional[str]:
    """
    Reads the 'project.godot' file in the given directory and extracts the
    project name from the 'config/name' property.

    Args:
        project_path: Path object for the project directory.

    Returns:
        The project name string if found, otherwise None.
    """
    project_file = project_path / "project.godot"
    if not project_file.is_file():
        return None # project.godot not found

    try:
        with open(project_file, "r", encoding="utf-8") as f:
            for line in f:
                clean_line = line.strip()
                # Look for the line defining the project name
                if clean_line.startswith("config/name"):
                    parts = clean_line.split("=", 1)
                    if len(parts) == 2:
                        value_part = parts[1].strip()
                        # Extract name from quotes "Project Name"
                        if (
                            len(value_part) >= 2
                            and value_part[0] in ('"', "'") # Check for starting quote
                            and value_part[0] == value_part[-1] # Check for matching ending quote
                        ):
                            return value_part[1:-1] # Return content within quotes
        # If loop finishes without finding the name
        logging.warning(f"'config/name' not found or invalid format in {project_file}")
        return None
    except Exception as e:
        logging.error(f"Error reading {project_file}: {e}")
        return None


def scan_projects_folder(folder_path: Path, recursive: bool = True) -> Dict[str, str]:
    """
    Scans a given folder recursively for subdirectories containing a 'project.godot' file
    and extracts their project names.

    Args:
        folder_path: Path object for the folder to scan.
        recursive: If True, scans subdirectories recursively.

    Returns:
        A dictionary mapping project names to their absolute path strings.
        Returns an empty dictionary if the folder_path is invalid or not a directory.
    """
    found_projects: Dict[str, str] = {}
    if not folder_path or not folder_path.is_dir():
        logging.warning(f"Scan skipped: Invalid or non-existent folder path: {folder_path}")
        return found_projects

    logging.info(f"Scanning projects folder{' recursively' if recursive else ''}: {folder_path}")
    folders_to_scan = [folder_path]
    scanned_folders: Set[Path] = set()

    while folders_to_scan:
        current_folder = folders_to_scan.pop(0)
        if current_folder in scanned_folders:
            continue # Avoid rescanning or infinite loops with symlinks
        scanned_folders.add(current_folder)

        logging.debug(f"Scanning directory: {current_folder}")
        try:
            # Check if the current folder itself is a Godot project
            project_name = get_project_name_from_file(current_folder)
            project_path_str = str(current_folder.resolve()) # Store resolved path
            if project_name:
                if project_name in found_projects:
                    logging.warning(
                        f"Duplicate project name '{project_name}' found during scan. "
                        f"Path '{found_projects[project_name]}' will be overwritten by '{project_path_str}'."
                    )
                found_projects[project_name] = project_path_str
                logging.info(
                    f"  -> Found: '{project_name}' in '{project_path_str}'"
                )
                # If we find a project, don't scan its subfolders unless recursion is very deep
                # This avoids finding nested demo projects etc. typically.
                # Change this logic if nested projects are desired.
                continue # Skip scanning subfolders of a found project folder

            # Iterate through items in the current folder if recursion is enabled
            if recursive:
                for item in current_folder.iterdir():
                    if item.is_dir(): # Check only subdirectories
                        # Basic check to avoid common large/unrelated directories
                        # TODO: Make this configurable or more robust?
                        if item.name.lower() in [".git", ".venv", "node_modules", "__pycache__", "cache", "assets"]:
                            logging.debug(f"Skipping common directory: {item.name}")
                            continue
                        if item not in scanned_folders:
                            folders_to_scan.append(item)
                    # else: # Check if the item is project.godot (alternative to get_project_name_from_file first)
                    #    pass

        except PermissionError:
             logging.warning(f"Permission denied scanning {current_folder}. Skipping.")
        except OSError as e:
            logging.error(f"OS error scanning {current_folder}: {e}", exc_info=False)
        except Exception as e:
            logging.exception(f"Unexpected error scanning {current_folder}")

    logging.info(f"Scan complete. Found {len(found_projects)} projects in {folder_path}.")
    return found_projects


def create_project_structure(project_path: Path, project_name: str, godot_exe_path: Optional[str], renderer_method: str) -> bool:
    """
    Creates a basic Godot project structure (folder and project.godot file)
    and downloads the default Godot icon.

    Args:
        project_path: The Path object where the project folder should be created.
        project_name: The name for the new project.
        godot_exe_path: Path to the Godot executable (used to determine version for features).
        renderer_method: The rendering method ("forward_plus", "mobile", "gl_compatibility").

    Returns:
        True if creation was successful, False otherwise.
    """
    godot_version = get_godot_version_string(godot_exe_path) if godot_exe_path else "4.2"
    # Determine Godot version string for features array
    godot_version = get_godot_version_string(godot_exe_path) if godot_exe_path else "4.x" # Use "4.x" if path unknown
    renderer_features = {"forward_plus": "Forward Plus", "mobile": "Mobile", "gl_compatibility": "Compatibility"}
    renderer_name_feature = renderer_features.get(renderer_method, "Mobile") # Default to Mobile if invalid method given

    logging.info(f"Creating project '{project_name}' (Godot ~{godot_version}, Renderer: {renderer_method}) at {project_path}")
    try:
        # 1. Create project directory
        project_path.mkdir(parents=True, exist_ok=False) # exist_ok=False to prevent overwriting
        logging.debug(f"Project directory created: {project_path}")

        # 2. Create basic project.godot file
        content = f"""; Engine configuration file generated by Godot Custom Launcher.

    config_version=5

    [application]

    config/name="{project_name}"
    config/features=PackedStringArray("{godot_version}", "{renderer_name_feature}")
    config/name="{project_name}"
    config/features=PackedStringArray("{godot_version}", "{renderer_name_feature}")
    config/icon="res://{DEFAULT_ICON_NAME}" # Points to the default icon
    config/resource_uid_capacity=8192 # Default UID capacity
    config/resource_uid_pool=PackedInt64Array() # Default UID pool

    [filesystem]

    resource_uid/check_missing_dependencies=true
    resource_uid/create_redirects=true
    resource_uid/rename_on_move=true # Recommended settings

    [rendering]

    renderer/rendering_method="{renderer_method}" # Set chosen renderer
    textures/vram_compression/import_etc2_astc=true # Enable modern compression

    """
        project_file = project_path / "project.godot"
        with open(project_file, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n") # Write content, ensuring a final newline
        logging.debug(f"project.godot file created: {project_file}")

        # 3. Download the default Godot icon
        icon_dest_path = project_path / DEFAULT_ICON_NAME
        logging.info(f"Downloading default Godot icon from {GODOT_ICON_URL} to {icon_dest_path}")
        try:
            headers = {"User-Agent": "GodotCustomLauncher/1.1 (Python)"} # Identify client
            response = requests.get(GODOT_ICON_URL, timeout=15, headers=headers)
            response.raise_for_status() # Check for HTTP errors

            # Save SVG content directly
            with open(icon_dest_path, "wb") as f: # Use 'wb' to write bytes
                f.write(response.content)
            logging.info("Default Godot icon downloaded successfully.")

        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to download default Godot icon: {e}. Project will be created without it.", exc_info=False)
            # Don't block project creation for this, but log the error.
            # The user can add the icon manually later.
        except Exception as e:
            logging.exception("Unexpected error during Godot icon download/save.")

        logging.info(f"Project structure for '{project_name}' created successfully.")
        return True

    except FileExistsError:
        logging.warning(f"Project creation failed: Directory '{project_path}' already exists.");
        QMessageBox.warning(None, "Error", f"Folder '{project_path.name}' already exists in the target directory.");
        return False
    except Exception as e:
        logging.exception(f"Project creation failed for '{project_name}'");
        QMessageBox.critical(None, "Error", f"Project creation failed:\n{e}");
        # Attempt to clean up created directory if creation failed mid-way
        if project_path.exists():
            try:
                logging.info(f"Attempting to clean up partially created project at {project_path}")
                shutil.rmtree(project_path)
            except OSError as rm_err:
                logging.error(f"Error cleaning up failed project directory {project_path}: {rm_err}")
        return False


def get_godot_version_string(godot_path: Optional[str]) -> str:
    """
    Attempts to extract a significant version string (e.g., "4.2", "3.5", "4")
    from the executable path or version folder name.

    Args:
        godot_path: The path string to the Godot executable or version folder.

    Returns:
        A version string like "X.Y" or "X". Defaults to "4.x" if extraction fails or path is None.
    """
    if not godot_path:
        logging.warning("get_godot_version_string: Godot path is None, using default '4.x'")
        return "4.x" # Generic default if no path is set

    try:
        path_part = Path(godot_path).name # Get the filename or folder name
        # Pattern to find versions like X.Y.Z, X.Y, vX.Y.Z, vX.Y
        # Prioritize X.Y.Z or vX.Y.Z first
        match_xyz = re.search(r"v?(\d+\.\d+\.\d+)", path_part)
        if match_xyz:
            version = match_xyz.group(1)
            logging.debug(f"Extracted Godot version (X.Y.Z): {version} from {path_part}")
            # Return major.minor (e.g., "4.2") as the API often uses this
            return ".".join(version.split(".")[:2])

        # Try X.Y or vX.Y
        match_xy = re.search(r"v?(\d+\.\d+)", path_part)
        if match_xy:
            version = match_xy.group(1)
            logging.debug(f"Extracted Godot version (X.Y): {version} from {path_part}")
            return version # e.g., "4.2"

        # Try just the major version (e.g., v4)
        match_x = re.search(r"v?(\d+)", path_part)
        if match_x:
            version = match_x.group(1)
            logging.debug(f"Extracted Godot version (X): {version} from {path_part}")
            return version # e.g., "4"

        logging.warning(
            f"Could not extract version from '{path_part}'. Using default '4.x'."
        )
        return "4.x" # Final fallback

    except Exception as e:
        logging.error(
            f"Error extracting version from '{godot_path}': {e}. Using default '4.x'."
        )
        return "4.x"


# --- Extension Installation Logic ---
class ExtensionInstaller(QThread):
    """
    A QThread worker to download and install a single Godot asset (extension/template)
    into a specified project's 'addons' folder.
    """
    progress = pyqtSignal(int) # Overall progress (0-100), -1 for indeterminate
    status_update = pyqtSignal(str) # User-friendly status message
    finished = pyqtSignal(int, bool, str) # asset_id, success (bool), final message

    def __init__(self, asset_id: int, project_path: Path, data_manager: DataManager):
        """
        Initializes the ExtensionInstaller.

        Args:
            asset_id: The ID of the asset to install.
            project_path: The Path object for the target project directory.
            data_manager: The DataManager instance (passed but not directly used in run).
        """
        super().__init__()
        self.asset_id = asset_id
        self.project_path = project_path
        self.data_manager = data_manager # Store DataManager instance (might be useful later)
        self.download_thread: Optional[DownloadThread] = None
        # Define temporary directory using system temp + specific subfolder
        try:
            system_temp_dir = Path(tempfile.gettempdir())
            self.temp_dir = system_temp_dir / "godot_launcher_temp" / "godot_extensions"
        except Exception as e:
            logging.error(f"Failed to determine temporary directory: {e}. Falling back.")
            # Fallback to relative path if system temp fails
            self.temp_dir = Path("./temp_download_extension_fallback")

        self.zip_save_path = self.temp_dir / f"asset_{self.asset_id}.zip"
        self._is_running = True
        self.setObjectName(f"ExtensionInstaller_{asset_id}") # For logging

    def stop(self):
        """Requests the installer thread and any active download sub-thread to stop."""
        logging.info(f"Requesting stop for {self.objectName()}")
        self._is_running = False
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.stop() # Propagate stop request to download thread

    def run(self):
        """Executes the download and extraction process for the asset."""
        logging.info(f"Starting {self.objectName()} for project {self.project_path}")
        if not self._is_running:
            logging.warning(f"{self.objectName()} cancelled before start.")
            # Emit finished signal for consistency, indicating cancellation
            self.finished.emit(self.asset_id, False, "Cancelled before start.")
            return

        addons_dir = self.project_path / "addons"
        addons_dir.mkdir(exist_ok=True) # Ensure addons directory exists
        error_message: Optional[str] = None
        success = False
        asset_title = f"Asset_{self.asset_id}" # Default title
        final_dl_error: Optional[str] = None # To store error from download thread signal

        try:
            # 1. Fetch Asset Details
            logging.debug(f"Fetching details for asset ID {self.asset_id}...")
            self.status_update.emit(f"Getting info for ID {self.asset_id}...")
            self.progress.emit(10) # Initial progress
            asset_details = fetch_asset_details_sync(self.asset_id)

            if not self._is_running: raise InterruptedError("Cancelled after fetching details")
            if not asset_details: raise ValueError(f"Details not found for asset ID {self.asset_id}.")

            download_url = asset_details.get("download_url")
            asset_title = asset_details.get("title", asset_title) # Use real title if available
            if not download_url: raise ValueError(f"Download URL not found for asset ID {self.asset_id}.")

            logging.debug(f"Details obtained: Title='{asset_title}', URL='{download_url}'")
            self.progress.emit(20)
            self.status_update.emit(f"Downloading '{asset_title}'...")

            # 2. Download Asset ZIP (using DownloadThread and wait())
            logging.debug("Preparing DownloadThread...")
            # Ensure the calculated temporary directory exists
            try:
                self.temp_dir.mkdir(parents=True, exist_ok=True)
                logging.debug(f"Ensured temporary directory exists: {self.temp_dir}")
            except Exception as e:
                 logging.exception(f"Failed to create temporary directory {self.temp_dir} before download.")
                 raise IOError(f"Could not create temporary directory: {e}") from e

            self.download_thread = DownloadThread(download_url, str(self.zip_save_path))

            # Connect signals BEFORE starting the thread
            self.download_thread.progress.connect(self._handle_download_progress)
            self.download_thread.status_update.connect(self.status_update.emit) # Forward status

            # Local function to capture the error from the download thread's finished signal
            def store_dl_error(path: str, error: Optional[str]):
                nonlocal final_dl_error
                final_dl_error = error
                logging.debug(f"DownloadThread finished signal received. Error: '{error}'")

            self.download_thread.finished.connect(store_dl_error)

            logging.debug("Starting DownloadThread...")
            self.download_thread.start()
            logging.debug("Waiting for DownloadThread to finish (wait)...")
            # wait() blocks execution of *this* thread (ExtensionInstaller)
            # until download_thread finishes.
            self.download_thread.wait()
            logging.debug("DownloadThread finished (wait returned).")

            # Check status AFTER wait() has returned
            if not self._is_running:
                # If stop() was called on ExtensionInstaller WHILE it was waiting
                error_msg_dl = final_dl_error if final_dl_error else "Cancelled during download wait"
                raise InterruptedError(error_msg_dl)
            if final_dl_error:
                # If the download finished but reported an error
                raise ConnectionError(f"Download failed: {final_dl_error}")

            # If we are here, download finished successfully without cancellation

            # 3. Extract ZIP
            logging.info("Proceeding with extraction...")
            self.progress.emit(80) # Progress before extraction
            self.status_update.emit(f"Extracting '{asset_title}'...")

            # No need to re-check _is_running here, wait() would have exited with exception if cancelled

            logging.info(f"Attempting ZIP extraction: {self.zip_save_path} -> {addons_dir}")
            # extract_zip handles different common addon structures
            extract_zip(self.zip_save_path, addons_dir, remove_common_prefix=True)
            logging.info("ZIP extraction completed.")

            # Check cancellation AFTER extraction (unlikely, but for safety)
            if not self._is_running: raise InterruptedError("Cancelled after extraction")

            # If we reach here, everything succeeded
            success = True
            error_message = f"'{asset_title}' (ID:{self.asset_id}) installed successfully."
            self.progress.emit(100)
            self.status_update.emit(f"'{asset_title}' installed.")

        except (ValueError, ConnectionError, FileNotFoundError, IOError) as e:
            # Known errors during the process
            error_message = f"Installation failed: {e}"
            logging.error(f"Error installing asset ID {self.asset_id}: {error_message}", exc_info=False)
        except InterruptedError as e:
            # Explicit cancellation
            error_message = f"Installation cancelled: {e}"
            logging.info(f"Installation cancelled for asset ID {self.asset_id} ({error_message}).")
            success = False # Ensure success is False
        except Exception as e:
            # Unexpected errors
            error_message = f"Unexpected error installing asset ID {self.asset_id}: {e}"
            logging.exception(error_message) # Log the full traceback
        finally:
            # Clean up download thread reference
            self.download_thread = None
            # Clean up temporary ZIP file
            if self.zip_save_path.exists():
                try:
                    self.zip_save_path.unlink()
                    logging.debug(f"Removed temp ZIP: {self.zip_save_path}")
                    # Attempt to remove temp directory if empty
                    if self.temp_dir.exists() and not any(self.temp_dir.iterdir()):
                        self.temp_dir.rmdir()
                        logging.debug(f"Removed empty temp directory: {self.temp_dir}")
                except OSError as e:
                    logging.warning(f"Failed to clean up temp ZIP/dir {self.zip_save_path}: {e}")

            # Prepare final message
            final_msg = error_message if error_message else "Completed successfully."
            logging.info(f"{self.objectName()} finished. Success: {success}, Msg: {final_msg}")
            # Emit finished signal in all cases (success, error, cancellation)
            self.finished.emit(self.asset_id, success, final_msg)

    def _handle_download_progress(self, percent: int):
        """Scales download progress (0-100) to the overall installer progress (20-80)."""
        if self._is_running:
            # Map 0-100% download progress to 20-80% overall progress
            total_progress = 20 + int(percent * 0.6) if percent >= 0 else -1 # Handle indeterminate (-1)
            self.progress.emit(total_progress)


def install_extensions_logic(
    asset_ids: List[int],
    project_path: Path,
    data_manager: DataManager, # Accept DataManager instance
    status_label, # Optional status label widget
    progress_bar, # Optional progress bar widget
    cancel_button, # Optional cancel button widget
    finished_callback=None, # Optional callback function (success: bool, message: str)
) -> Optional[callable]:
    """
    Manages the sequential installation of multiple extensions using ExtensionInstaller threads.

    Updates UI elements (status label, progress bar, cancel button) if provided.

    Args:
        asset_ids: A list of asset IDs to install.
        project_path: The target project directory Path.
        data_manager: The DataManager instance.
        status_label: The QLabel to display status updates.
        progress_bar: The QProgressBar to display overall progress.
        cancel_button: The QPushButton to trigger cancellation.
        finished_callback: A function to call when all installations are done or cancelled.

    Returns:
        A function that can be called to cancel the ongoing installation process, or None if no assets were provided.
    """
    logging.info(
        f"Starting extension installation logic for {len(asset_ids)} assets into {project_path}"
    )
    if not asset_ids:
        if status_label: status_label.setText("No extensions selected.")
        if progress_bar: progress_bar.setVisible(False)
        if cancel_button: cancel_button.setVisible(False)
        if finished_callback: finished_callback(True, "No extensions selected.")
        return None # Nothing to do

    ids_to_install = list(asset_ids) # Copy the list
    total = len(ids_to_install)
    installed_count = 0
    first_error_msg: Optional[str] = None
    # State dictionary to manage the current installer and cancellation flag
    state = {"current_installer": None, "cancelled": False}

    # --- Initial UI Setup ---
    if status_label: status_label.setText(f"Starting installation of {total} extensions...")
    if progress_bar:
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        progress_bar.setVisible(True)
    if cancel_button:
        cancel_button.setText("Cancel")
        cancel_button.setEnabled(True)
        cancel_button.setVisible(True)
    QApplication.processEvents() # Update UI

    # --- Nested Functions for Control Flow ---
    def run_next_installer():
        """Starts the next installer in the queue or finishes the process."""
        nonlocal installed_count, first_error_msg
        # Check if cancelled or queue is empty
        if state["cancelled"] or not ids_to_install:
            success = first_error_msg is None and not state["cancelled"]
            final_message = (
                "Installation cancelled." if state["cancelled"]
                else ("Installation complete." if success else f"Installation finished with errors: {first_error_msg}")
            )
            logging.info(f"Extension installation logic finished. Success: {success}, Msg: {final_message}")
            # Final UI updates
            if status_label: status_label.setText(final_message)
            if progress_bar: progress_bar.setVisible(False)
            if cancel_button: cancel_button.setVisible(False)
            # Call the final callback
            if finished_callback: finished_callback(success, final_message)
            state["current_installer"] = None # Clear reference
            return # End of process

        # Get next asset ID and update UI for the new step
        asset_id = ids_to_install.pop(0)
        base_progress = int(100 * installed_count / total)
        logging.debug(f"Starting installation step [{installed_count+1}/{total}] for Asset ID {asset_id}")
        if status_label: status_label.setText(f"[{installed_count+1}/{total}] Starting ID {asset_id}...")
        if progress_bar:
            progress_bar.setRange(0, 100) # Ensure range is correct
            progress_bar.setValue(base_progress)
        QApplication.processEvents() # Update UI

        # Create and connect the installer thread
        installer = ExtensionInstaller(asset_id, project_path, data_manager)
        state["current_installer"] = installer # Store current installer

        # --- Signal Handlers for the Current Installer ---
        def handle_status_update(message: str):
            if status_label and not state["cancelled"]:
                status_label.setText(f"[{installed_count+1}/{total}] ID {asset_id}: {message}")

        def handle_progress_update(percent: int):
            if progress_bar and not state["cancelled"]:
                if percent >= 0:
                    progress_bar.setRange(0, 100) # Ensure range is correct
                    # Calculate overall progress based on current step's progress
                    step_fraction = percent / 100.0
                    overall_progress = int(100 * (installed_count + step_fraction) / total)
                    progress_bar.setValue(overall_progress)
                else:
                    # Indeterminate progress
                    progress_bar.setRange(0, 0)

        def handle_installer_finished(id_finished: int, success: bool, message: str):
            nonlocal installed_count, first_error_msg
            logging.debug(f"Installation step finished for ID {id_finished}. Success: {success}")
            if state["cancelled"]:
                # If cancelled while this installer was running, just proceed to finish
                run_next_installer()
                return

            installed_count += 1
            if not success and first_error_msg is None:
                # Store the first error encountered
                first_error_msg = f"ID {id_finished}: {message}"
                logging.warning(f"Error installing ID {id_finished}: {message}. Continuing...")
            elif success:
                logging.info(f"Successfully installed ID {id_finished}.")

            # Run the next installer in the sequence
            run_next_installer()
        # --- End Signal Handlers ---

        installer.status_update.connect(handle_status_update)
        installer.progress.connect(handle_progress_update)
        installer.finished.connect(handle_installer_finished)
        installer.start() # Start the installer thread

    def cancel_installation_process():
        """Handles the cancellation request."""
        if not state["cancelled"]:
            logging.info("Cancelling multiple extension installation...")
            state["cancelled"] = True
            if status_label: status_label.setText("Cancelling...")
            if cancel_button: cancel_button.setEnabled(False) # Disable button during cancel

            # Stop the currently running installer, if any
            current_installer = state.get("current_installer")
            if current_installer and current_installer.isRunning():
                current_installer.stop()
            # The run_next_installer function will handle the final cleanup

    # --- Start the Process ---
    run_next_installer() # Start the first installer
    return cancel_installation_process # Return the cancellation function


# --- Project Synchronization Logic ---
def synchronize_projects_with_default_folder(data_manager: DataManager) -> bool:
    """
    Synchronizes the stored project list with the contents of the default projects folder.

    - Adds projects found in the folder but not in the stored list.
    - Updates names if a project in the folder has a different name than stored.
    - Removes projects from the stored list if they were previously in the default folder
      but are no longer found there.
    - Removes projects from the stored list if they were added manually (outside the
      default folder) but their path no longer exists.

    Args:
        data_manager: The DataManager instance holding the stored project data.

    Returns:
        True if any changes were made to the stored project list, False otherwise.
    """
    default_folder_str = data_manager.get_default_projects_folder()
    if not default_folder_str:
        logging.info("Sync skipped: Default projects folder is not set.")
        return False

    try:
        # Resolve the default folder path once
        default_folder_path = Path(default_folder_str).resolve()
    except Exception as e:
        logging.error(
            f"Sync failed: Default projects folder path '{default_folder_str}' is invalid: {e}"
        )
        return False

    if not default_folder_path.is_dir():
        logging.warning(
            f"Sync skipped: Default projects folder '{default_folder_path}' is not a valid directory."
        )
        return False

    logging.info(f"Starting project synchronization with folder: {default_folder_path}")

    # 1. Scan the default folder
    scanned_projects = scan_projects_folder(default_folder_path) # {name: path_str}

    # 2. Get currently stored projects
    stored_projects = data_manager.get_projects() # {name: path_str}
    updated = False

    # 3. Create maps for efficient lookup (using resolved paths as keys)
    stored_paths_map: Dict[Path, str] = {} # {resolved_path: name}
    for name, path_str in stored_projects.items():
        try:
            resolved_path = Path(path_str).resolve()
            if name in stored_paths_map.values() and stored_paths_map.get(resolved_path) != name:
                 logging.warning(f"Sync: Stored data contains duplicate path '{resolved_path}' for names '{stored_paths_map.get(resolved_path)}' and '{name}'. Check data integrity.")
            stored_paths_map[resolved_path] = name
        except Exception as e:
            logging.warning(
                f"Sync: Ignoring invalid path in stored data: '{path_str}' for project '{name}' ({e})"
            )

    scanned_paths_map: Dict[Path, str] = {} # {resolved_path: name}
    for name, path_str in scanned_projects.items():
        try:
            resolved_path = Path(path_str).resolve()
            if resolved_path in scanned_paths_map:
                 logging.warning(f"Sync: Scan found duplicate path '{resolved_path}' for names '{scanned_paths_map[resolved_path]}' and '{name}'. Using '{name}'.")
            scanned_paths_map[resolved_path] = name
        except Exception as e:
            logging.error(f"Sync: Error resolving scanned path '{path_str}' for project '{name}': {e}")

    scanned_paths_set = set(scanned_paths_map.keys())

    # 4. Add or Update projects found during scan
    for scanned_path, scanned_name in scanned_paths_map.items():
        if scanned_path in stored_paths_map:
            # Project path exists in storage. Check if the name matches.
            stored_name = stored_paths_map[scanned_path]
            if stored_name != scanned_name:
                # Name mismatch: Update the stored name to match the scanned name
                logging.info(
                    f"Sync: Updating name for project at '{scanned_path}'. '{stored_name}' -> '{scanned_name}'."
                )
                # DataManager handles saving internally
                data_manager.remove_project(stored_name) # Remove old entry
                data_manager.add_project(scanned_name, str(scanned_path)) # Add new entry
                updated = True
        else:
            # New project found in the folder that wasn't stored before.
            logging.info(
                f"Sync: Adding new project found in folder: '{scanned_name}' ({scanned_path})."
            )
            data_manager.add_project(scanned_name, str(scanned_path))
            updated = True

    # 5. Remove stale projects from storage
    projects_to_remove: List[str] = []
    for stored_path, stored_name in stored_paths_map.items():
        is_inside_default_folder = False
        try:
            # Check if the stored path is within the default folder being scanned
            # Use is_relative_to for robustness (Python 3.9+)
            if sys.version_info >= (3, 9):
                is_inside_default_folder = stored_path.is_relative_to(default_folder_path)
            else: # Fallback for older Python versions
                is_inside_default_folder = str(stored_path).startswith(str(default_folder_path))
        except Exception as e:
             # Path comparison might fail for weird paths, log but continue
             logging.warning(f"Sync: Error checking if path {stored_path} is inside {default_folder_path}: {e}")

        if is_inside_default_folder and stored_path not in scanned_paths_set:
            # Project was in the default folder but is no longer found by the scan. Remove it.
            logging.warning(
                f"Sync: Project '{stored_name}' ({stored_path}) previously in default folder, but not found in scan. Removing from list."
            )
            projects_to_remove.append(stored_name)
            updated = True
        elif not is_inside_default_folder and not stored_path.exists():
             # Project was added manually (outside default folder) but its path no longer exists. Remove it.
             logging.warning(
                 f"Sync: Manually added project '{stored_name}' path ({stored_path}) no longer exists. Removing from list."
             )
             projects_to_remove.append(stored_name)
             updated = True
        # else: Project is inside default folder and was found OR project is outside default folder and still exists -> Keep it.

    # Perform removals
    for name in projects_to_remove:
        data_manager.remove_project(name) # DataManager handles saving

    if updated:
        logging.info("Project list synchronized with default folder. Changes were made.")
    else:
        logging.info("Project list is already synchronized with default folder. No changes needed.")
    return updated
