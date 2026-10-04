"""Backend selection."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from ..utils.platform import SessionInfo, SessionType
from .base import IdleDetector
from .fallback import FallbackIdleDetector
from .wayland import WaylandIdleDetector
from .x11 import X11IdleDetector

log = logging.getLogger(__name__)

DetectorFactory = Callable[[], IdleDetector]


def default_factories(session: SessionInfo, timeout: int) -> list[DetectorFactory]:
    """Ordered candidates for this session. X11 is never tried on Wayland sessions
    because XScreenSaver on XWayland only sees X11 clients' input."""
    wayland: DetectorFactory = lambda: WaylandIdleDetector(session.desktop, timeout)  # noqa: E731
    x11: DetectorFactory = X11IdleDetector
    if session.session is SessionType.WAYLAND:
        return [wayland]
    if session.session is SessionType.X11:
        return [x11]
    factories: list[DetectorFactory] = []
    if session.has_x_display:
        factories.append(x11)
    if session.has_wayland_display:
        factories.append(wayland)
    return factories


def select_detector(
    session: SessionInfo,
    timeout: int = 60,
    factories: Sequence[DetectorFactory] | None = None,
) -> IdleDetector:
    """Return the first working detector, else a safe fallback."""
    candidates = list(factories) if factories is not None else default_factories(session, timeout)
    reasons: list[str] = []
    for factory in candidates:
        try:
            detector = factory()
        except Exception:  # a broken backend must never crash the app
            log.exception("Idle backend failed to initialise")
            reasons.append("backend crashed during initialisation")
            continue
        if detector.is_available():
            log.info("Using idle backend: %s", detector.name)
            return detector
        reason = detector.unavailable_reason or "unavailable"
        log.warning("Idle backend %s unavailable: %s", detector.name, reason)
        reasons.append(reason)
        detector.close()
    reason = " ".join(reasons) if reasons else "no graphical session was detected."
    fallback = FallbackIdleDetector(reason)
    log.warning("Using idle backend: %s", fallback.name)
    return fallback
