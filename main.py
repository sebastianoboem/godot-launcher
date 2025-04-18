# -*- coding: utf-8 -*-
# main.py (Main Entry Point - v1.2 - Online Icon)

import logging
import os
import platform
import sys
import traceback
from pathlib import Path

# Import QApplication and QMessageBox first for error fallback
from PyQt6.QtWidgets import QApplication

# Add the project root directory to sys.path
# This allows absolute imports like 'from validators import ...' from submodules like 'gui'
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --- Debug Prints ---
print(f"DEBUG: Current Working Directory: {os.getcwd()}")
print(f"DEBUG: Project Root added to sys.path: {project_root}")
print(f"DEBUG: sys.path includes:\n{sys.path}")
# --- End Debug Prints ---

# Import local modules AFTER setting up logging
try:
    # --- Logging Setup ---
    import logging.handlers # Import handler for rotation
    # Setup logging BEFORE importing other local modules that might log
    log_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - [%(threadName)s] %(filename)s:%(lineno)d - %(message)s"
    )
    # File handler (overwrites log on each start)
    log_handler = logging.FileHandler("launcher.log", mode="w", encoding="utf-8")
    log_handler.setFormatter(log_formatter)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG) # Log everything to file

    # Remove any preconfigured handlers (useful in some environments)
    # for handler in logger.handlers[:]:
    #    logger.removeHandler(handler)

    # File handler with rotation
    log_file = "launcher.log"
    max_bytes = 1 * 1024 * 1024 # 1 MB
    backup_count = 5
    rotating_handler = logging.handlers.RotatingFileHandler(
        log_file, mode='a', maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8'
    )
    rotating_handler.setFormatter(log_formatter)
    rotating_handler.setLevel(logging.DEBUG) # Log everything to file
    logger.addHandler(rotating_handler)

    # Console handler (less verbose)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    logging.info("++++ Launcher Application Started (PID: %d) ++++", os.getpid())
    logging.info(f"Python Version: {sys.version}")
    logging.info(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")
    # --- End Logging Setup ---

    # Now import other local modules
    from data_manager import DataManager # Use the DataManager class
    from gui.main_window import MainWindow
    from project_handler import synchronize_projects_with_default_folder # Keep for now, needs update
    from utils import ICON_CACHE_DIR, log_and_show_error

except ImportError as e:
    # Handle missing critical dependencies (like PyQt6) before logging is fully set up
    print(f"Critical Import Error (likely PyQt6 or requests missing): {e}")
    print("Please install dependencies: pip install PyQt6 requests")
    # Attempt to show a minimal graphical error if QApplication is importable
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        app = QApplication([]) # Minimal app to show the box
        QMessageBox.critical(
            None, "Missing Dependencies",
            f"Critical import error: {e}\n\nPlease install required libraries (e.g., 'pip install PyQt6 requests')."
        )
    except:
        pass # Ignore if UI can't be shown
    sys.exit(1)
except Exception as e:
    # Handle other potential errors during initial imports
    print(f"Critical error during initial imports: {e}")
    # Attempt to log, but might fail if logging setup itself failed
    try:
        logging.critical("Critical error during initial imports!", exc_info=True)
    except:
        pass # Ignore logging errors during critical failure
    # Attempt to show a minimal graphical error
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        app = QApplication([]) # Minimal app to show the box
        QMessageBox.critical(
            None, "Initialization Error",
            f"A critical error occurred during startup: {e}\n\nCheck console output for details."
        )
    except:
        pass # Ignore if UI can't be shown
    sys.exit(1)


def main():
    """Main application function."""
    main_window = None # Initialize to None for the except block
    try:
        # Create necessary directories (cache, temporary download folders)
        logging.debug("Creating necessary directories (cache, temp)...")
        # Removed creation of 'assets' folder as it should exist or be handled differently
        # Removed creation of temp download folders (extension, template, godot) at startup
        ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True) # Cache for asset icons still needed

        # Create DataManager instance (loads data internally)
        logging.debug("Creating DataManager instance...")
        data_manager = DataManager()

        # Removed ensuring Godot versions directory exists at startup.
        # This will be checked/created only when a download is requested.

        # Removed placeholder icon check/creation logic

        # Synchronize projects on startup if a default folder is configured
        # Pass the DataManager instance directly
        if data_manager.get_default_projects_folder():
            logging.info("Synchronizing projects on startup...")
            try:
                synchronize_projects_with_default_folder(data_manager) # Pass instance
            except Exception as sync_err:
                # Use the new function to log and show the error (not critical)
                log_and_show_error(
                    title="Sync Error",
                    message=f"Could not synchronize projects on startup.\nError: {sync_err}",
                    level="warning", # Was warning
                    parent=None # No main window yet
                )

        # Create and start the Qt application
        logging.debug("Creating QApplication...")
        app = QApplication(sys.argv)
        app.setStyle("Fusion") # Optional: Set application style

        logging.debug("Creating MainWindow...")
        # Pass the DataManager instance to the MainWindow
        main_window = MainWindow(data_manager)
        logging.debug("Showing MainWindow...")
        main_window.show()

        logging.info("Starting QApplication event loop...")
        exit_code = app.exec()
        logging.info(f"QApplication finished with exit code: {exit_code}")
        sys.exit(exit_code)

    except Exception as e:
        # Catch any unhandled exceptions in the main function
        # Logging already happened in log_and_show_error
        log_and_show_error(
            title="Unexpected Critical Error",
            message=f"A fatal error occurred:\n{e}\n\nPlease check 'launcher.log' for details.",
            level="critical",
            exc_info=True, # Pass the exception for detailed logging
            parent=main_window # Pass the main window if it exists
        )
        # Fallback to console print if UI failed before main_window creation or if log_and_show_error fails
        if not main_window:
            print(f"CRITICAL UNHANDLED ERROR (UI likely unavailable): {e}")
            print(traceback.format_exc())
        sys.exit(1) # Exit with error code


if __name__ == "__main__":
    # Entry point of the application
    main()
