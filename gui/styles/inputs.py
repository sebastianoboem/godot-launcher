"""
Definition of styles for input components like textbox, combobox, and checkbox.
Also includes styles for the different validation states of inputs.
"""

from .colors import COLORS

# Stile per i campi di input
INPUT_STYLE = f"""
    QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QComboBox {{
        background-color: {COLORS["bg_content"]};
        color: {COLORS["text_primary"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 4px;
        padding: 8px;
    }}
    
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus, QComboBox:focus {{
        border: 1px solid {COLORS["accent"]};
    }}
    
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    
    QComboBox::down-arrow {{
        image: url("assets/icons/dropdown-arrow.png");
        width: 12px;
        height: 12px;
    }}
    
    QComboBox QAbstractItemView {{
        background-color: {COLORS["bg_content"]};
        color: {COLORS["text_primary"]};
        border: 1px solid {COLORS["border"]};
        selection-background-color: {COLORS["accent"]};
    }}
"""

# Stili per la validazione degli input
INPUT_NEUTRAL_STYLE = f"""
    QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QComboBox {{
        background-color: {COLORS["bg_content"]};
        color: {COLORS["text_primary"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 4px;
        padding: 8px;
    }}
    
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus, QComboBox:focus {{
        border: 1px solid {COLORS["accent"]};
    }}
"""

INPUT_VALID_STYLE = f"""
    QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QComboBox {{
        background-color: {COLORS["bg_content"]};
        color: {COLORS["text_primary"]};
        border: 1px solid {COLORS["success"]};
        border-radius: 4px;
        padding: 8px;
    }}
    
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus, QComboBox:focus {{
        border: 1px solid {COLORS["success"]};
    }}
"""

INPUT_INVALID_STYLE = f"""
    QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QComboBox {{
        background-color: {COLORS["bg_content"]};
        color: {COLORS["text_primary"]};
        border: 1px solid {COLORS["error"]};
        border-radius: 4px;
        padding: 8px;
    }}
    
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus, QComboBox:focus {{
        border: 1px solid {COLORS["error"]};
    }}
"""

# Stile per QCheckBox
CHECKBOX_STYLE = f"""
    QCheckBox {{
        color: {COLORS["text_primary"]};
        background-color: {COLORS["bg_content"]};
        spacing: 8px;
    }}
    
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 1px solid {COLORS["border"]};
        border-radius: 3px;
    }}
    
    QCheckBox::indicator:unchecked {{
        background-color: {COLORS["bg_content"]};
    }}
    
    QCheckBox::indicator:checked {{
        background-color: {COLORS["accent"]};
        image: url("assets/icons/check.png");
    }}
    
    QCheckBox::indicator:hover {{
        border: 1px solid {COLORS["accent"]};
    }}
""" 