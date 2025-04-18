"""
Initialization module for the styles package.
Imports and combines all style modules to facilitate importing.
"""

# Import all style modules
from .colors import COLORS
from .buttons import (
    NAV_BUTTON_STYLE,
    BUTTON_STYLE,
    PRIMARY_BUTTON_STYLE,
    DANGER_BUTTON_STYLE
)
from .inputs import (
    INPUT_STYLE,
    INPUT_NEUTRAL_STYLE,
    INPUT_VALID_STYLE,
    INPUT_INVALID_STYLE,
    CHECKBOX_STYLE
)
from .containers import (
    GROUP_BOX_STYLE,
    LIST_WIDGET_STYLE,
    FRAME_STYLE,
    DIALOG_STYLE
)
from .misc import (
    PROGRESS_BAR_STYLE,
    SPLITTER_STYLE,
    TITLE_LABEL_STYLE,
    ITEM_SELECTED_STYLE
)
from .main import MAIN_STYLE

# Import specific component styles
from .components import (
    STATUS_STYLE,
    PAGINATION_STYLE,
    ASSET_TITLE_STYLE,
    ASSET_INFO_STYLE,
    COPY_BUTTON_STYLE,
    ICON_PLACEHOLDER_STYLE,
    CANCEL_BUTTON_STYLE
)

# Export all elements
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
    'STATUS_STYLE',
    'PAGINATION_STYLE',
    'ASSET_TITLE_STYLE',
    'ASSET_INFO_STYLE',
    'COPY_BUTTON_STYLE',
    'ICON_PLACEHOLDER_STYLE',
    'CANCEL_BUTTON_STYLE',
    'ITEM_SELECTED_STYLE'
] 