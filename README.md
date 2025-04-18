# Godot Launcher

A desktop application built with Python that simplifies the Godot Engine development environment management.

## Overview

Godot Launcher provides a centralized interface for managing Godot projects, engine versions, extensions, and templates. It streamlines the workflow for Godot developers by offering an efficient way to organize and launch projects, download different versions of the engine, and manage extensions and templates.

## Features

- **Project Management**
  - Create new projects
  - Import existing projects

- **Godot Engine Version Management**
  - Download and install multiple Godot versions

- **Extensions Management**
  - Browse available extensions from Godot Asset Library
  - Multi-project extension installation

- **Templates Management**
  - Browse and download project templates
  - Use templates when creating new projects

- **Settings and Configuration**
  - Customizable application settings
  - Cache management with cleanup options
  - Log file management

## System Requirements

- **Operating System**: 
  - Windows 
  - Linux (can't be testes)
  - MacOS (in the roadmap)
- **Python**: 3.8 or higher
- **Dependencies**: PyQt6, Requests

## Installation

### Release

Get the [Latest Release](https://github.com/sebastianoboem/godot-launcher/releases/latest)
  - Your antivirus may detect the **no console** version as false positive due to the flag *console=False* used during build, but they are identical and safe.

### Manual

1. Clone the repository:
   ```
   git clone https://github.com/sebastianoboem/godot-launcher.git
   cd GodotLauncher
   ```

2. Create and activate a virtual environment (recommended):
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Run the application:
   ```
   python main.py
   ```

## Usage

### Settings
- Set up **Manal Godot Path** and press **Validate** (optional).
  - This is the fallback executable to use when no **Installed Version** is found.
- Set up **Godot Downloaded Version Folder**.
  - This is the forder where the launcher can download new engine versions.
- Choose an avaiable online version from **Fetched Online Versions** for the Download.
- Press **Download Selected Version**.
- Choose **Installed Versions** downloaded before.
- Press OK.

### Projects Tab
  - Set up **Default Projects Folder** Path an press **Save Path** .
    - This is where projects will be created.
    - Program will automatically scan for existing projects.

### Extensions Management
- Browse and search for extensions in the Extensions tab.
- Select it using checkox near the icon to save as default for next projects.
- You can install selected extensions in the already existing projects.

### Cache Management
- Clean the application cache through the Settings dialog to free up disk space.
- Manage log files for troubleshooting.

## Development

### Project Structure
```
GodotLauncher/
├── main.py                 # Entry point
├── utils.py                # Utility functions
├── data_manager.py         # Data management
├── project_handler.py      # Project handling
├── api_clients.py          # API clients
├── validators.py           # Input validation
│
├── gui/                    # UI components
│   ├── main_window.py      # Main window
│   ├── projects_tab.py     # Projects tab
│   ├── extensions_tab.py   # Extensions tab
│   ├── templates_tab.py    # Templates tab
│   ├── settings_dialog.py  # Settings dialog
│   └── ...                 # Other UI components
│
└── cache/                  # Temporary cache
```

## Issues Reporting

If you find an issue/bug on code and you cannot try fix and submit a pull request, [open up an Issue](https://github.com/sebastianoboem/godot-launcher/issues/new/choose) on how you have find the bug.
  - Be as much detailed as possible so i can reproduce the bug/issue by myself and try to fix it as fast as possible. The more detail you gave, the better i can find the issue.

## Contributing

Contributions are welcome! Please feel free to submit a [Pull Request](https://github.com/sebastianoboem/godot-launcher/pulls).

## Features Proposal

Feel free to [open up a poll](https://github.com/sebastianoboem/godot-launcher/discussions/new?category=polls) in the discussions sections.
  - Try to be as much detailed as possible.
  - Include some example.
