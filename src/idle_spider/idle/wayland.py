"""Wayland idle detection.

Wayland deliberately has no "global idle time" API for ordinary clients. What exists:

* GNOME (Mutter) exposes ``org.gnome.Mutter.IdleMonitor`` on the session D-Bus.
* Compositors implementing the ``ext-idle-notify-v1`` protocol (Sway, Hyprland, river,
  labwc, KDE Plasma 6, COSMIC, ...) can be queried through the ``swayidle`` tool,
  which is event driven (no polling of input).

Each strategy is probed at runtime; if none works the detector reports itself
unavailable and the application degrades to manual mode (see ``fallback.py``).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
from typing import Protocol

from .base import IdleDetector

log = logging.getLogger(__name__)


class WaylandBackend(Protocol):
    label: str
    failure: str | None

    def probe(self) -> bool: ...
    def idle_seconds(self) -> float | None: ...
    def set_timeout(self, seconds: int) -> None: ...
    def close(self) -> None: ...


class MutterBackend:
    """GNOME: ``org.gnome.Mutter.IdleMonitor.GetIdletime`` over D-Bus (QtDBus)."""

    label = "GNOME Mutter D-Bus"
    SERVICE = "org.gnome.Mutter.IdleMonitor"
    PATH = "/org/gnome/Mutter/IdleMonitor/Core"
    IFACE = "org.gnome.Mutter.IdleMonitor"

    def __init__(self) -> None:
        self._iface = None
        self.failure: str | None = None

    def probe(self) -> bool:
        try:
            from PySide6.QtDBus import QDBusConnection, QDBusInterface
        except ImportError:
            self.failure = "QtDBus is not available in this PySide6 build."
            return False
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            self.failure = "No D-Bus session bus."
            return False
        iface = QDBusInterface(self.SERVICE, self.PATH, self.IFACE, bus)
        if not iface.isValid():
            self.failure = "GNOME Mutter idle monitor is not on the session bus."
            return False
        self._iface = iface
        if self.idle_seconds() is None:
            self._iface = None
            self.failure = "Mutter idle monitor did not answer GetIdletime."
            return False
        return True

    def idle_seconds(self) -> float | None:
        if self._iface is None:
            return None
        arguments = self._iface.call("GetIdletime").arguments()
        if not arguments:
            return None
        try:
            return int(arguments[0]) / 1000.0
        except (TypeError, ValueError):
            return None

    def set_timeout(self, seconds: int) -> None:
        """Polling backend: nothing to configure."""

    def close(self) -> None:
        self._iface = None


class SwayidleBackend:
    """Any compositor with ``ext-idle-notify-v1``, through the ``swayidle`` helper."""

    label = "ext-idle-notify-v1 (swayidle)"

    def __init__(self, timeout: int = 60) -> None:
        self._timeout = max(1, int(timeout))
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._idle_since: float | None = None
        self._warned = False
        self.failure: str | None = None

    def probe(self) -> bool:
        if not shutil.which("swayidle"):
            self.failure = "'swayidle' is not installed."
            return False
        return self._spawn()

    def _spawn(self) -> bool:
        self.close()
        try:
            proc = subprocess.Popen(
                ["swayidle", "-w", "timeout", str(self._timeout), "echo IDLE",
                 "resume", "echo ACTIVE"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
            )
        except OSError as exc:
            self.failure = f"Cannot start swayidle: {exc}"
            return False
        try:  # swayidle exits at once if the compositor lacks the protocol
            proc.wait(timeout=0.4)
        except subprocess.TimeoutExpired:
            pass
        else:
            err = (proc.stderr.read() if proc.stderr else "").strip().splitlines()
            self.failure = "swayidle exited: " + (err[-1] if err else "protocol unsupported?")
            return False
        self._proc = proc
        self._idle_since = None
        threading.Thread(target=self._reader, args=(proc,), daemon=True).start()
        return True

    def _reader(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            token = line.strip()
            with self._lock:
                if token == "IDLE":
                    self._idle_since = time.monotonic() - self._timeout
                elif token == "ACTIVE":
                    self._idle_since = None

    def idle_seconds(self) -> float | None:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            if not self._warned:
                log.warning("swayidle stopped; idle detection lost")
                self._warned = True
            return None
        with self._lock:
            since = self._idle_since
        return 0.0 if since is None else time.monotonic() - since

    def set_timeout(self, seconds: int) -> None:
        seconds = max(1, int(seconds))
        if seconds != self._timeout:
            self._timeout = seconds
            if self._proc is not None:
                self._spawn()

    def close(self) -> None:
        proc, self._proc = self._proc, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()


class WaylandIdleDetector(IdleDetector):
    """Picks the first working Wayland strategy; unavailable if none works."""

    name = "Wayland"

    def __init__(
        self, desktop: str = "", timeout: int = 60, backends: list[WaylandBackend] | None = None
    ) -> None:
        self._desktop = desktop
        self._backend: WaylandBackend | None = None
        self._failures: list[str] = []
        candidates = backends if backends is not None else [
            MutterBackend(), SwayidleBackend(timeout)
        ]
        for backend in candidates:
            if backend.probe():
                self._backend = backend
                self.name = f"Wayland ({backend.label})"
                break
            self._failures.append(f"{backend.label}: {backend.failure}")
        for other in candidates:
            if other is not self._backend:
                other.close()

    def is_available(self) -> bool:
        return self._backend is not None

    @property
    def unavailable_reason(self) -> str | None:
        if self._backend is not None:
            return None
        hint = (
            "Install 'swayidle' (needs a compositor with ext-idle-notify-v1) "
            "or log into an X11 session."
        )
        return f"No Wayland idle source works on {self._desktop or 'this compositor'} " \
               f"({'; '.join(self._failures)}). {hint}"

    def get_idle_seconds(self) -> float | None:
        return self._backend.idle_seconds() if self._backend else None

    def set_timeout(self, seconds: int) -> None:
        if self._backend:
            self._backend.set_timeout(seconds)

    def close(self) -> None:
        if self._backend:
            self._backend.close()
