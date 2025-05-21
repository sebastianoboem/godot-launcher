# Changelog

All notable changes to the GodotLauncher project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Smart ZIP extraction algorithm that recursively searches for 'addons' directories
- Automatic update checking at startup with configurable settings
- Version display in status bar and application title
- Two executable versions during build: console version for debugging and no-console version for clean UI
- Cache cleanup functionality with preservation of directory structure
- Log file cleanup functionality with proper file permission handling
- Comprehensive test documentation in English with detailed instructions for running and extending tests
- Windows portable release with two executable versions and portable package

### Changed
- Improved UI interaction by automatically updating manual path field when selecting Godot version
- Optimized settings UI loading with immediate initialization
- Standardized all user text, comments, and log messages to English
- Improved UI robustness in Settings and Extensions tabs
- Updated README.md with information about antivirus false positives

### Fixed
- Issue preventing saving of installed Godot versions in settings
- UI styles missing issue (ITEM_SELECTED_STYLE) that prevented application startup
- Extension display issue that prevented viewing the complete list of available extensions
- Extensions checkboxes displaying as unselected for selected extensions
- Error messages and handling for extensions that cannot be removed

## [1.0.0-dev1] - 2025-04-18

### Added
- Basic application structure
- Project management functionality
- Extension management with Asset Library integration
- Extension filtering by support type
- Multi-project extension installation
- Logging system with rotation and differentiated levels
- Asynchronous downloads with progress reporting
- Tab-based UI layout with separate components for each feature

### Changed
- Initial project structure and organization
- Settings dialog implementation

### Fixed
- Initial bug fixes and improvements

[Unreleased]: https://github.com/username/GodotLauncher/compare/v1.0.0-dev1...HEAD
[1.0.0-dev1]: https://github.com/username/GodotLauncher/releases/tag/v1.0.0-dev1 