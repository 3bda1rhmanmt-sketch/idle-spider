"""Spider model: position, smooth heading and a procedural 8-leg gait (no GUI code)."""

from __future__ import annotations

import math

from .movement import Vec, clamp, wrap_angle

_LEG_ANGLES = tuple(math.radians(a) for a in (48, 78, 108, 138))
_HIP_X = (0.30, 0.14, -0.04, -0.22)
_TURN_RATE = 9.0   # rad/s


class Spider:
    """Faces +x in local space; ``legs()`` returns hip/knee/foot points per leg."""

    def __init__(self, pos: Vec, size: float) -> None:
        self.pos: Vec = pos
        self.size = float(size)
        self.heading = 0.0
        self.gait_phase = 0.0

    def face(self, target: Vec) -> None:
        self.heading = math.atan2(target[1] - self.pos[1], target[0] - self.pos[0])

    def update(self, dt: float, new_pos: Vec) -> None:
        """Move to ``new_pos``, turning smoothly and advancing the gait by distance."""
        dx, dy = new_pos[0] - self.pos[0], new_pos[1] - self.pos[1]
        moved = math.hypot(dx, dy)
        if moved > 1e-4:
            desired = math.atan2(dy, dx)
            limit = _TURN_RATE * dt
            self.heading = wrap_angle(
                self.heading + clamp(wrap_angle(desired - self.heading), -limit, limit)
            )
            self.gait_phase = (self.gait_phase + 2 * math.pi * moved / (self.size * 3.0)) % (
                2 * math.pi
            )
        self.pos = new_pos

    def legs(self) -> list[list[Vec]]:
        s = self.size
        legs: list[list[Vec]] = []
        for i in range(4):
            for side in (1, -1):
                phase = self.gait_phase + math.pi * ((i + (side > 0)) % 2)
                a = _LEG_ANGLES[i] + 0.28 * math.sin(phase)
                hip = (_HIP_X[i] * s, side * 0.12 * s)
                knee = (hip[0] + math.cos(a) * 0.60 * s, hip[1] + side * math.sin(a) * 0.60 * s)
                a2 = a + (math.pi / 2 - a) * 0.55
                foot = (knee[0] + math.cos(a2) * 0.75 * s, knee[1] + side * math.sin(a2) * 0.75 * s)
                legs.append([hip, knee, foot])
        return legs
