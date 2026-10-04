"""Last-resort detector: never crashes, never guesses."""

from __future__ import annotations

from .base import IdleDetector


class FallbackIdleDetector(IdleDetector):
    """Used when no real idle source exists.

    Automatic triggering is disabled (guessing idleness from unreliable data would
    start the spider while you work). The animation can still be started manually from
    the tray, ``--test`` or ``Start Animation Now``; it then stops by itself after a limit.
    """

    name = "Fallback (manual only)"
    reports_activity = False

    def __init__(self, reason: str = "no idle detection backend available") -> None:
        self._reason = reason

    def is_available(self) -> bool:
        return True

    def get_idle_seconds(self) -> float | None:
        return None

    @property
    def status_message(self) -> str | None:
        return (
            f"Idle detection is unavailable: {self._reason} "
            "Automatic mode is disabled; use the tray menu to start the animation manually."
        )
