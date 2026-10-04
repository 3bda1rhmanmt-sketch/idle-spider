"""QPainter helpers shared by the overlay and the tray icon."""

from __future__ import annotations

import math
from collections.abc import Iterable

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from ..animation.spider import Spider


def web_path(lines: Iterable[tuple[float, float, float, float]]) -> QPainterPath:
    """One path for all threads, so overlapping threads do not compound opacity."""
    path = QPainterPath()
    for x1, y1, x2, y2 in lines:
        path.moveTo(x1, y1)
        path.lineTo(x2, y2)
    return path


def paint_spider(
    painter: QPainter, spider: Spider, color: QColor, halo_alpha: int = 70
) -> None:
    """Draw the minimal vector spider (8 legs, round body, two tiny eyes)."""
    s = spider.size
    dark = color.lightness() < 128
    halo = QColor(255, 255, 255, halo_alpha) if dark else QColor(0, 0, 0, halo_alpha)
    eye = QColor(255, 255, 255) if dark else QColor(20, 20, 20)

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(spider.pos[0], spider.pos[1])
    painter.rotate(math.degrees(spider.heading))

    legs = QPainterPath()
    for hip, knee, foot in spider.legs():
        legs.moveTo(*hip)
        legs.lineTo(*knee)
        legs.lineTo(*foot)
    width = max(1.0, s * 0.09)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    pen = QPen(halo, width + 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
               Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawPath(legs)
    pen.setColor(color)
    pen.setWidthF(width)
    painter.setPen(pen)
    painter.drawPath(legs)

    painter.setPen(QPen(halo, 1.2))
    painter.setBrush(color)
    painter.drawEllipse(QPointF(-0.38 * s, 0.0), 0.45 * s, 0.36 * s)   # abdomen
    painter.drawEllipse(QPointF(0.24 * s, 0.0), 0.26 * s, 0.24 * s)    # head
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(eye)
    r = 0.055 * s
    for side in (-1, 1):
        painter.drawEllipse(QPointF(0.38 * s, side * 0.10 * s), r, r)
    painter.restore()
