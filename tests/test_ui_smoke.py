"""Offscreen Qt smoke tests: construction, painting and the app state flow."""

import random

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor, QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from idle_spider.animation.controller import (  # noqa: E402
    AnimationController,
    AnimationSettings,
    ScreenInfo,
)
from idle_spider.config import Config  # noqa: E402
from idle_spider.ui.overlay import OverlayStyle, OverlayWindow  # noqa: E402
from idle_spider.ui.settings import SettingsWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_overlay_paints_nonblank(qapp):
    screen = QGuiApplication.primaryScreen()
    ctrl = AnimationController(AnimationSettings(speed=3.0), random.Random(1))
    ctrl.start([ScreenInfo(0, 800, 600)])
    for _ in range(600):
        ctrl.update(1 / 30)
    overlay = OverlayWindow(screen, ctrl.scenes[0],
                            OverlayStyle(QColor("#000"), QColor("#fff"), 0.8))
    overlay.resize(800, 600)
    overlay.refresh(1.0)
    image = overlay.grab().toImage()
    assert not image.isNull()
    assert any(image.pixelColor(x, y).alpha() > 0
               for x in range(0, 800, 7) for y in range(0, 600, 7))
    overlay.dismiss()


def test_settings_roundtrip(qapp):
    cfg = Config(idle_timeout=90, spider_color="#1e88e5", web_color="#123456",
                 start_corner="random", monitor_mode="all", max_webs=3, web_density=8)
    win = SettingsWindow(cfg, "backend")
    assert win.to_config() == cfg.normalize()
