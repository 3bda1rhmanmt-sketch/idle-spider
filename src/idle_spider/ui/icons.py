"""Application icon drawn with QPainter (no binary assets required)."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from ..animation.spider import Spider
from .painting import paint_spider


def make_app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 22, 32, 48, 64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        spider = Spider((size / 2, size / 2), size * 0.36)
        spider.heading = -math.pi / 2
        paint_spider(painter, spider, QColor("#202020"), halo_alpha=220)
        painter.end()
        icon.addPixmap(pixmap)
    return icon
