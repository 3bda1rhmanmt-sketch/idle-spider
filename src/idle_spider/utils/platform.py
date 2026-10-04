"""Session / desktop environment detection (pure, testable)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class SessionType(StrEnum):
    X11 = "x11"
    WAYLAND = "wayland"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SessionInfo:
    session: SessionType
    desktop: str
    has_x_display: bool
    has_wayland_display: bool


_KNOWN_DESKTOPS = {
    "GNOME": "GNOME", "KDE": "KDE", "XFCE": "XFCE", "X-CINNAMON": "CINNAMON",
    "CINNAMON": "CINNAMON", "MATE": "MATE", "LXQT": "LXQT", "LXDE": "LXDE",
    "BUDGIE": "BUDGIE", "DEEPIN": "DEEPIN", "PANTHEON": "PANTHEON", "COSMIC": "COSMIC",
    "SWAY": "SWAY", "HYPRLAND": "HYPRLAND", "UNITY": "UNITY",
}


def normalize_desktop(raw: str) -> str:
    """Turn e.g. ``ubuntu:GNOME`` or ``X-Cinnamon`` into a canonical name."""
    tokens = [t.strip().upper() for t in raw.replace(";", ":").split(":") if t.strip()]
    for token in tokens:
        if token in _KNOWN_DESKTOPS:
            return _KNOWN_DESKTOPS[token]
    return tokens[0] if tokens else "UNKNOWN"


def detect_session(env: Mapping[str, str] | None = None) -> SessionInfo:
    """Detect X11 vs Wayland and the desktop environment from the environment."""
    env = os.environ if env is None else env
    declared = env.get("XDG_SESSION_TYPE", "").lower()
    wayland = bool(env.get("WAYLAND_DISPLAY"))
    x_display = bool(env.get("DISPLAY"))

    if declared == "wayland":
        session = SessionType.WAYLAND
    elif declared == "x11":
        session = SessionType.X11
    elif wayland:
        session = SessionType.WAYLAND
    elif x_display:
        session = SessionType.X11
    else:
        session = SessionType.UNKNOWN

    raw_desktop = env.get("XDG_CURRENT_DESKTOP") or env.get("DESKTOP_SESSION") or ""
    return SessionInfo(session, normalize_desktop(raw_desktop), x_display, wayland)
