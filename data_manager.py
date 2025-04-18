# -*- coding: utf-8 -*-
# data_manager.py

import json
import logging
from pathlib import Path
import os
from typing import Any, Dict, List, Optional, Union

# --- Constants ---
CONFIG_FILE = Path("launcher_data.json")
DEFAULT_GODOT_PATH_KEY = "default_godot_path"
PROJECTS_KEY = "projects"
AUTO_INSTALL_EXT_KEY = "auto_install_extensions"
DEFAULT_PROJECTS_FOLDER_KEY = "default_projects_folder"
GODOT_VERSIONS_PATH_KEY = "godot_versions_path"
DEFAULT_GODOT_VERSIONS_DIR = Path("godot_versions")
DEFAULT_ICON_NAME = "icon.svg"  # Used in project_handler
DEFAULT_ICON_PATH_IN_LAUNCHER = (
    Path("assets") / DEFAULT_ICON_NAME
)  # Used in project_handler


class DataManager:
    """Manages loading, saving, and accessing application data."""

    def __init__(self, config_path: Path = CONFIG_FILE):
        """
        Initializes the DataManager.

        Args:
            config_path: The path to the JSON configuration file.
        """
        self.config_path = config_path
        # Assign default path string *before* loading data, as _get_default_data uses it
        # Store the *unresolved* default path string. Resolution happens only if needed.
        self._default_godot_versions_path_str = str(DEFAULT_GODOT_VERSIONS_DIR)
        self._data: Dict[str, Any] = self._load_data()
        logging.debug("DataManager initialized.")

    def _get_default_data(self) -> Dict[str, Any]:
        """Returns the default data structure."""
        return {
            PROJECTS_KEY: {},
            AUTO_INSTALL_EXT_KEY: [],
            DEFAULT_GODOT_PATH_KEY: None,
            DEFAULT_PROJECTS_FOLDER_KEY: None,
            # Default to None, indicating not configured initially
            GODOT_VERSIONS_PATH_KEY: None,
        }

    def _load_data(self) -> Dict[str, Any]:
        """Loads configuration data from the JSON file."""
        logging.debug(f"Calling _load_data() for {self.config_path}")
        default_data = self._get_default_data()

        if not self.config_path.exists():
            logging.info(f"File {self.config_path} not found. Using default data.")
            return default_data

        logging.info(f"Found configuration file: {self.config_path}")
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logging.debug(f"Data loaded: {data}")

            # Ensure main keys exist, falling back to defaults if necessary
            data.setdefault(PROJECTS_KEY, default_data[PROJECTS_KEY])
            data.setdefault(DEFAULT_GODOT_PATH_KEY, default_data[DEFAULT_GODOT_PATH_KEY])
            data.setdefault(DEFAULT_PROJECTS_FOLDER_KEY, default_data[DEFAULT_PROJECTS_FOLDER_KEY])
            # Use get() to check if the key exists, default to None if not present in JSON
            data[GODOT_VERSIONS_PATH_KEY] = data.get(GODOT_VERSIONS_PATH_KEY, None)
            data.setdefault(AUTO_INSTALL_EXT_KEY, default_data[AUTO_INSTALL_EXT_KEY]) # Ensure this key also exists

            # Clean and validate auto-install extension list (ensure they are integers)
            raw_ext_ids = data.get(AUTO_INSTALL_EXT_KEY, [])
            valid_ext_ids = []
            for id_val in raw_ext_ids:
                try:
                    valid_ext_ids.append(int(id_val))
                except (ValueError, TypeError):
                    logging.warning(f"Invalid non-integer extension ID found and removed: {id_val}")
            data[AUTO_INSTALL_EXT_KEY] = valid_ext_ids


            # Validate Godot versions path: if it exists, it must be a non-empty string.
            # If it's None or invalid type, treat it as None (not configured).
            loaded_path_value = data.get(GODOT_VERSIONS_PATH_KEY)
            if loaded_path_value is not None:
                if not isinstance(loaded_path_value, str) or not loaded_path_value.strip():
                    logging.warning(
                        f"Invalid Godot versions path found in config ('{loaded_path_value}'). "
                        f"Treating as not configured (None)."
                    )
                    data[GODOT_VERSIONS_PATH_KEY] = None # Set to None if invalid string found
            # If loaded_path_value was already None, it remains None.

            logging.debug("Finished _load_data() - success")
            return data
        except json.JSONDecodeError:
            logging.error(
                f"File {self.config_path} is corrupted. Using default data.", exc_info=False
            )
            return default_data
        except Exception:
            logging.exception(
                f"Unexpected error loading {self.config_path}. Using default data."
            )
            return default_data

    def save_data(self):
        """Saves the current configuration data to the JSON file."""
        logging.debug(f"Calling save_data() for {self.config_path}")
        try:
            # Ensure default keys exist before saving (redundant if _load_data worked, but safe)
            self._data.setdefault(PROJECTS_KEY, {})
            self._data.setdefault(AUTO_INSTALL_EXT_KEY, [])
            self._data.setdefault(DEFAULT_GODOT_PATH_KEY, None)
            self._data.setdefault(DEFAULT_PROJECTS_FOLDER_KEY, None)
            # Ensure the key exists, defaulting to None if somehow missing after load
            self._data.setdefault(GODOT_VERSIONS_PATH_KEY, None)

            # Create directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4, ensure_ascii=False)
            logging.info(f"Data successfully saved to {self.config_path}")
        except TypeError as e:
            logging.error(f"Type error during JSON preparation for saving: {e}")
            logging.error(f"Current data causing error: {self._data}")
        except Exception:
            logging.exception(f"Critical error saving data to {self.config_path}")

    # --- Accessor Methods ---

    def get_projects(self) -> Dict[str, str]:
        """Returns the dictionary of projects {name: path_string}."""
        # Ensure the key exists and is a dictionary
        projects = self._data.get(PROJECTS_KEY, {})
        if not isinstance(projects, dict):
            logging.warning(f"'{PROJECTS_KEY}' data is not a dictionary. Returning empty dict.")
            return {}
        return projects


    def get_auto_install_extensions(self) -> List[int]:
        """Returns the list of extension IDs to auto-install."""
        # Ensure the key exists and is a list
        extensions = self._data.get(AUTO_INSTALL_EXT_KEY, [])
        if not isinstance(extensions, list):
             logging.warning(f"'{AUTO_INSTALL_EXT_KEY}' data is not a list. Returning empty list.")
             return []
        # We assume _load_data already validated the contents are integers
        return extensions

    def get_godot_path(self) -> Optional[str]:
        """Returns the default Godot executable path string."""
        path = self._data.get(DEFAULT_GODOT_PATH_KEY)
        if path is not None and not isinstance(path, str):
            logging.warning(f"'{DEFAULT_GODOT_PATH_KEY}' data is not a string or None. Returning None.")
            return None
        return path

    def set_godot_path(self, path: Optional[str]):
        """Sets the default Godot executable path and saves."""
        if path is not None and not isinstance(path, str):
             logging.error(f"Attempted to set non-string default Godot path: {path}. Ignoring.")
             return
        self._data[DEFAULT_GODOT_PATH_KEY] = path
        self.save_data()

    def get_default_projects_folder(self) -> Optional[str]:
        """Returns the default projects folder path string."""
        folder = self._data.get(DEFAULT_PROJECTS_FOLDER_KEY)
        if folder is not None and not isinstance(folder, str):
             logging.warning(f"'{DEFAULT_PROJECTS_FOLDER_KEY}' data is not a string or None. Returning None.")
             return None
        return folder

    def set_default_projects_folder(self, path: Union[Path, str, None]):
        """Sets the default projects folder path and saves."""
        path_str = str(path) if path else None
        if path_str is not None and not isinstance(path_str, str): # Extra check just in case str(path) fails weirdly
             logging.error(f"Attempted to set invalid default projects folder: {path}. Ignoring.")
             return
        self._data[DEFAULT_PROJECTS_FOLDER_KEY] = path_str
        self.save_data()

    def add_project(self, name: str, path_str: Union[Path, str]):
        """Adds a project to the list and saves."""
        if not isinstance(name, str) or not name:
            logging.error(f"Attempted to add project with invalid name: {name}. Ignoring.")
            return
        if not isinstance(path_str, (str, Path)) or not path_str:
             logging.error(f"Attempted to add project '{name}' with invalid path: {path_str}. Ignoring.")
             return

        projects = self._data.setdefault(PROJECTS_KEY, {})
        if not isinstance(projects, dict): # Ensure it's a dict before adding
             logging.error(f"'{PROJECTS_KEY}' is not a dictionary. Cannot add project. Resetting.")
             projects = {}
             self._data[PROJECTS_KEY] = projects

        projects[name] = str(path_str)
        self.save_data()

    def remove_project(self, name: str) -> bool:
        """Removes a project from the list and saves. Returns True if removed."""
        projects = self._data.setdefault(PROJECTS_KEY, {})
        if not isinstance(projects, dict):
             logging.error(f"'{PROJECTS_KEY}' is not a dictionary. Cannot remove project.")
             return False

        removed = name in projects
        if removed:
            del projects[name]
            self.save_data()
        return removed

    def add_auto_install_extension(self, asset_id: Union[int, str]) -> bool:
        """Adds an asset ID to the auto-install list and saves. Returns True if added."""
        ext_list = self._data.setdefault(AUTO_INSTALL_EXT_KEY, [])
        if not isinstance(ext_list, list):
             logging.error(f"'{AUTO_INSTALL_EXT_KEY}' is not a list. Cannot add extension. Resetting.")
             ext_list = []
             self._data[AUTO_INSTALL_EXT_KEY] = ext_list

        try:
            int_asset_id = int(asset_id)
            added = int_asset_id not in ext_list
            if added:
                ext_list.append(int_asset_id)
                self.save_data()
                logging.info(f"Extension ID {int_asset_id} successfully added to auto-install list. Current list: {ext_list}")
            else:
                logging.info(f"Extension ID {int_asset_id} already in auto-install list. Current list: {ext_list}")
            return added
        except (ValueError, TypeError):
            logging.warning(f"Attempted to add invalid extension ID: {asset_id}")
            return False


    def remove_auto_install_extension(self, asset_id: Union[int, str]) -> bool:
        """Removes an asset ID from the auto-install list and saves. Returns True if removed."""
        ext_list = self._data.setdefault(AUTO_INSTALL_EXT_KEY, [])
        if not isinstance(ext_list, list):
             logging.error(f"'{AUTO_INSTALL_EXT_KEY}' is not a list. Cannot remove extension.")
             return False

        try:
            int_asset_id = int(asset_id)
            removed = int_asset_id in ext_list
            if removed:
                ext_list.remove(int_asset_id)
                self.save_data()
                logging.info(f"Extension ID {int_asset_id} successfully removed from auto-install list.")
            else:
                logging.warning(f"Extension ID {int_asset_id} not found in auto-install list. Current IDs: {ext_list}")
            return removed
        except (ValueError, TypeError):
             logging.warning(f"Attempted to remove invalid extension ID: {asset_id}")
             return False

    def get_godot_versions_path_str(self) -> Optional[str]:
        """
        Returns the configured path string for Godot versions, or None if not configured.
        Does NOT resolve the path or return a default.
        """
        path_str = self._data.get(GODOT_VERSIONS_PATH_KEY)
        # Ensure it's either None or a non-empty string
        if path_str is not None and (not isinstance(path_str, str) or not path_str.strip()):
            logging.warning(f"Invalid value found for '{GODOT_VERSIONS_PATH_KEY}': {path_str}. Returning None.")
            return None
        return path_str # Returns the string or None

    def get_resolved_godot_versions_path(self) -> Optional[Path]:
        """
        Returns the configured path for Godot versions as a RESOLVED Path object,
        or None if not configured or the path is invalid/cannot be resolved.
        """
        path_str = self.get_godot_versions_path_str()
        if not path_str:
            logging.debug("Godot versions path is not configured.")
            return None # Not configured

        try:
            # Attempt to resolve the configured path
            resolved_path = Path(path_str).resolve()
            # Optional: Add check if resolved_path.is_dir() if you only want directories
            # if not resolved_path.is_dir():
            #     logging.warning(f"Resolved Godot versions path '{resolved_path}' is not a directory. Returning None.")
            #     return None
            return resolved_path
        except Exception as e:
            logging.error(
                f"Error resolving configured Godot versions path '{path_str}': {e}. Returning None.",
                exc_info=False, # Keep log cleaner unless debugging resolution issues
            )
            return None # Path is configured but invalid or resolution failed

    def set_godot_versions_path(self, path: Union[Path, str, None]):
        """Sets and saves the path string for Godot versions. Saves None if path is None or empty."""
        logging.debug(f"Calling set_godot_versions_path with input: {path}")
        path_to_save: Optional[str] = None

        if path:
            path_str_candidate = str(path).strip()
            if isinstance(path_str_candidate, str) and path_str_candidate:
                 path_to_save = path_str_candidate
                 logging.info(f"Godot versions path will be saved as: '{path_to_save}'")
            else:
                 # Treat invalid input like empty input -> None
                 logging.warning(f"Attempted to set invalid Godot versions path: {path}. Saving as None.")
                 path_to_save = None
        else:
            # Path is None or empty string
            logging.info("Godot versions path explicitly set to None (not configured).")
            path_to_save = None

        # Save the string or None to the internal dictionary
        self._data[GODOT_VERSIONS_PATH_KEY] = path_to_save
        self.save_data() # Save changes to JSON

    def get_all_data(self) -> Dict[str, Any]:
        """Returns a copy of all configuration data."""
        return self._data.copy()

    def get(self, key: str, default: Any = None) -> Any:
        """
        Gets a value from the data dictionary with a default fallback.
        
        Args:
            key: The key to look up in the config data
            default: Value to return if the key doesn't exist
            
        Returns:
            The value from config or the default if not found
        """
        return self._data.get(key, default)

# --- Deprecated Functions (kept for temporary compatibility, should be removed) ---
# It is recommended to update the code to use an instance of DataManager directly.

_global_data_manager_instance: Optional[DataManager] = None

def _get_global_instance() -> DataManager:
    """Helper function to get/create a global instance (for deprecated functions)."""
    global _global_data_manager_instance
    if _global_data_manager_instance is None:
        logging.warning("Implicitly creating global DataManager instance for deprecated functions.")
        _global_data_manager_instance = DataManager()
    return _global_data_manager_instance

def load_data() -> Dict[str, Any]:
    """DEPRECATED: Use DataManager().get_all_data() or specific getter methods."""
    logging.warning("Called deprecated function load_data(). Use DataManager instance.")
    # Always load fresh data via the instance when this is called
    instance = _get_global_instance()
    instance._data = instance._load_data() # Reload data
    return instance.get_all_data()

def save_data(data: Dict[str, Any]):
    """DEPRECATED: Use DataManager().save_data() or specific setter methods which save automatically."""
    logging.warning("Called deprecated function save_data(). Use DataManager instance.")
    instance = _get_global_instance()
    # Overwrites the internal data of the global instance and saves
    instance._data = data # Warning: direct overwrite!
    instance.save_data()

def get_projects(data: Dict[str, Any]) -> Dict[str, str]:
    """DEPRECATED: Use DataManager().get_projects()."""
    logging.warning("Called deprecated function get_projects(). Use DataManager instance.")
    # Operates on the passed 'data' dictionary (potentially outdated), not the instance's current data
    return data.get(PROJECTS_KEY, {})

# --- Add similar warnings and potentially redirect to instance methods for other deprecated functions ---
# Note: For minimal initial disruption, many deprecated functions below still operate on the
# passed 'data' dictionary. A full refactor would update all call sites to use a DataManager instance.
# Functions that *need* the instance's logic (like path resolution or saving) are redirected.

def get_godot_versions_path_str(data: Dict[str, Any]) -> Optional[str]:
    """DEPRECATED: Use DataManager().get_godot_versions_path_str()."""
    logging.warning("Called deprecated function get_godot_versions_path_str(). Use DataManager instance.")
    return _get_global_instance().get_godot_versions_path_str()

def get_resolved_godot_versions_path(data: Dict[str, Any]) -> Optional[Path]:
    """DEPRECATED: Use DataManager().get_resolved_godot_versions_path()."""
    logging.warning("Called deprecated function get_resolved_godot_versions_path(). Use DataManager instance.")
    return _get_global_instance().get_resolved_godot_versions_path()

def set_godot_versions_path(data: Dict[str, Any], path: Union[Path, str, None]):
     """DEPRECATED: Use DataManager().set_godot_versions_path()."""
     logging.warning("Called deprecated function set_godot_versions_path(). Use DataManager instance.")
     instance = _get_global_instance()
     instance.set_godot_versions_path(path) # Use instance to save correctly

def get_auto_install_extensions(data: Dict[str, Any]) -> List[int]:
    """DEPRECATED: Use DataManager().get_auto_install_extensions()."""
    logging.warning("Called deprecated function get_auto_install_extensions(). Use DataManager instance.")
    return data.get(AUTO_INSTALL_EXT_KEY, [])

def get_godot_path(data: Dict[str, Any]) -> Optional[str]:
    """DEPRECATED: Use DataManager().get_godot_path()."""
    logging.warning("Called deprecated function get_godot_path(). Use DataManager instance.")
    return data.get(DEFAULT_GODOT_PATH_KEY)

def set_godot_path(data: Dict[str, Any], path: Optional[str]):
    """DEPRECATED: Use DataManager().set_godot_path()."""
    logging.warning("Called deprecated function set_godot_path(). Use DataManager instance.")
    instance = _get_global_instance()
    instance.set_godot_path(path)

def get_default_projects_folder(data: Dict[str, Any]) -> Optional[str]:
    """DEPRECATED: Use DataManager().get_default_projects_folder()."""
    logging.warning("Called deprecated function get_default_projects_folder(). Use DataManager instance.")
    return data.get(DEFAULT_PROJECTS_FOLDER_KEY)

def set_default_projects_folder(data: Dict[str, Any], path: Union[Path, str, None]):
    """DEPRECATED: Use DataManager().set_default_projects_folder()."""
    logging.warning("Called deprecated function set_default_projects_folder(). Use DataManager instance.")
    instance = _get_global_instance()
    instance.set_default_projects_folder(path)

def add_project(data: Dict[str, Any], name: str, path_str: Union[Path, str]):
    """DEPRECATED: Use DataManager().add_project()."""
    logging.warning("Called deprecated function add_project(). Use DataManager instance.")
    instance = _get_global_instance()
    instance.add_project(name, path_str)

def remove_project(data: Dict[str, Any], name: str) -> bool:
    """DEPRECATED: Use DataManager().remove_project()."""
    logging.warning("Called deprecated function remove_project(). Use DataManager instance.")
    instance = _get_global_instance()
    return instance.remove_project(name) # Return boolean result

def add_auto_install_extension(data: Dict[str, Any], asset_id: Union[int, str]) -> bool:
    """DEPRECATED: Use DataManager().add_auto_install_extension()."""
    logging.warning("Called deprecated function add_auto_install_extension(). Use DataManager instance.")
    instance = _get_global_instance()
    return instance.add_auto_install_extension(asset_id) # Return boolean result

def remove_auto_install_extension(data: Dict[str, Any], asset_id: Union[int, str]) -> bool:
    """DEPRECATED: Use DataManager().remove_auto_install_extension()."""
    logging.warning("Called deprecated function remove_auto_install_extension(). Use DataManager instance.")
    instance = _get_global_instance()
    return instance.remove_auto_install_extension(asset_id) # Return boolean result
