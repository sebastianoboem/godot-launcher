"""
Definition of styles for various components.
Includes styles for ProgressBar, Splitter and title labels.
"""

from .colors import COLORS

# Stile per QProgressBar
PROGRESS_BAR_STYLE = f"""
    QProgressBar {{
        border: 1px solid {COLORS["border"]};
        border-radius: 4px;
        background-color: {COLORS["bg_content"]};
        text-align: center;
        color: {COLORS["text_primary"]};
        height: 10px;
    }}
    
    QProgressBar::chunk {{
        background-color: {COLORS["accent"]};
        border-radius: 2px;
    }}
"""

# Stile per QSplitter
SPLITTER_STYLE = f"""
    QSplitter {{
        width: 3px;
        background-color: transparent;
    }}

    QSplitter::handle {{
        background-color: {COLORS["border"]};
        width: 3px;
        height: 1px;
        margin: 0px 10px;
    }}
    
    QSplitter::handle:horizontal:hover {{
        background-color: {COLORS["accent"]};
    }}
"""

# Stile per QLabel con titolo
TITLE_LABEL_STYLE = f"""
    QLabel {{
        color: {COLORS["text_primary"]};
        font-size: 14pt;
        font-weight: bold;
        border: 0px;
    }}
"""

# Style for selected items in list widgets
ITEM_SELECTED_STYLE = f"""
    QListWidget::item:selected {{
        background-color: {COLORS["accent"]};
        color: white;
        border-radius: 3px;
    }}
    
    QListWidget::item:hover {{
        background-color: {COLORS["bg_hover"]};
        border-radius: 3px;
    }}
""" 