"""Idle detection abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod


class IdleDetector(ABC):
    """Reports how long the user has been inactive (keyboard + pointer)."""

    #: Human readable backend name, e.g. ``"X11 (XScreenSaver)"``.
    name: str = "unknown"
    #: False if the backend cannot tell when the user comes back.
    reports_activity: bool = True

    @abstractmethod
    def is_available(self) -> bool:
        """True if this backend works in the current session."""

    @abstractmethod
    def get_idle_seconds(self) -> float | None:
        """Seconds since the last user input, or None if unknown right now."""

    @property
    def unavailable_reason(self) -> str | None:
        """Why the backend is unusable (None if it is available)."""
        return None

    @property
    def status_message(self) -> str | None:
        """A message worth showing to the user (None when everything is fine)."""
        return None

    def set_timeout(self, seconds: int) -> None:  # noqa: B027 - optional hook
        """Inform event-driven backends of the configured idle timeout."""

    def close(self) -> None:  # noqa: B027 - optional hook
        """Release any resources."""
