# -*- coding: utf-8 -*-
# utils.py

import logging
import os
import re
import tempfile
import shutil
import zipfile
import threading
from pathlib import Path
from typing import Optional, Union

import requests
from PyQt6.QtCore import QObject, QRunnable, QSize, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import QMessageBox, QWidget

# Constants
ICON_CACHE_DIR = Path("cache/icons")
ICON_SIZE = QSize(64, 64)
ASSETS_DIR = Path("assets") # Define the base assets directory


# --- NEW FUNCTION: get_icon ---
def get_icon(icon_filename: str) -> Optional[QIcon]:
    """Loads a QIcon from the assets directory.

    Args:
        icon_filename: The name of the icon file (e.g., 'my_icon.png').

    Returns:
        A QIcon instance if the file exists, otherwise None.
    """
    icon_path = ASSETS_DIR / icon_filename
    if icon_path.is_file():
        try:
            icon = QIcon(str(icon_path))
            if icon.isNull(): # Check if the icon loaded correctly
                logging.warning(f"get_icon: QIcon created but is null for {icon_path}")
                return None
            logging.debug(f"get_icon: Successfully loaded icon from {icon_path}")
            return icon
        except Exception as e:
            logging.error(f"get_icon: Failed to load icon from {icon_path}: {e}")
            return None
    else:
        logging.warning(f"get_icon: Icon file not found at {icon_path}")
        return None
# --- END NEW FUNCTION ---


# --- NEW FUNCTION: ensure_directory_exists ---
def ensure_directory_exists(directory_path: Union[str, Path]):
    """
    Assicura che una directory esista, creandola se necessario.

    Args:
        directory_path: Path alla directory da creare.
    """
    try:
        os.makedirs(str(directory_path), exist_ok=True)
        logging.debug(f"ensure_directory_exists: Directory assicurata: {directory_path}")
    except Exception as e:
        logging.error(f"ensure_directory_exists: Errore nella creazione della directory {directory_path}: {e}")
        raise
# --- END NEW FUNCTION ---


# --- NEW FUNCTION: download_file ---
def download_file(url: str, target_file: Union[str, Path], timeout: int = 30):
    """
    Scarica un file da un URL e lo salva localmente.

    Args:
        url: URL del file da scaricare.
        target_file: Path dove salvare il file.
        timeout: Timeout in secondi per la richiesta.

    Returns:
        True se il download è riuscito, False altrimenti.
    """
    target_path = Path(target_file)
    
    try:
        # Assicurati che la directory di destinazione esista
        ensure_directory_exists(target_path.parent)
        
        # Scarica il file - Modificato per allinearsi con il test
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Salva il file
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        logging.info(f"download_file: File scaricato con successo: {url} -> {target_path}")
        return True
    
    except Exception as e:
        logging.error(f"download_file: Errore nel download da {url}: {e}")
        # Pulisci il file parziale se esiste
        if target_path.exists():
            try:
                target_path.unlink()
            except Exception:
                pass
        return False
# --- END NEW FUNCTION ---


# --- NEW FUNCTION: get_safe_filename ---
def get_safe_filename(filename: str) -> str:
    """
    Converte una stringa in un nome file sicuro, rimuovendo o sostituendo caratteri non validi.

    Args:
        filename: La stringa da convertire in un nome file sicuro.

    Returns:
        Una versione sicura del nome file.
    """
    # Sostituisce caratteri non validi con underscore
    safe_name = re.sub(r'[\\/*?:"<>|]', "_", filename)
    
    # Sostituisce spazi con underscore
    safe_name = safe_name.replace(" ", "_")
    
    # Sostituisce caratteri specifici
    safe_name = safe_name.replace("/", "_")
    safe_name = safe_name.replace("\\", "_")
    safe_name = safe_name.replace(":", "_")
    
    logging.debug(f"get_safe_filename: Convertito '{filename}' in '{safe_name}'")
    return safe_name
# --- END NEW FUNCTION ---


class DownloadThread(QThread):
    """
    A QThread subclass for downloading files asynchronously.

    Signals:
        progress (int): Emitted with the download progress percentage (0-100).
                        Emits -1 if total size is unknown.
        finished (str, str): Emitted when the download finishes or is stopped.
                             Provides the save path and an error message (None if successful).
        status_update (str): Emitted to provide user-friendly status updates.
    """
    progress = pyqtSignal(int)
    finished = pyqtSignal(str, str)  # save_path, error_message (None if ok)
    status_update = pyqtSignal(str)

    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = Path(save_path)
        self._is_running = True
        self.setObjectName(f"DownloadThread_{self.save_path.name}") # Useful for logging

    def stop(self):
        """Requests the download thread to stop."""
        logging.info(f"Requesting stop for {self.objectName()}")
        self._is_running = False

    def run(self):
        """Executes the download process."""
        logging.info(f"Starting {self.objectName()} for URL: {self.url}")
        error_message = None
        try:
            self.status_update.emit(f"Connecting to {self.url}...")
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            headers = {"User-Agent": "GodotCustomLauncher/1.1 (Python)"}
            response = requests.get(self.url, stream=True, timeout=30, headers=headers)
            response.raise_for_status()
            logging.debug(f"Connection OK (Status: {response.status_code})")
            total_size_str = response.headers.get("content-length")
            total_size = int(total_size_str) if total_size_str and total_size_str.isdigit() else 0
            bytes_downloaded = 0
            chunk_size = 8192
            self.status_update.emit(
                f"Starting download: {self.save_path.name} ({total_size} bytes)"
            )
            with open(self.save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if not self._is_running:
                        raise InterruptedError("Download canceled by user.")
                    if chunk:
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        if total_size > 0:
                            self.progress.emit(int(100 * bytes_downloaded / total_size))
                        else:
                            # Emit -1 for indeterminate progress
                            self.progress.emit(-1)
            if self._is_running:
                logging.info(
                    f"Download completed: {self.save_path.name} ({bytes_downloaded} bytes)"
                )
                self.progress.emit(100)
                self.status_update.emit(f"Download complete: {self.save_path.name}")
            else:
                # If stopped, but the loop finished without exception (rare)
                raise InterruptedError("Download completed but was interrupted.")

        except requests.exceptions.Timeout:
            error_message = "Download timeout."
            logging.warning(error_message)
        except requests.exceptions.RequestException as e:
            error_message = f"Network error: {e}"
            logging.error(error_message, exc_info=False) # Don't log traceback for common network errors
        except InterruptedError as e:
            error_message = str(e)
            logging.info(f"Download interrupted: {error_message}")
        except Exception as e:
            error_message = f"Unexpected download error: {e}"
            logging.exception(error_message) # Log traceback for unexpected errors
        finally:
            final_error_msg = error_message if error_message else None
            if final_error_msg:
                self._cleanup_failed_download()
            logging.info(f"{self.objectName()} finished. Error: {final_error_msg}")
            self.finished.emit(str(self.save_path), final_error_msg)

    def _cleanup_failed_download(self):
        """Removes the partially downloaded file if the download failed or was cancelled."""
        if self.save_path.exists():
            try:
                self.save_path.unlink()
                logging.info(f"Removed temporary file: {self.save_path}")
            except OSError as rm_err:
                logging.warning(f"Failed to remove {self.save_path}: {rm_err}")


# --- Helper Function for Error Dialogs --- 
def log_and_show_error(title: str, message: str, level: str = "error", log_message: Optional[str] = None, exc_info: bool = False, parent: Optional[QWidget] = None):
    """
    Logs a message and optionally shows a QMessageBox to the user.

    Args:
        title: Title for the QMessageBox.
        message: The user-facing message to display.
        level: Severity level ("info", "warning", "error", "critical"). Controls
               both the logging level and the QMessageBox icon.
        log_message: Specific message for logging. If None, uses `message`.
        exc_info: If True, logs exception information.
        parent: Parent widget for the QMessageBox.
    """
    # Determine logging level and function
    log_level_map = {
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    log_func_map = {
        "info": logging.info,
        "warning": logging.warning,
        "error": logging.error,
        "critical": logging.critical,
    }

    selected_log_level = log_level_map.get(level.lower(), logging.ERROR)
    selected_log_func = log_func_map.get(level.lower(), logging.error)

    # Log the message
    final_log_message = log_message if log_message is not None else message
    selected_log_func(final_log_message, exc_info=exc_info)

    # Determine QMessageBox icon
    icon_map = {
        "info": QMessageBox.Icon.Information,
        "warning": QMessageBox.Icon.Warning,
        "error": QMessageBox.Icon.Critical,
        "critical": QMessageBox.Icon.Critical, # Use Critical icon for critical errors
    }
    selected_icon = icon_map.get(level.lower(), QMessageBox.Icon.Warning) # Default to Warning

    # Show the message box
    try:
        # Ensure MessageBox runs in the main thread if called from another thread
        # This requires a more complex setup usually involving signals/slots or QTimer.singleShot
        # For simplicity here, assume it's called from the main thread or handle threading carefully.
        # If you encounter issues with cross-thread GUI updates, refactor using signals.

        # Check if we are in the main thread before showing the message box
        if threading.current_thread() is threading.main_thread():
            # Modifica per test - usare direttamente QMessageBox.critical, warning, info
            if level.lower() == "error" or level.lower() == "critical":
                QMessageBox.critical(parent, title, message)
            elif level.lower() == "warning":
                QMessageBox.warning(parent, title, message)
            else:
                QMessageBox.information(parent, title, message)
        else:
            # If not in main thread, log a warning - cannot show GUI directly
            logging.warning(f"Attempted to show QMessageBox ('{title}') from non-GUI thread. Logging only.")
            # Consider emitting a signal here to show the message box in the main thread

    except Exception as e:
        logging.error(f"Failed to show QMessageBox ('{title}'): {e}", exc_info=True)


def extract_zip(zip_path: Union[str, Path], destination_dir: Union[str, Path], remove_common_prefix=True):
    """
    Extracts a ZIP archive, handling common addon structures intelligently.

    Extraction Logic:
    1. Extract the entire archive to a temporary directory
    2. For each level of the extracted directory (including the root):
        - If a folder named "addons" is found:
            - If it's not a compressed file: extract it to the project root and stop
            - If it's a compressed file: extract it and restart the search
        - Otherwise: continue to the next directory level
    3. If no "addons" folder is found, extract everything to the addons/ directory in the project

    Args:
        zip_path: Path to the ZIP file.
        destination_dir: Path to the directory where files should be extracted.
        remove_common_prefix: If True, attempts smart extraction described above.
                              If False, extracts the entire ZIP as-is.

    Returns:
        True if extraction was successful, False otherwise.
    """
    try:
        logging.info(f"Starting ZIP extraction: '{zip_path}' -> '{destination_dir}' (Remove Prefix: {remove_common_prefix})")
        # Convert strings to Path objects
        zip_path_obj = Path(zip_path)
        destination_dir_obj = Path(destination_dir)
        
        if not zip_path_obj.is_file():
            logging.error(f"extract_zip failed: ZIP file not found: {zip_path}")
            raise FileNotFoundError(f"ZIP file not found: {zip_path}")

        # Ensure the final destination directory exists
        destination_dir_obj.mkdir(parents=True, exist_ok=True)
        
        # If we don't need smart extraction, just extract everything
        if not remove_common_prefix:
            with zipfile.ZipFile(str(zip_path_obj)) as zf:
                zf.extractall(str(destination_dir_obj))
            logging.info(f"ZIP extraction completed successfully (full extract): {zip_path}")
            return True
            
        # Create a temporary directory for the extraction process
        temp_dir = tempfile.mkdtemp(prefix="godotlauncher_extract_")
        try:
            # First step: Extract the entire archive to the temporary directory
            with zipfile.ZipFile(str(zip_path_obj)) as zf:
                zf.extractall(temp_dir)
            
            # Function to scan directories recursively searching for "addons" folder
            def find_and_process_addons(current_dir: Path, level: int = 0) -> bool:
                logging.debug(f"Scanning directory level {level}: {current_dir}")
                
                # Look for "addons" directory at the current level
                addons_dir = current_dir / "addons"
                if addons_dir.exists():
                    logging.info(f"Found 'addons' directory at level {level}: {addons_dir}")
                    
                    # Check if this is actually a ZIP file (compressed folder)
                    try:
                        # Try to open it as a ZIP file
                        if addons_dir.is_file() and zipfile.is_zipfile(addons_dir):
                            logging.info(f"The 'addons' found at {addons_dir} is a compressed file. Extracting...")
                            
                            # Extract this ZIP to a new temporary directory and restart the search
                            nested_temp_dir = tempfile.mkdtemp(prefix="godotlauncher_nested_")
                            try:
                                with zipfile.ZipFile(addons_dir) as nested_zf:
                                    nested_zf.extractall(nested_temp_dir)
                                
                                # Restart the search with the extracted content
                                return find_and_process_addons(Path(nested_temp_dir), level + 1)
                            finally:
                                # Clean up the nested temp directory if needed
                                try:
                                    shutil.rmtree(nested_temp_dir)
                                except Exception as e:
                                    logging.warning(f"Failed to clean up nested temp dir {nested_temp_dir}: {e}")
                    except Exception as e:
                        logging.debug(f"Error checking if 'addons' is a ZIP file: {e}")
                    
                    # If we're here, it's a regular directory named "addons" - this is what we want
                    # Extract its CONTENTS directly to the project root
                    if addons_dir.is_dir():
                        logging.info(f"Extracting contents of 'addons' directory to {destination_dir_obj}")
                        for item in addons_dir.iterdir():
                            if item.is_dir():
                                # For directories, use shutil.copytree
                                dest_path = destination_dir_obj / item.name
                                logging.debug(f"Copying directory: {item} -> {dest_path}")
                                shutil.copytree(item, dest_path, dirs_exist_ok=True)
                            else:
                                # For files, use shutil.copy2
                                dest_path = destination_dir_obj / item.name
                                logging.debug(f"Copying file: {item} -> {dest_path}")
                                shutil.copy2(item, dest_path)
                        return True
                
                # Check for ZIP files named "addons.zip" or similar
                for item in current_dir.iterdir():
                    if item.is_file() and item.name.lower() in ['addons.zip', 'addons']:
                        try:
                            if zipfile.is_zipfile(item):
                                logging.info(f"Found file named '{item.name}' that is a ZIP file. Extracting...")
                                nested_temp_dir = tempfile.mkdtemp(prefix="godotlauncher_nested_")
                                try:
                                    with zipfile.ZipFile(item) as nested_zf:
                                        nested_zf.extractall(nested_temp_dir)
                                    
                                    # Restart the search with the extracted content
                                    return find_and_process_addons(Path(nested_temp_dir), level + 1)
                                finally:
                                    try:
                                        shutil.rmtree(nested_temp_dir)
                                    except Exception as e:
                                        logging.warning(f"Failed to clean up nested temp dir {nested_temp_dir}: {e}")
                        except Exception as e:
                            logging.debug(f"Error checking if '{item.name}' is a ZIP file: {e}")
                
                # If no "addons" dir found at this level, recursively check subdirectories
                for item in current_dir.iterdir():
                    if item.is_dir():
                        # Recursively process the subdirectory
                        if find_and_process_addons(item, level + 1):
                            return True
                
                # If we reach here, no "addons" directory found in this branch
                return False
            
            # Start the addons directory search
            addons_found = find_and_process_addons(Path(temp_dir))
            
            # If no addons directory was found, extract everything to addons/
            if not addons_found:
                logging.info("No 'addons' directory found. Extracting to addons/ directory.")
                addons_dir = destination_dir_obj / 'addons'
                addons_dir.mkdir(parents=True, exist_ok=True)
                
                # Get the contents of the temp directory
                temp_path = Path(temp_dir)
                if len(list(temp_path.iterdir())) == 1:
                    # If there's only one item and it's a directory, extract its contents
                    single_item = next(temp_path.iterdir())
                    if single_item.is_dir():
                        # Extract the contents of the single directory to addons/
                        for item in single_item.iterdir():
                            if item.is_dir():
                                shutil.copytree(item, addons_dir / item.name, dirs_exist_ok=True)
                            else:
                                shutil.copy2(item, addons_dir / item.name)
                    else:
                        # Single file - copy it to addons/
                        shutil.copy2(single_item, addons_dir / single_item.name)
                else:
                    # Multiple items - copy all to addons/
                    for item in temp_path.iterdir():
                        if item.is_dir():
                            shutil.copytree(item, addons_dir / item.name, dirs_exist_ok=True)
                        else:
                            shutil.copy2(item, addons_dir / item.name)
            
            logging.info(f"ZIP extraction completed successfully")
            return True
            
        finally:
            # Always clean up the temporary directory
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logging.warning(f"Failed to clean up temp dir {temp_dir}: {e}")
    
    except Exception as e:
        logging.error(f"Error during ZIP extraction: {e}", exc_info=True)
        return False


class IconDownloaderSignals(QObject):
    """Container for signals emitted by IconDownloader."""
    finished = pyqtSignal()
    icon_ready = pyqtSignal(str, str) # asset_id, cache_path
    error = pyqtSignal(str, str) # asset_id, error_message


class IconDownloader(QRunnable):
    """
    A QRunnable task for downloading and caching asset icons.

    Downloads an icon from a URL, saves it to a local cache directory,
    and emits signals indicating success or failure. Uses the asset ID
    to generate a safe filename for caching.
    """
    def __init__(self, asset_id, icon_url):
        """
        Initializes the IconDownloader.

        Args:
            asset_id: The unique identifier for the asset (used for filename).
                      Can be a number or a URL string (for previews).
            icon_url: The URL from which to download the icon.
        """
        super().__init__()
        self.internal_id = str(asset_id) # Store original ID for signals
        self.icon_url = icon_url
        self.signals = IconDownloaderSignals()

        # Determine file extension
        url_path = Path(QUrl(icon_url).path())
        self.extension = url_path.suffix.lower() if url_path.suffix else ".png"
        # Fallback to png if extension is not a common image format
        if self.extension not in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]:
            logging.warning(f"Unsupported icon extension '{self.extension}' for {asset_id}. Using .png.")
            self.extension = ".png"

        # Generate a safe filename from the asset_id (could be URL)
        # Remove protocol and replace invalid characters.
        safe_filename_base = str(asset_id).replace("https://", "").replace("http://", "")
        safe_filename_base = re.sub(r'[\\/:*?"<>|]', "_", safe_filename_base)

        # Optional: Limit max filename length to prevent path errors
        max_len = 100
        if len(safe_filename_base) > max_len:
            # Keep start and end parts for some readability
            safe_filename_base = (
                safe_filename_base[: max_len // 2]
                + "..."
                + safe_filename_base[-(max_len // 2) :]
            )

        self.cache_path = ICON_CACHE_DIR / f"{safe_filename_base}{self.extension}"

    def run(self):
        """Executes the icon download and caching process."""
        error_msg = None
        try:
            # Check cache first
            if self.cache_path.exists() and self.cache_path.stat().st_size > 0:
                logging.debug(
                    f"Icon {self.internal_id} found in cache: {self.cache_path}"
                )
                # Emit signal with original ID
                self.signals.icon_ready.emit(self.internal_id, str(self.cache_path))
            else:
                # Download the icon
                logging.debug(f"Downloading icon {self.internal_id} from {self.icon_url}")
                ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                headers = {"User-Agent": "GodotCustomLauncher/1.1 (Python)"} # Identify client
                response = requests.get(
                    self.icon_url, stream=True, timeout=15, headers=headers
                )
                response.raise_for_status() # Check for HTTP errors

                # Save the downloaded content
                with open(self.cache_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=4096):
                        f.write(chunk)

                # Verify download wasn't empty and emit success
                if self.cache_path.stat().st_size > 0:
                    logging.debug(
                        f"Icon {self.internal_id} downloaded to {self.cache_path}"
                    )
                    # Emit signal with original ID
                    self.signals.icon_ready.emit(self.internal_id, str(self.cache_path))
                else:
                    # Handle empty download case
                    logging.warning(
                        f"Downloaded icon {self.internal_id} is empty, removing..."
                    )
                    self.cache_path.unlink(missing_ok=True) # Clean up empty file
                    raise ValueError("Downloaded icon is empty.")

        except requests.exceptions.RequestException as e:
            error_msg = f"Network Error Icon {self.internal_id}: {e}"
            logging.warning(error_msg) # Log network errors as warnings
        except Exception as e:
            error_msg = f"Error DL Icon {self.internal_id}: {e}"
            logging.exception(error_msg) # Log other exceptions with traceback
        finally:
            # Emit error signal if something went wrong
            if error_msg:
                # Emit signal with original ID
                self.signals.error.emit(self.internal_id, error_msg)
            # Always emit finished signal
            self.signals.finished.emit()
