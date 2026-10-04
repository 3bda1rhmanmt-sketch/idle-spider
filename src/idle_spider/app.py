"""Application coordinator: wires detector, state machine, animation and UI."""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, replace

from PySide6.QtCore import QElapsedTimer, QObject, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QScreen
from PySide6.QtWidgets import QApplication

from .animation.controller import AnimationController, AnimationSettings, ScreenInfo
from .config import Config, ConfigStore
from .idle.base import IdleDetector
from .idle.detector import select_detector
from .state import State, StateMachine
from .ui.overlay import OverlayStyle, OverlayWindow
from .ui.settings import SettingsWindow
from .ui.tray import TrayController
from .utils.autostart import is_autostart_enabled, set_autostart
from .utils.platform import SessionInfo

log = logging.getLogger(__name__)

TEST_DURATION_S = 20.0          # "Test Animation" runs this long, ignoring input
NO_ACTIVITY_LIMIT_S = 60.0      # manual run when the backend cannot see activity
ACTIVITY_GRACE_S = 0.9          # ignore the click that started a manual run
COOLDOWN_S = 1.5
MONITOR_INTERVAL_MS = 1000
ACTIVITY_INTERVAL_MS = 150
FRAME_INTERVAL_MS = 16


@dataclass
class AppOptions:
    timeout: int | None = None      # CLI override (not persisted)
    no_tray: bool = False
    open_settings: bool = False
    run_test: bool = False


class IdleSpiderApp(QObject):
    def __init__(self, qt_app: QApplication, store: ConfigStore, options: AppOptions,
                 session: SessionInfo) -> None:
        super().__init__()
        self.qt_app = qt_app
        self.store = store
        self.options = options
        self.session = session
        self.rng = random.Random()
        self.paused = False

        self.sm = StateMachine()
        self.sm.add_listener(lambda a, b: log.debug("State %s -> %s", a.name, b.name))
        self.detector: IdleDetector = select_detector(session, self.timeout)
        self.detector.set_timeout(self.timeout)
        self.controller = AnimationController(
            AnimationSettings.from_config(store.config), self.rng)

        self.tray: TrayController | None = None
        self.settings_window: SettingsWindow | None = None
        self._overlays: list[OverlayWindow] = []
        self._ignore_activity = False
        self._auto_stop_at: float | None = None
        self._grace_until = 0.0
        self._cooldown_until = 0.0
        self._last_idle: float | None = None
        self._last_begin = (False, None, False)   # manual, auto_stop, ignore_activity

        self._monitor_timer = QTimer(self)
        self._monitor_timer.setInterval(MONITOR_INTERVAL_MS)
        self._monitor_timer.timeout.connect(self._poll_idle)
        self._activity_timer = QTimer(self)
        self._activity_timer.setInterval(ACTIVITY_INTERVAL_MS)
        self._activity_timer.timeout.connect(self._poll_activity)
        self._frame_timer = QTimer(self)
        self._frame_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._frame_timer.setInterval(FRAME_INTERVAL_MS)
        self._frame_timer.timeout.connect(self._tick)
        self._clock = QElapsedTimer()
        self._screens_timer = QTimer(self)
        self._screens_timer.setSingleShot(True)
        self._screens_timer.setInterval(300)
        self._screens_timer.timeout.connect(self._on_screens_settled)

    # -- properties ----------------------------------------------------
    @property
    def config(self) -> Config:
        return self.store.config

    @property
    def timeout(self) -> int:
        return self.options.timeout or self.config.idle_timeout

    @property
    def animating(self) -> bool:
        return self.sm.state is not State.MONITORING

    # -- lifecycle -----------------------------------------------------
    def start(self) -> None:
        log.info("Idle timeout: %ds", self.timeout)
        if self.config.autostart != is_autostart_enabled():
            set_autostart(self.config.autostart)
        for screen in QGuiApplication.screens():
            self._watch_screen(screen)
        self.qt_app.screenAdded.connect(self._watch_screen)
        self.qt_app.screenRemoved.connect(lambda _s: self._screens_timer.start())
        self.qt_app.primaryScreenChanged.connect(lambda _s: self._screens_timer.start())

        if not self.options.no_tray:
            if TrayController.available():
                self.tray = TrayController(self)
                self._connect_tray(self.tray)
                self.tray.show()
            else:
                log.warning("System tray not available; opening the settings window instead. "
                            "Use 'idle-spider --quit' to stop the background process.")
                self.options.open_settings = True
        if self.detector.status_message:
            log.warning(self.detector.status_message)
            if self.tray:
                self.tray.notify(self.detector.status_message)

        self._sync_ui()
        self._update_monitoring()
        if self.options.open_settings:
            self.show_settings()
        if self.options.run_test:
            QTimer.singleShot(500, self.start_test)

    def _connect_tray(self, tray: TrayController) -> None:
        tray.enable_toggled.connect(self.set_enabled)
        tray.settings_requested.connect(self.show_settings)
        tray.pause_requested.connect(lambda: self.set_paused(True))
        tray.resume_requested.connect(lambda: self.set_paused(False))
        tray.start_requested.connect(self.start_now)
        tray.stop_requested.connect(self.stop_animation)
        tray.test_requested.connect(self.start_test)
        tray.reset_requested.connect(self.reset)
        tray.quit_requested.connect(self.quit)

    def handle_command(self, command: str) -> None:
        log.debug("Command: %s", command)
        match command:
            case "show" | "settings":
                self.show_settings()
            case "test":
                self.start_test()
            case "start":
                self.start_now()
            case "stop":
                self.stop_animation()
            case "quit":
                self.quit()

    def quit(self) -> None:
        log.info("Quitting")
        self._force_idle()
        self.detector.close()
        if self.tray:
            self.tray.hide()
        self.qt_app.quit()

    # -- user actions --------------------------------------------------
    def show_settings(self) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self.config, self._backend_text())
            self.settings_window.applied.connect(self.apply_config)
            self.settings_window.test_requested.connect(self.start_test)
        else:
            self.settings_window.load(self.config)
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _backend_text(self) -> str:
        text = f"Idle backend: {self.detector.name}"
        if self.detector.status_message:
            text += f"\n{self.detector.status_message}"
        return text

    def apply_config(self, new: Config) -> None:
        old = self.config
        if new.idle_timeout != old.idle_timeout:
            self.options.timeout = None          # explicit user choice wins over --timeout
        self.store.save(new.normalize())
        if new.autostart != old.autostart and not set_autostart(new.autostart):
            log.warning("Could not change the autostart entry")
        self.detector.set_timeout(self.timeout)
        self.controller.settings = AnimationSettings.from_config(new)
        if not new.enabled:
            self._force_idle()
        self._sync_ui()
        self._update_monitoring()
        log.info("Settings applied (timeout %ds)", self.timeout)

    def set_enabled(self, enabled: bool) -> None:
        self.apply_config(replace(self.config, enabled=enabled))

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        if paused:
            self._force_idle()
        log.info("Paused" if paused else "Resumed")
        self._sync_ui()
        self._update_monitoring()

    def start_now(self) -> None:
        """Run until user activity (or a safety limit if activity cannot be seen)."""
        limit = None if self.detector.reports_activity else NO_ACTIVITY_LIMIT_S
        self._begin(manual=True, auto_stop=limit, ignore_activity=False)

    def start_test(self) -> None:
        """Run for a fixed time regardless of input so the effect can be watched."""
        self._begin(manual=True, auto_stop=TEST_DURATION_S, ignore_activity=True)

    def stop_animation(self) -> None:
        self._request_stop("manual stop")

    def reset(self) -> None:
        self._force_idle()
        self.controller.stop()
        self._cooldown_until = 0.0
        log.info("Reset")
        self._update_monitoring()

    # -- monitoring ----------------------------------------------------
    def _update_monitoring(self) -> None:
        should = (self.config.enabled and not self.paused
                  and self.sm.state is State.MONITORING
                  and self.detector.get_idle_seconds() is not None)
        if should and not self._monitor_timer.isActive():
            self._monitor_timer.start()
        elif not should and self._monitor_timer.isActive():
            self._monitor_timer.stop()

    def _poll_idle(self) -> None:
        if time.monotonic() < self._cooldown_until:
            return
        idle = self.detector.get_idle_seconds()
        if idle is not None and idle >= self.timeout:
            log.info("Idle threshold reached (%.0fs)", idle)
            self._begin(manual=False, auto_stop=None, ignore_activity=False)

    def _poll_activity(self) -> None:
        now = time.monotonic()
        if self._auto_stop_at is not None and now >= self._auto_stop_at:
            self._request_stop("time limit reached")
            return
        if self._ignore_activity:
            return
        idle = self.detector.get_idle_seconds()
        if idle is None:
            return
        previous, self._last_idle = self._last_idle, idle
        if now >= self._grace_until and previous is not None and idle < previous - 0.25:
            log.info("Activity detected")
            self._request_stop("user activity")

    # -- animation lifecycle -------------------------------------------
    def _pick_screens(self) -> list[QScreen]:
        screens = QGuiApplication.screens()
        if not screens:
            return []
        mode = self.config.monitor_mode
        if mode == "all":
            return screens
        if mode == "random":
            return [self.rng.choice(screens)]
        current = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        return [current or screens[0]]

    def _begin(self, manual: bool, auto_stop: float | None, ignore_activity: bool) -> bool:
        if self.sm.state is not State.MONITORING:
            log.debug("Animation request ignored (state %s)", self.sm.state.name)
            return False
        screens = self._pick_screens()
        if not screens:
            log.warning("No screen available for the overlay")
            return False
        self.sm.transition(State.IDLE_DETECTED)
        self.sm.transition(State.ANIMATING)
        self._last_begin = (manual, auto_stop, ignore_activity)
        self._ignore_activity = ignore_activity

        self.controller.settings = AnimationSettings.from_config(self.config)
        infos = [ScreenInfo(i, s.geometry().width(), s.geometry().height())
                 for i, s in enumerate(screens)]
        self.controller.start(infos)
        style = OverlayStyle(QColor(self.config.spider_color), QColor(self.config.web_color),
                             self.config.web_opacity)
        for info, screen in zip(infos, screens, strict=True):
            overlay = OverlayWindow(screen, self.controller.scenes[info.index], style)
            overlay.present()
            self._overlays.append(overlay)

        now = time.monotonic()
        self._last_idle = self.detector.get_idle_seconds()
        self._grace_until = now + (ACTIVITY_GRACE_S if manual else 0.0)
        self._auto_stop_at = now + auto_stop if auto_stop else None
        self._monitor_timer.stop()
        self._clock.start()
        self._frame_timer.start()
        self._activity_timer.start()
        self._sync_ui()
        log.info("Animation started (%d screen(s)%s)", len(screens), ", manual" if manual else "")
        return True

    def _request_stop(self, reason: str) -> None:
        if self.sm.state is not State.ANIMATING:
            return
        log.info("Stopping animation: %s", reason)
        self.sm.transition(State.USER_ACTIVITY)
        self.sm.transition(State.FADE_OUT)
        self._activity_timer.stop()
        self.controller.begin_fade()
        self._clock.restart()
        if not self._frame_timer.isActive():
            self._frame_timer.start()

    def _tick(self) -> None:
        dt = self._clock.restart() / 1000.0
        self.controller.update(dt)
        alpha = self.controller.fade_alpha
        for overlay in self._overlays:
            overlay.refresh(alpha)
        if self.controller.fade_finished:
            self._finish()
        elif self.controller.settled and not self.controller.fading:
            self._frame_timer.stop()      # everything drawn: no more repaints needed

    def _finish(self) -> None:
        self._frame_timer.stop()
        self._activity_timer.stop()
        for overlay in self._overlays:
            overlay.dismiss()
        self._overlays.clear()
        self.controller.stop()
        self.sm.transition(State.MONITORING)
        self._cooldown_until = time.monotonic() + COOLDOWN_S
        log.info("Animation stopped")
        self._sync_ui()
        self._update_monitoring()

    def _force_idle(self) -> None:
        """Tear down immediately (no fade); safe in any state."""
        if self.sm.state is State.MONITORING:
            return
        if self.sm.state is State.ANIMATING:
            self.sm.transition(State.USER_ACTIVITY)
        if self.sm.state is State.USER_ACTIVITY:
            self.sm.transition(State.FADE_OUT)
        if self.sm.state is State.FADE_OUT:
            self._finish()
        else:
            self.sm.reset()

    # -- screens -------------------------------------------------------
    def _watch_screen(self, screen: QScreen) -> None:
        screen.geometryChanged.connect(lambda _g: self._screens_timer.start())
        screen.logicalDotsPerInchChanged.connect(lambda _d: self._screens_timer.start())
        if self.animating:
            self._screens_timer.start()

    def _on_screens_settled(self) -> None:
        if self.sm.state is State.ANIMATING:
            log.info("Screen layout changed; restarting animation")
            manual, auto_stop, ignore = self._last_begin
            self._force_idle()
            self._cooldown_until = 0.0
            self._begin(manual, auto_stop, ignore)

    # -- ui sync -------------------------------------------------------
    def _sync_ui(self) -> None:
        if self.tray:
            self.tray.sync(self.config.enabled, self.paused, self.animating)
