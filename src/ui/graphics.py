"""Graphics items for canvas rendering."""

from typing import List

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPen, QBrush, QColor, QPainter
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem


class GroupBoxItem(QGraphicsRectItem):
    """Resizable, draggable bounding box for a text group."""

    def __init__(self, group_id: int, bbox: List[List[float]], parent=None):
        """Initialize group box.

        Args:
            group_id: Unique identifier for this group
            bbox: 4-point bounding box [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        """
        self.group_id = group_id
        self.bbox_points = bbox

        # Convert bbox to rectangle
        xs = [pt[0] for pt in bbox]
        ys = [pt[1] for pt in bbox]
        x_min, y_min = min(xs), min(ys)
        width = max(xs) - x_min
        height = max(ys) - y_min

        super().__init__(x_min, y_min, width, height, parent)

        # Make interactive
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

        # Default styling
        self.setPen(QPen(QColor(0, 255, 0, 200), 2))  # Green outline
        self.setBrush(QBrush(QColor(0, 255, 0, 30)))  # Transparent green fill

        # Selected styling
        self.selected_pen = QPen(QColor(255, 255, 0, 255), 3)  # Yellow outline
        self.selected_brush = QBrush(QColor(255, 255, 0, 50))  # Transparent yellow fill

    def paint(self, painter: QPainter, option, widget=None):
        """Custom paint to handle selection state."""
        if self.isSelected():
            painter.setPen(self.selected_pen)
            painter.setBrush(self.selected_brush)
        else:
            painter.setPen(self.pen())
            painter.setBrush(self.brush())

        painter.drawRect(self.rect())

    def get_bbox(self) -> List[List[float]]:
        """Get current bounding box as 4-point format."""
        rect = self.rect()
        x = self.x()
        y = self.y()

        return [
            [x + rect.left(), y + rect.top()],
            [x + rect.right(), y + rect.top()],
            [x + rect.right(), y + rect.bottom()],
            [x + rect.left(), y + rect.bottom()],
        ]

    def set_bbox(self, bbox: List[List[float]]) -> None:
        """Update box from 4-point format."""
        xs = [pt[0] for pt in bbox]
        ys = [pt[1] for pt in bbox]
        x_min, y_min = min(xs), min(ys)
        width = max(xs) - x_min
        height = max(ys) - y_min

        self.setRect(0, 0, width, height)
        self.setPos(x_min, y_min)
        self.bbox_points = bbox
