"""
Definition of styles for container-type components.
Includes styles for GroupBox, ListWidget, Frame and Dialog.
"""

from .colors import COLORS

# Stile per QGroupBox
GROUP_BOX_STYLE = f"""
    QGroupBox {{
        background-color: {COLORS["bg_content"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 4px;
        margin-top: 10px;
        font-weight: bold;
        padding-top: 15px;
    }}
    
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 15px;
        background-color: {COLORS["accent"]};
        color: white;
        padding: 3px 12px;
        border-radius: 3px;
    }}
"""

# Stile per QListWidget
LIST_WIDGET_STYLE = f"""
    QListWidget {{
        background-color: {COLORS["bg_content"]};
        color: {COLORS["text_primary"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 4px;
        padding: 5px;
        outline: none;
    }}
    
    QListWidget::item {{
        padding: 8px;
        border-radius: 4px;
    }}
    
    QListWidget::item:selected {{
        background-color: {COLORS["accent"]};
        color: white;
    }}
    
    QListWidget::item:hover:!selected {{
        background-color: rgba(255, 255, 255, 0.1);
    }}
"""

# Stile per QFrame
FRAME_STYLE = f"""
    QFrame {{
        background-color: {COLORS["bg_content"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 4px;
    }}
"""

# Stile per QDialog
DIALOG_STYLE = f"""
    QDialog {{
        background-color: {COLORS["bg_dark"]};
        color: {COLORS["text_primary"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 6px;
    }}
    
    QDialog QLabel {{
        color: {COLORS["text_primary"]};
    }}
    
    QDialog QLabel[title="true"] {{
        font-size: 14pt;
        font-weight: bold;
        margin-bottom: 10px;
    }}
    
    QDialog QLabel[subtitle="true"] {{
        color: {COLORS["text_secondary"]};
        font-style: italic;
    }}
""" 