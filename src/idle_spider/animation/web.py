"""A single spider web: geometry + incremental construction.

The construction path is also the spider's walking path, so the spider is always
exactly where the thread is being laid. Order: frame -> radial threads -> spiral.
"""

from __future__ import annotations

import math
import random
from bisect import bisect_right
from collections.abc import Iterator
from dataclasses import dataclass

from .movement import Vec


@dataclass(frozen=True)
class Segment:
    a: Vec
    b: Vec
    visible: bool  # False = spider retraces an existing thread

    @property
    def length(self) -> float:
        return math.hypot(self.b[0] - self.a[0], self.b[1] - self.a[1])


class Web:
    def __init__(self, center: Vec, radius: float, density: int, rng: random.Random) -> None:
        self.center = center
        self.radius = radius
        self.density = max(1, min(10, density))
        self.anchors: list[Vec] = []
        self.hub: Vec = center
        self.segments: list[Segment] = []
        self.progress = 0.0
        self._starts: list[float] = []
        self.total_length = 0.0
        self._build(rng)

    # -- geometry ------------------------------------------------------
    def _build(self, rng: random.Random) -> None:
        cx, cy = self.center
        n = 7 + self.density                      # number of radial threads
        step = 2 * math.pi / n
        base = rng.uniform(0, 2 * math.pi)
        for i in range(n):
            ang = base + i * step + rng.uniform(-0.22, 0.22) * step
            r = self.radius * rng.uniform(0.86, 1.14)
            self.anchors.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
        self.hub = (cx + rng.uniform(-0.06, 0.06) * self.radius,
                    cy + rng.uniform(-0.06, 0.06) * self.radius)
        anchors, hub = self.anchors, self.hub
        add = lambda a, b, vis: self.segments.append(Segment(a, b, vis))  # noqa: E731

        for i in range(n):                         # 1. frame
            add(anchors[i], anchors[(i + 1) % n], True)
        add(anchors[0], hub, True)                 # 2. radial threads
        for i in range(1, n):
            add(hub, anchors[i], True)
            add(anchors[i], hub, False)

        turns = 3.0 + 0.55 * self.density          # 3. spiral
        total = int(n * turns)
        inner, outer = 0.10, 0.94

        def spoke_point(k: int) -> Vec:
            ax, ay = anchors[k % n]
            f = inner + (outer - inner) * (k + 1) / total
            return (hub[0] + (ax - hub[0]) * f, hub[1] + (ay - hub[1]) * f)

        prev = spoke_point(0)
        add(hub, prev, False)
        for k in range(1, total):
            cur = spoke_point(k)
            add(prev, cur, True)
            prev = cur

        acc = 0.0
        for seg in self.segments:
            self._starts.append(acc)
            acc += seg.length
        self.total_length = acc

    @property
    def start_point(self) -> Vec:
        return self.anchors[0]

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        xs = [p[0] for p in self.anchors]
        ys = [p[1] for p in self.anchors]
        return min(xs), min(ys), max(xs), max(ys)

    # -- construction --------------------------------------------------
    @property
    def complete(self) -> bool:
        return self.progress >= self.total_length

    def advance(self, distance: float) -> bool:
        """Lay ``distance`` pixels of thread. Returns True when finished."""
        self.progress = min(self.total_length, self.progress + max(0.0, distance))
        return self.complete

    def _index(self) -> int:
        return min(len(self.segments) - 1, max(0, bisect_right(self._starts, self.progress) - 1))

    @property
    def current_visible(self) -> bool:
        """True while the spider is laying new thread (False while retracing)."""
        return self.segments[self._index()].visible

    def position(self) -> Vec:
        """Where the spider currently is."""
        i = self._index()
        seg = self.segments[i]
        length = seg.length
        t = 1.0 if length <= 0 else min(1.0, (self.progress - self._starts[i]) / length)
        return (seg.a[0] + (seg.b[0] - seg.a[0]) * t, seg.a[1] + (seg.b[1] - seg.a[1]) * t)

    def lines(self) -> Iterator[tuple[float, float, float, float]]:
        """Visible thread laid so far as (x1, y1, x2, y2); the last may be partial."""
        for i, seg in enumerate(self.segments):
            start = self._starts[i]
            if start >= self.progress:
                break
            if not seg.visible:
                continue
            length = seg.length
            frac = 1.0 if length <= 0 else min(1.0, (self.progress - start) / length)
            yield (
                seg.a[0], seg.a[1],
                seg.a[0] + (seg.b[0] - seg.a[0]) * frac,
                seg.a[1] + (seg.b[1] - seg.a[1]) * frac,
            )
