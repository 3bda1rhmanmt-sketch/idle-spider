"""Unix signal -> Qt event loop bridge (no polling timers)."""

from __future__ import annotations

import signal
import socket
from collections.abc import Callable

from PySide6.QtCore import QObject, QSocketNotifier


class SignalBridge(QObject):
    """Calls ``callback`` when SIGINT/SIGTERM arrives, without wake-up timers."""

    def __init__(self, callback: Callable[[], None]) -> None:
        super().__init__()
        self._read, self._write = socket.socketpair()
        self._read.setblocking(False)
        self._write.setblocking(False)
        signal.set_wakeup_fd(self._write.fileno())
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: None)
        self._notifier = QSocketNotifier(self._read.fileno(), QSocketNotifier.Type.Read, self)
        self._notifier.activated.connect(lambda *_: self._fire(callback))

    def _fire(self, callback: Callable[[], None]) -> None:
        try:
            self._read.recv(64)
        except OSError:
            pass
        callback()
