"""
Definition of specific styles for the Extensions tab.
Includes styles for cards, pagination and other specific interface components.
"""

from ..colors import COLORS

# Style for search status
STATUS_STYLE = f"""
    color: {COLORS["text_primary"]};
    background-color: {COLORS["bg_content"]};
    padding: 4px;
    border-radius: 4px;
"""

# Style for pagination controls
PAGINATION_STYLE = f"""
    QPushButton {{
        background-color: {COLORS["bg_dark"]};
        color: {COLORS["text_primary"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 4px;
        padding: 6px 12px;
    }}
    QPushButton:hover {{
        background-color: {COLORS["accent"]};
        color: white;
    }}
    QPushButton:disabled {{
        background-color: {COLORS["bg_dark"]};
        color: {COLORS["muted"]};
        border-color: {COLORS["bg_dark"]};
    }}
    QLabel {{
        color: {COLORS["text_primary"]};
        font-weight: bold;
        padding: 0 10px;
    }}
"""

# Style for asset titles
ASSET_TITLE_STYLE = f"""
    QLabel {{
        color: {COLORS["text_primary"]};
        font-weight: bold;
        font-size: 13px;
    }}
"""

# Style for asset info
ASSET_INFO_STYLE = f"""
    QLabel {{
        color: {COLORS["text_secondary"]};
        font-size: 11px;
    }}
"""

# Style for ID copy buttons
COPY_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {COLORS["bg_content"]};
        color: {COLORS["text_primary"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 4px;
        padding: 4px;
        font-size: 11px;
    }}
    QPushButton:hover {{
        border-color: {COLORS["accent"]};
        color: white;
    }}
    QPushButton:pressed {{
        background-color: {COLORS["accent_hover"]};
    }}
"""

# Style for unloaded icons
ICON_PLACEHOLDER_STYLE = f"""
    QLabel {{
        background-color: {COLORS["bg_dark"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 4px;
        color: {COLORS["text_secondary"]};
        padding: 2px;
        qproperty-alignment: AlignCenter;
    }}
"""

# Style for cancel button
CANCEL_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {COLORS["bg_dark"]};
        color: {COLORS["error"]};
        border: 1px solid {COLORS["error"]};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
    }}
    QPushButton:hover {{
        background-color: {COLORS["error"]};
        color: white;
    }}
    QPushButton:pressed {{
        background-color: #D32F2F;
    }}
""" 