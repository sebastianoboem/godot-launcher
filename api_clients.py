# -*- coding: utf-8 -*-
# api_clients.py

import logging
import requests
from PyQt6.QtCore import QThread, pyqtSignal

# --- API Constants ---
ASSET_LIB_API_BASE = "https://godotengine.org/asset-library/api"
GITHUB_API_RELEASES = "https://api.github.com/repos/godotengine/godot/releases"


# --- Godot Asset Library API Client ---
class ApiFetchThread(QThread):
    """
    A QThread for fetching asset data from the Godot Asset Library API asynchronously.

    Signals:
        results_fetched (dict): Emitted when asset data is successfully fetched.
                                Contains keys: 'results', 'total_items', 'total_pages', 'current_page'.
        fetch_error (str): Emitted when an error occurs during the API request.
    """
    results_fetched = pyqtSignal(dict)
    fetch_error = pyqtSignal(str)

    def __init__(
        self,
        asset_type="addon",
        query="",
        godot_version="4",
        category_id=None,
        support_levels=None,
        sort_by="updated",
        page=0,
    ):
        super().__init__()
        self.asset_type = asset_type
        self.query = query
        self.godot_version = godot_version
        self.category_id = category_id
        self.support_levels = support_levels if support_levels else {}
        self.sort_by = sort_by
        self.page = page
        self._is_running = True
        self.setObjectName(f"ApiFetchThread_{asset_type}_p{page}") # Useful for logging

    def stop(self):
        """Requests the thread to stop its operation."""
        logging.info(f"Requesting stop for {self.objectName()}")
        self._is_running = False

    def run(self):
        """Executes the API request to fetch asset data."""
        logging.info(f"Starting {self.objectName()}")
        params = {
            "type": self.asset_type,
            "filter": self.query,
            "godot_version": self.godot_version,
            "page": self.page,
            "sort": self.sort_by,
        }
        if self.category_id is not None and str(self.category_id).isdigit():
            params["category"] = int(self.category_id)
        for level, include in self.support_levels.items():
            if include:
                params[f"support[{level}]"] = 1 # Add support level filters if specified
        try:
            logging.info(f"AssetLib API Request: {ASSET_LIB_API_BASE}/asset | Params: {params}")
            headers = {"User-Agent": "GodotCustomLauncher/1.1 (Python)"} # Identify client
            response = requests.get(
                f"{ASSET_LIB_API_BASE}/asset", # Endpoint for fetching assets
                params=params,
                timeout=20,
                headers=headers,
            )
            response.raise_for_status() # Check for HTTP errors
            if not self._is_running:
                logging.info(f"{self.objectName()} stopped during request.")
                return # Exit if stop was requested
            data = response.json()
            results = data.get("result", [])
            total_items = int(data.get("total_items", 0))
            current_api_page = int(data.get("page", 0))
            page_size_api = int(data.get("page_length", 40)) # Use 40 as fallback if missing
            total_api_pages = int(data.get("pages", 0))
            logging.debug(
                f"AssetLib API Response Paging: total={total_items}, page={current_api_page}, pages(api)={data.get('pages')}, page_length(api)={page_size_api}, calculated_pages={total_api_pages}"
            )
            fetch_data = {
                "results": results if isinstance(results, list) else [],
                "total_items": total_items,
                "total_pages": total_api_pages,
                "current_page": current_api_page,
            }
            if self._is_running:
                self.results_fetched.emit(fetch_data) # Emit results if still running
        except requests.exceptions.RequestException as e:
            error_msg = f"AssetLib API Network Error: {e}"
            logging.error(error_msg, exc_info=False) # Log network errors without traceback
            if self._is_running:
                self.fetch_error.emit(error_msg)
        except Exception as e:
            error_msg = f"AssetLib API Error: {e}"
            logging.exception(error_msg) # Log other errors with traceback
            if self._is_running:
                self.fetch_error.emit(error_msg)
        finally:
            logging.info(f"{self.objectName()} finished.")


def fetch_asset_details_sync(asset_id):
    """
    Fetches detailed information for a specific asset synchronously.

    Args:
        asset_id: The ID of the asset to fetch details for.

    Returns:
        A dictionary containing the asset details, or None if an error occurred.
    """
    logging.debug(f"Requesting details for asset ID: {asset_id}")
    try:
        headers = {"User-Agent": "GodotCustomLauncher/1.1 (Python)"} # Identify client
        response = requests.get(
            f"{ASSET_LIB_API_BASE}/asset/{asset_id}", timeout=15, headers=headers
        )
        response.raise_for_status() # Check for HTTP errors
        logging.debug(f"Details received for asset ID {asset_id}.")
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Network Error fetching details for ID {asset_id}: {e}", exc_info=False)
        return None
    except Exception as e:
        logging.error(f"Error fetching details for ID {asset_id}: {e}", exc_info=False)
        return None


# --- GitHub API Client ---
class GitHubReleasesThread(QThread):
    """
    A QThread for fetching Godot Engine release data from the GitHub API asynchronously.

    Signals:
        releases_fetched (list): Emitted with a list of release dictionaries when fetched successfully.
        fetch_error (str): Emitted when an error occurs during the API request.
    """
    releases_fetched = pyqtSignal(list)
    fetch_error = pyqtSignal(str)

    def __init__(self, per_page=30):
        super().__init__()
        self.per_page = per_page
        self._is_running = True
        self.setObjectName("GitHubReleasesThread") # Useful for logging

    def stop(self):
        """Requests the thread to stop its operation."""
        logging.info(f"Requesting stop for {self.objectName()}")
        self._is_running = False

    def run(self):
        """Executes the API request to fetch GitHub release data."""
        logging.info(f"Starting {self.objectName()}")
        releases = []
        page = 1 # Currently fetches only the first page
        try:
            # TODO: Implement pagination if more than `per_page` releases are needed.
            if self._is_running:
                logging.info(f"GitHub API Request: Page {page}...")
                headers = {
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "GodotCustomLauncher/1.1 (Python)", # Identify client
                }
                params = {"per_page": self.per_page, "page": page}
                response = requests.get(
                    GITHUB_API_RELEASES, headers=headers, params=params, timeout=20
                )
                response.raise_for_status() # Check for HTTP errors
                if not self._is_running:
                    logging.info(f"{self.objectName()} stopped during request.")
                    return # Exit if stop was requested
                data = response.json()
                releases.extend(data) # Add fetched releases to the list
            if self._is_running:
                logging.info(f"Found {len(releases)} releases from GitHub.")
                self.releases_fetched.emit(releases) # Emit results if still running
        except requests.exceptions.RequestException as e:
            error_msg = f"GitHub API Network Error: {e}"
            logging.error(error_msg, exc_info=False) # Log network errors without traceback
            if self._is_running:
                self.fetch_error.emit(error_msg)
        except Exception as e:
            error_msg = f"Unexpected GitHub API Error: {e}"
            logging.exception(error_msg) # Log other errors with traceback
            if self._is_running:
                self.fetch_error.emit(error_msg)
        finally:
            logging.info(f"{self.objectName()} finished.")
