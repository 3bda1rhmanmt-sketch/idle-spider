"""Explicit, testable application state machine."""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum

log = logging.getLogger(__name__)


class State(Enum):
    MONITORING = "monitoring"
    IDLE_DETECTED = "idle_detected"
    ANIMATING = "animating"
    USER_ACTIVITY = "user_activity"
    FADE_OUT = "fade_out"


ALLOWED: dict[State, frozenset[State]] = {
    State.MONITORING: frozenset({State.IDLE_DETECTED}),
    State.IDLE_DETECTED: frozenset({State.ANIMATING, State.MONITORING}),
    State.ANIMATING: frozenset({State.USER_ACTIVITY}),
    State.USER_ACTIVITY: frozenset({State.FADE_OUT}),
    State.FADE_OUT: frozenset({State.MONITORING}),
}

Listener = Callable[[State, State], None]


class StateMachine:
    """MONITORING -> IDLE_DETECTED -> ANIMATING -> USER_ACTIVITY -> FADE_OUT -> MONITORING."""

    def __init__(self) -> None:
        self._state = State.MONITORING
        self._listeners: list[Listener] = []

    @property
    def state(self) -> State:
        return self._state

    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def can_transition(self, target: State) -> bool:
        return target in ALLOWED[self._state]

    def transition(self, target: State) -> bool:
        """Move to ``target`` if legal. Returns False (and logs) otherwise."""
        if not self.can_transition(target):
            log.debug("Ignored illegal transition %s -> %s", self._state.name, target.name)
            return False
        previous, self._state = self._state, target
        for listener in self._listeners:
            listener(previous, target)
        return True

    def reset(self) -> None:
        """Force MONITORING (used by Reset / error recovery)."""
        previous, self._state = self._state, State.MONITORING
        if previous is not State.MONITORING:
            for listener in self._listeners:
                listener(previous, State.MONITORING)
