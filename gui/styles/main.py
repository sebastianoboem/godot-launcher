"""
Main application styles.
Includes basic styles for main widgets.
"""

from .colors import COLORS

# Stylesheet principale dell'applicazione
MAIN_STYLE = f"""
    QWidget {{
        background-color: {COLORS["bg_dark"]};
        color: {COLORS["text_primary"]};
        font-family: 'Segoe UI', Arial, sans-serif;
    }}
    
    QMainWindow {{
        background-color: {COLORS["bg_dark"]};
    }}
    
    QTabWidget::pane {{
        border: 1px solid {COLORS["border"]};
        background-color: {COLORS["bg_content"]};
        border-radius: 4px;
    }}
    
    QTabBar::tab {{
        padding: 10px 16px;
        min-width: 100px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        background-color: {COLORS["bg_dark"]};
        margin-right: 2px;
        color: {COLORS["text_secondary"]};
    }}
    
    QTabBar::tab:selected {{
        background-color: {COLORS["bg_content"]};
        color: {COLORS["text_primary"]};
        border-bottom: 2px solid {COLORS["accent"]};
    }}
    
    QTabBar::tab:hover:!selected {{
        background-color: #303030;
    }}
    
    QStatusBar {{
        background-color: {COLORS["bg_dark"]};
        color: {COLORS["text_secondary"]};
        border-top: 1px solid {COLORS["border"]};
    }}
    
    QLabel {{
        background-color: transparent;
        color: {COLORS["text_primary"]};
    }}
    
    QScrollBar:vertical {{
        background-color: {COLORS["bg_dark"]};
        width: 12px;
        margin: 0px;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {COLORS["muted"]};
        min-height: 20px;
        border-radius: 6px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {COLORS["accent"]};
    }}
    
    QScrollBar:horizontal {{
        background-color: {COLORS["bg_dark"]};
        height: 12px;
        margin: 0px;
    }}
    
    QScrollBar::handle:horizontal {{
        background-color: {COLORS["muted"]};
        min-width: 20px;
        border-radius: 6px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background-color: {COLORS["accent"]};
    }}
""" 