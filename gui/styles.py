# -*- coding: utf-8 -*-
# gui/styles.py

"""
This file is a wrapper for the gui/styles/ package.
Imports and re-exports all styles to maintain compatibility with existing code.
"""

# Import all styles from the new package
from gui.styles.colors import COLORS
from gui.styles.buttons import (
    NAV_BUTTON_STYLE,
    BUTTON_STYLE,
    PRIMARY_BUTTON_STYLE,
    DANGER_BUTTON_STYLE
)
from gui.styles.inputs import (
    INPUT_STYLE,
    INPUT_NEUTRAL_STYLE,
    INPUT_VALID_STYLE,
    INPUT_INVALID_STYLE,
    CHECKBOX_STYLE
)
from gui.styles.containers import (
    GROUP_BOX_STYLE,
    LIST_WIDGET_STYLE,
    FRAME_STYLE,
    DIALOG_STYLE
)
from gui.styles.misc import (
    PROGRESS_BAR_STYLE,
    SPLITTER_STYLE,
    TITLE_LABEL_STYLE
)
from gui.styles.main import MAIN_STYLE
from gui.styles.components import (
    STATUS_STYLE,
    PAGINATION_STYLE,
    ASSET_TITLE_STYLE,
    ASSET_INFO_STYLE,
    COPY_BUTTON_STYLE,
    ICON_PLACEHOLDER_STYLE,
    CANCEL_BUTTON_STYLE
)

# Export all styles
__all__ = [
    'COLORS',
    'MAIN_STYLE',
    'NAV_BUTTON_STYLE',
    'BUTTON_STYLE',
    'PRIMARY_BUTTON_STYLE',
    'DANGER_BUTTON_STYLE',
    'INPUT_STYLE',
    'INPUT_NEUTRAL_STYLE',
    'INPUT_VALID_STYLE',
    'INPUT_INVALID_STYLE',
    'GROUP_BOX_STYLE',
    'LIST_WIDGET_STYLE',
    'PROGRESS_BAR_STYLE',
    'SPLITTER_STYLE',
    'FRAME_STYLE',
    'TITLE_LABEL_STYLE',
    'CHECKBOX_STYLE',
    'DIALOG_STYLE',
    # Specific components
    'STATUS_STYLE',
    'PAGINATION_STYLE',
    'ASSET_TITLE_STYLE',
    'ASSET_INFO_STYLE',
    'COPY_BUTTON_STYLE',
    'ICON_PLACEHOLDER_STYLE',
    'CANCEL_BUTTON_STYLE'
] 