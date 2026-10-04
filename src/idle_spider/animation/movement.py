"""Math + organic movement: easing, Bezier paths, wandering with pauses."""

from __future__ import annotations

import math
import random

Vec = tuple[float, float]


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def dist(a: Vec, b: Vec) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def wrap_angle(angle: float) -> float:
    """Wrap to (-pi, pi]."""
    return (angle + math.pi) % (2 * math.pi) - math.pi


def ease_in_out_sine(t: float) -> float:
    return -(math.cos(math.pi * clamp(t, 0.0, 1.0)) - 1.0) / 2.0


def ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - clamp(t, 0.0, 1.0)) ** 3


def smootherstep(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t * t * (t * (t * 6 - 15) + 10)


def bezier_point(p0: Vec, p1: Vec, p2: Vec, p3: Vec, t: float) -> Vec:
    u = 1.0 - t
    a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
    return (
        a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
        a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
    )


class BezierPath:
    """Cubic Bezier with an arc-length table so speed is given in pixels/second."""

    def __init__(self, p0: Vec, p1: Vec, p2: Vec, p3: Vec, samples: int = 40) -> None:
        self.points = (p0, p1, p2, p3)
        self._samples = samples
        lut = [0.0]
        prev = p0
        for i in range(1, samples + 1):
            cur = bezier_point(p0, p1, p2, p3, i / samples)
            lut.append(lut[-1] + dist(prev, cur))
            prev = cur
        self._lut = lut
        self.length = max(lut[-1], 1e-6)

    def t_at_distance(self, s: float) -> float:
        s = clamp(s, 0.0, self.length)
        lo, hi = 0, self._samples
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self._lut[mid] <= s:
                lo = mid
            else:
                hi = mid
        span = self._lut[hi] - self._lut[lo]
        frac = 0.0 if span <= 0 else (s - self._lut[lo]) / span
        return (lo + frac) / self._samples

    def point_at_distance(self, s: float) -> Vec:
        return bezier_point(*self.points, self.t_at_distance(s))


def make_wander_path(start: Vec, end: Vec, rng: random.Random, wobble: float = 0.3) -> BezierPath:
    """A gently curving path whose control points are pushed sideways at random."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    controls = []
    for along in (rng.uniform(0.15, 0.4), rng.uniform(0.6, 0.85)):
        off = rng.uniform(-1.0, 1.0) * wobble * length
        controls.append((start[0] + dx * along + nx * off, start[1] + dy * along + ny * off))
    return BezierPath(start, controls[0], controls[1], end)


class Wanderer:
    """Moves a point along Bezier legs with speed variation and short search pauses.

    Frame independent: motion integrates ``speed * dt`` along the path.
    """

    def __init__(self, pos: Vec, rng: random.Random) -> None:
        self.pos: Vec = pos
        self._rng = rng
        self._path: BezierPath | None = None
        self._s = 0.0
        self._speed = 0.0
        self._pause = 0.0
        self._pause_at: float | None = None
        self._clock = 0.0
        self._phase = rng.uniform(0.0, 2 * math.pi)

    @property
    def moving(self) -> bool:
        return self._path is not None

    def travel_to(
        self, target: Vec, speed: float, wobble: float = 0.3, pauses: bool = True
    ) -> None:
        self._path = make_wander_path(self.pos, target, self._rng, wobble)
        self._s = 0.0
        self._speed = max(speed, 1.0)
        self._pause = 0.0
        long_enough = self._path.length > 160
        self._pause_at = (
            self._rng.uniform(0.3, 0.7) if pauses and long_enough and self._rng.random() < 0.6
            else None
        )

    def update(self, dt: float) -> bool:
        """Advance by ``dt`` seconds; True once the current leg is finished."""
        path = self._path
        if path is None:
            return True
        self._clock += dt
        if self._pause > 0.0:
            self._pause -= dt
            return False
        u = clamp(self._s / path.length, 0.0, 1.0)
        if self._pause_at is not None and u >= self._pause_at:
            self._pause = self._rng.uniform(0.25, 0.7)
            self._pause_at = None
            return False
        profile = 0.3 + 0.7 * math.sqrt(math.sin(math.pi * u))
        wobble = 1.0 + 0.25 * math.sin(2 * math.pi * 0.6 * self._clock + self._phase)
        self._s += self._speed * profile * wobble * dt
        if self._s >= path.length:
            self.pos = path.points[3]
            self._path = None
            return True
        self.pos = path.point_at_distance(self._s)
        return False
