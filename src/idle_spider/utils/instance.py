"""Single-instance guard based on a local (Unix) socket."""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

log = logging.getLogger(__name__)

COMMANDS = frozenset({"show", "settings", "test", "start", "stop", "quit"})


class InstanceGuard(QObject):
    """First instance listens; later instances send a command and exit."""

    command_received = Signal(str)

    def __init__(self, name: str | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._name = name or f"idle-spider-{os.getuid()}"
        self._server: QLocalServer | None = None

    def send(self, command: str, timeout_ms: int = 500) -> bool:
        """Send a command to a running instance. False if none is running."""
        sock = QLocalSocket()
        sock.connectToServer(self._name)
        if not sock.waitForConnected(timeout_ms):
            return False
        sock.write(command.encode("utf-8") + b"\n")
        sock.flush()
        sock.waitForBytesWritten(timeout_ms)
        sock.disconnectFromServer()
        return True

    def listen(self) -> bool:
        """Become the primary instance."""
        QLocalServer.removeServer(self._name)  # drop stale socket from a crash
        server = QLocalServer(self)
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not server.listen(self._name):
            log.warning("Single-instance socket unavailable: %s", server.errorString())
            return False
        server.newConnection.connect(self._on_new_connection)
        self._server = server
        return True

    def _on_new_connection(self) -> None:
        assert self._server is not None
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            sock.readyRead.connect(lambda s=sock: self._read(s))
            sock.disconnected.connect(sock.deleteLater)
            if sock.bytesAvailable():
                self._read(sock)

    def _read(self, sock: QLocalSocket) -> None:
        text = bytes(sock.readAll()).decode("utf-8", "ignore")
        for line in text.splitlines():
            command = line.strip()
            if command in COMMANDS:
                self.command_received.emit(command)
