"""X11 idle detection via the XScreenSaver extension (ctypes, no extra Python deps)."""

from __future__ import annotations

import ctypes
import logging
import os
import shutil
import subprocess
from collections.abc import Callable
from ctypes import POINTER, c_char_p, c_int, c_ulong, c_void_p
from ctypes.util import find_library

from .base import IdleDetector

log = logging.getLogger(__name__)


class _XScreenSaverInfo(ctypes.Structure):
    _fields_ = [
        ("window", c_ulong),
        ("state", c_int),
        ("kind", c_int),
        ("til_or_since", c_ulong),
        ("idle", c_ulong),
        ("event_mask", c_ulong),
    ]


class X11IdleDetector(IdleDetector):
    """Uses libXss (``XScreenSaverQueryInfo``); falls back to the ``xprintidle`` tool."""

    name = "X11"

    def __init__(self) -> None:
        self._query: Callable[[], float | None] | None = None
        self._reason: str | None = None
        self._xlib: ctypes.CDLL | None = None
        self._xss: ctypes.CDLL | None = None
        self._display: int | None = None
        self._root = 0
        self._info = None
        self._setup()

    # -- setup ---------------------------------------------------------
    def _setup(self) -> None:
        if not os.environ.get("DISPLAY"):
            self._reason = "DISPLAY is not set (no X11 server reachable)."
            return
        if self._setup_xss() or self._setup_xprintidle():
            return
        self._reason = (
            "Neither libXss (XScreenSaver extension) nor the 'xprintidle' tool was found. "
            "Install libxss1 (Debian/Ubuntu), libXScrnSaver (Fedora) or libxss (Arch)."
        )

    def _setup_xss(self) -> bool:
        x11_name, xss_name = find_library("X11"), find_library("Xss")
        if not (x11_name and xss_name):
            return False
        try:
            xlib, xss = ctypes.CDLL(x11_name), ctypes.CDLL(xss_name)
            xlib.XOpenDisplay.argtypes = [c_char_p]
            xlib.XOpenDisplay.restype = c_void_p
            xlib.XDefaultRootWindow.argtypes = [c_void_p]
            xlib.XDefaultRootWindow.restype = c_ulong
            xlib.XCloseDisplay.argtypes = [c_void_p]
            xlib.XCloseDisplay.restype = c_int
            xlib.XFree.argtypes = [c_void_p]
            xss.XScreenSaverAllocInfo.restype = POINTER(_XScreenSaverInfo)
            xss.XScreenSaverQueryInfo.argtypes = [c_void_p, c_ulong, POINTER(_XScreenSaverInfo)]
            xss.XScreenSaverQueryInfo.restype = c_int
        except (OSError, AttributeError) as exc:
            log.debug("libXss unusable: %s", exc)
            return False

        display = xlib.XOpenDisplay(None)
        if not display:
            return False
        info = xss.XScreenSaverAllocInfo()
        root = xlib.XDefaultRootWindow(display)
        if not info or not xss.XScreenSaverQueryInfo(display, root, info):
            xlib.XCloseDisplay(display)
            return False
        self._xlib, self._xss = xlib, xss
        self._display, self._root, self._info = display, root, info
        self._query = self._query_xss
        self.name = "X11 (XScreenSaver)"
        return True

    def _setup_xprintidle(self) -> bool:
        if not shutil.which("xprintidle"):
            return False
        if self._query_xprintidle() is None:
            return False
        self._query = self._query_xprintidle
        self.name = "X11 (xprintidle)"
        return True

    # -- queries -------------------------------------------------------
    def _query_xss(self) -> float | None:
        assert self._xss is not None
        if not self._xss.XScreenSaverQueryInfo(self._display, self._root, self._info):
            return None
        return self._info.contents.idle / 1000.0

    @staticmethod
    def _query_xprintidle() -> float | None:
        try:
            out = subprocess.run(
                ["xprintidle"], capture_output=True, text=True, timeout=2, check=True
            ).stdout
            return int(out.strip()) / 1000.0
        except (OSError, subprocess.SubprocessError, ValueError):
            return None

    # -- IdleDetector API ---------------------------------------------
    def is_available(self) -> bool:
        return self._query is not None

    @property
    def unavailable_reason(self) -> str | None:
        return None if self.is_available() else self._reason

    def get_idle_seconds(self) -> float | None:
        return self._query() if self._query else None

    def close(self) -> None:
        if self._xlib is not None and self._display:
            if self._info:
                self._xlib.XFree(self._info)
            self._xlib.XCloseDisplay(self._display)
        self._xlib = self._xss = self._display = self._info = None
        self._query = None
