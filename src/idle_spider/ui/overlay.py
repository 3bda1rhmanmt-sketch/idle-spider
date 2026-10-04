"""Transparent, click-through, focus-less overlay (one per monitor)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QPixmap, QScreen
from PySide6.QtWidgets import QWidget

from ..animation.controller import Scene
from .painting import paint_spider, web_path


@dataclass(frozen=True)
class OverlayStyle:
    spider_color: QColor
    web_color: QColor
    web_opacity: float

    def web_pen(self) -> QPen:
        color = QColor(self.web_color)
        color.setAlphaF(self.web_opacity)
        return QPen(color, 1.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin)


class OverlayWindow(QWidget):
    """Draws one :class:`Scene`. Finished webs are cached in a pixmap; each frame only
    the spider and the web under construction are repainted (dirty-rect updates)."""

    def __init__(self, screen: QScreen, scene: Scene, style: OverlayStyle) -> None:
        super().__init__(None)
        self._screen = screen
        self._scene = scene
        self._style = style
        self._alpha = 1.0
        self._cache: QPixmap | None = None
        self._cache_version = -1
        self._last_rect = None
        self._native_wayland = QGuiApplication.platformName() == "wayland"

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if QGuiApplication.platformName() == "xcb":
            flags |= Qt.WindowType.X11BypassWindowManagerHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())

    def present(self) -> None:
        self.setScreen(self._screen)
        if self._native_wayland:
            self.showFullScreen()      # native Wayland cannot position toplevels
        else:
            self.setGeometry(self._screen.geometry())
            self.show()

    def dismiss(self) -> None:
        self.hide()
        self.deleteLater()

    def refresh(self, alpha: float) -> None:
        """Schedule a repaint of only what changed."""
        scene = self._scene
        full = scene.completed_version != self._cache_version or abs(alpha - self._alpha) > 1e-3
        self._alpha = alpha
        rect = QRectF(*scene.dirty_rect()).toAlignedRect().adjusted(-3, -3, 3, 3)
        if full:
            self.update()
        else:
            self.update(rect.united(self._last_rect) if self._last_rect else rect)
        self._last_rect = rect

    def _rebuild_cache(self) -> None:
        dpr = self.devicePixelRatioF()
        pixmap = QPixmap(int(self.width() * dpr), int(self.height() * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(self._style.web_pen())
        for web in self._scene.webs:
            painter.drawPath(web_path(web.lines()))
        painter.end()
        self._cache = pixmap
        self._cache_version = self._scene.completed_version

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._cache is None or self._cache_version != self._scene.completed_version:
            self._rebuild_cache()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(self._alpha)
        if self._cache is not None:
            painter.drawPixmap(0, 0, self._cache)
        active = self._scene.active_web
        if active is not None:
            painter.setPen(self._style.web_pen())
            painter.drawPath(web_path(active.lines()))
        paint_spider(painter, self._scene.spider, self._style.spider_color)
        painter.end()
