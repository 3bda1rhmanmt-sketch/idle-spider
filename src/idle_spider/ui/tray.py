"""System tray icon and menu."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .icons import make_app_icon


class TrayController(QObject):
    enable_toggled = Signal(bool)
    settings_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    start_requested = Signal()
    stop_requested = Signal()
    test_requested = Signal()
    reset_requested = Signal()
    quit_requested = Signal()

    @staticmethod
    def available() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(make_app_icon(), self)
        self._tray.setToolTip("Idle Spider")
        menu = QMenu()
        self._menu = menu

        self._enable = QAction("Enable", menu, checkable=True)
        self._enable.toggled.connect(self.enable_toggled)
        menu.addAction(self._enable)
        self._act("Settings…", self.settings_requested)
        menu.addSeparator()
        self._pause = self._act("Pause", self.pause_requested)
        self._resume = self._act("Resume", self.resume_requested)
        menu.addSeparator()
        self._start = self._act("Start Animation Now", self.start_requested)
        self._stop = self._act("Stop Animation", self.stop_requested)
        self._act("Test Animation", self.test_requested)
        self._act("Reset", self.reset_requested)
        menu.addSeparator()
        self._act("Quit", self.quit_requested)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)

    def _act(self, text: str, signal: Signal) -> QAction:
        action = QAction(text, self._menu)
        action.triggered.connect(lambda _checked=False: signal.emit())
        self._menu.addAction(action)
        return action

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.settings_requested.emit()

    def sync(self, enabled: bool, paused: bool, animating: bool) -> None:
        self._enable.blockSignals(True)
        self._enable.setChecked(enabled)
        self._enable.blockSignals(False)
        self._pause.setEnabled(enabled and not paused)
        self._resume.setEnabled(enabled and paused)
        self._start.setEnabled(not animating)
        self._stop.setEnabled(animating)

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def notify(self, message: str) -> None:
        self._tray.showMessage("Idle Spider", message, QSystemTrayIcon.MessageIcon.Warning, 10_000)
