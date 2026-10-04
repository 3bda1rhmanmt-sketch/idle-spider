"""Command line entry point."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from . import __version__
from .utils.logger import setup_logging
from .utils.platform import SessionInfo, SessionType, detect_session

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="idle-spider",
        description="A tiny spider weaves webs on your desktop while you are away.",
    )
    p.add_argument("--settings", action="store_true", help="open the settings window")
    p.add_argument("--test", action="store_true", help="run a 20 second test animation")
    p.add_argument("--no-tray", action="store_true", help="run without a tray icon")
    p.add_argument("--debug", action="store_true", help="verbose logging")
    p.add_argument("--timeout", type=int, metavar="SECONDS",
                   help="idle timeout for this run (not saved)")
    p.add_argument("--quit", action="store_true", help="ask the running instance to quit")
    p.add_argument("--native-wayland", action="store_true",
                   help="use Qt's native Wayland backend instead of XWayland for the overlay")
    p.add_argument("--config", metavar="FILE", help="use an alternative config file")
    p.add_argument("--version", action="version", version=f"idle-spider {__version__}")
    return p


def configure_qt_platform(session: SessionInfo, native_wayland: bool = False) -> str | None:
    """Pick the Qt platform plugin before QApplication exists.

    Native Wayland clients cannot position or stack an always-on-top overlay (and a
    fullscreen one makes GNOME hide its panel). On a Wayland session with XWayland
    available we therefore render the overlay through xcb, which works on GNOME, KDE
    and wlroots compositors. Override with ``QT_QPA_PLATFORM`` or ``--native-wayland``.
    """
    if os.environ.get("QT_QPA_PLATFORM"):
        return os.environ["QT_QPA_PLATFORM"]
    if session.session is SessionType.WAYLAND and session.has_x_display and not native_wayland:
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        log.info("Wayland session: drawing the overlay through XWayland (xcb)")
        return "xcb"
    return None


def _command(args: argparse.Namespace) -> str:
    if args.quit:
        return "quit"
    if args.test:
        return "test"
    return "settings"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.debug)
    sys.excepthook = lambda t, v, tb: log.critical("Unhandled error", exc_info=(t, v, tb))

    session = detect_session()
    log.info("Detected session: %s", session.session.value.capitalize())
    log.info("Detected desktop: %s", session.desktop)
    if session.session is SessionType.UNKNOWN:
        print("idle-spider: no graphical session found (DISPLAY / WAYLAND_DISPLAY unset).",
              file=sys.stderr)
        return 1

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("idle-spider: PySide6 is required.  pip install PySide6", file=sys.stderr)
        return 2

    configure_qt_platform(session, args.native_wayland)

    from .app import AppOptions, IdleSpiderApp
    from .config import ConfigStore
    from .utils.instance import InstanceGuard
    from .utils.signals import SignalBridge

    qt_app = QApplication(sys.argv[:1])
    qt_app.setApplicationName("idle-spider")
    qt_app.setDesktopFileName("idle-spider")
    qt_app.setQuitOnLastWindowClosed(False)

    guard = InstanceGuard()
    if guard.send(_command(args)):
        log.info("Another instance is running; command forwarded")
        return 0
    if args.quit:
        print("idle-spider is not running.", file=sys.stderr)
        return 1
    guard.listen()

    store = ConfigStore(Path(args.config) if args.config else None)
    if args.timeout is not None and args.timeout < 1:
        print("idle-spider: --timeout must be >= 1", file=sys.stderr)
        return 2
    options = AppOptions(args.timeout, args.no_tray, args.settings, args.test)
    app = IdleSpiderApp(qt_app, store, options, session)
    guard.command_received.connect(app.handle_command)
    bridge = SignalBridge(app.quit)  # noqa: F841 - keep reference alive
    app.start()
    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
