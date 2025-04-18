# gui/common_widgets.py

import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import QFrame
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QMouseEvent, QEnterEvent, QPaintEvent


class ClickableAssetFrame(QFrame):
    """
    A QFrame subclass that emits a 'clicked' signal when pressed with the left mouse button.
    It's designed to hold and emit data associated with a specific asset.
    """

    # Signal emitted when the frame is clicked, carrying asset data.
    clicked = pyqtSignal(dict) # Emits a dictionary: {'asset_id': Any, 'initial_data': Dict[str, Any]}

    def __init__(self, parent=None):
        """Initializes the ClickableAssetFrame."""
        super().__init__(parent)
        self.setProperty("clickable", True) # Custom property for potential styling
        self._asset_id: Optional[Any] = None
        self._initial_data: Optional[Dict[str, Any]] = None
        self.setFrameShape(QFrame.Shape.StyledPanel) # Give it a default visible shape
        self.setFrameShadow(QFrame.Shadow.Raised)   # Give it a default visible shadow

    def setAssetData(self, asset_id: Any, initial_data: Dict[str, Any]):
        """
        Sets the data associated with this clickable frame.

        Args:
            asset_id: The unique identifier for the asset.
            initial_data: A dictionary containing initial data about the asset (e.g., title).
        """
        self._asset_id = asset_id
        self._initial_data = initial_data
        # Set a generic tooltip using the asset title or ID
        title = initial_data.get('title', str(asset_id)) # Fallback to asset_id if title missing
        self.setToolTip(f"Click to view details for '{title}'")

    def mousePressEvent(self, event: QMouseEvent):
        """Handles mouse press events to detect left clicks."""
        if event.button() == Qt.MouseButton.LeftButton:
            logging.debug(f"ClickableAssetFrame clicked: ID={self._asset_id}")
            # Emit the signal with the stored initial_data dictionary directly.
            # This assumes initial_data already contains necessary info like asset_id.
            if self._initial_data is not None:
                self.clicked.emit(self._initial_data)
            else:
                 logging.warning("ClickableAssetFrame clicked but asset data (_initial_data) is not set.")
        # Call the base implementation for other buttons or event handling
        super().mousePressEvent(event)

    def enterEvent(self, event: QEnterEvent):
        """Changes the cursor to a pointing hand when the mouse enters the frame."""
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Optional: Add visual feedback on hover (e.g., change background)
        # self.setStyleSheet("QFrame[clickable=true] { background-color: #e8f0fe; border: 1px solid #c8d8f8; }")
        super().enterEvent(event)

    def leaveEvent(self, event: QMouseEvent): # QMouseEvent is correct type hint here
        """Resets the cursor when the mouse leaves the frame."""
        self.unsetCursor()
        # Optional: Restore original style if changed on enterEvent
        # self.setStyleSheet("")
        super().leaveEvent(event)

    # Note: The default paintEvent is usually sufficient unless custom drawing is needed.
    # If uncommenting paintEvent, ensure QStyleOption, QPainter, QStyle are imported from QtGui/QtWidgets.
    # from PyQt6.QtWidgets import QStyle, QStyleOption
    # from PyQt6.QtGui import QPainter
    # def paintEvent(self, event: QPaintEvent):
    #    """Ensures custom styling is applied correctly (optional)."""
    #    opt = QStyleOption()
    #    opt.initFrom(self)
    #    p = QPainter(self)
    #    self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
    #    # super().paintEvent(event) # Call super if you want default drawing too
