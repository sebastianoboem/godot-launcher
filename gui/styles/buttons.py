"""
Definition of styles for application buttons.
Includes styles for different types of buttons: navigation, standard, primary and danger.
"""

from .colors import COLORS

# Stile per i bottoni di navigazione
NAV_BUTTON_STYLE = f"""
    QPushButton {{
        padding: 15px 25px;
        font-size: 12pt;
        border: none;
        border-radius: 4px;
        background-color: transparent;
        color: {COLORS["text_secondary"]};
        text-align: center;
        outline: none;
        min-width: 160px;
        max-width: 160px;
    }}
    
    QPushButton:hover {{
        background-color: rgba(255, 255, 255, 0.1);
        color: {COLORS["text_primary"]};
    }}
    
    QPushButton:checked {{
        background-color: {COLORS["accent"]};
        color: white;
        font-weight: bold;
    }}
    
    QPushButton:pressed {{
        background-color: {COLORS["accent_hover"]};
    }}
"""

# Stile per i bottoni standard
BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {COLORS["bg_content"]};
        color: {COLORS["text_primary"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 4px;
        padding: 8px 16px;
        font-weight: bold;
    }}
    
    QPushButton:hover {{
        background-color: {COLORS["muted"]};
    }}
    
    QPushButton:pressed {{
        background-color: {COLORS["border"]};
    }}
    
    QPushButton:disabled {{
        background-color: {COLORS["bg_content"]};
        color: {COLORS["muted"]};
        border-color: {COLORS["border"]};
    }}
"""

# Stile per i bottoni di azione primaria (accento)
PRIMARY_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {COLORS["accent"]};
        color: white;
        border: none;
        border-radius: 4px;
        padding: 8px 16px;
        font-weight: bold;
    }}
    
    QPushButton:hover {{
        background-color: {COLORS["accent_hover"]};
    }}
    
    QPushButton:pressed {{
        background-color: {COLORS["accent"]};
        opacity: 0.8;
    }}
    
    QPushButton:disabled {{
        background-color: {COLORS["muted"]};
        color: {COLORS["text_secondary"]};
    }}
"""

# Stile per i bottoni di pericolo/rimozione
DANGER_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: transparent;
        color: {COLORS["error"]};
        border: 1px solid {COLORS["error"]};
        border-radius: 4px;
        padding: 8px 16px;
        font-weight: bold;
    }}
    
    QPushButton:hover {{
        background-color: {COLORS["error"]};
        color: white;
    }}
    
    QPushButton:pressed {{
        background-color: #D32F2F;
        color: white;
    }}
""" 