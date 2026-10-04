"""Animation engine (GUI independent): scenes per monitor, spider behaviour, fade-out."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum

from ..config import Config
from .movement import Vec, Wanderer, clamp, dist, ease_out_cubic
from .spider import Spider
from .web import Web

WALK_SPEED = 150.0      # px/s while searching
BUILD_SPEED = 190.0     # px/s while laying thread
RETRACE_SPEED = 420.0   # px/s while walking over existing thread
FADE_SECONDS = 0.8


@dataclass(frozen=True)
class ScreenInfo:
    index: int
    width: float
    height: float


@dataclass(frozen=True)
class AnimationSettings:
    spider_size: int = 14
    speed: float = 1.0
    density: int = 5
    start_corner: str = "top_left"
    max_webs: int = 4

    @classmethod
    def from_config(cls, config: Config) -> AnimationSettings:
        return cls(config.spider_size, config.animation_speed, config.web_density,
                   config.start_corner, config.max_webs)


class SceneState(Enum):
    TRAVELING = "traveling"
    BUILDING = "building"
    RESTING = "resting"


class Scene:
    """One monitor: a spider that wanders to a spot, builds a web, then moves on."""

    def __init__(self, screen: ScreenInfo, settings: AnimationSettings, rng: random.Random):
        self.screen = screen
        self.settings = settings
        self.rng = rng
        self.width, self.height = screen.width, screen.height
        self.base_radius = min(clamp(min(self.width, self.height) * 0.17, 60.0, 230.0),
                               min(self.width, self.height) / 2.6)
        corner = settings.start_corner
        if corner == "random":
            corner = rng.choice(("top_left", "top_right", "bottom_left", "bottom_right"))
        start = self._corner_point(corner)
        self.spider = Spider(start, settings.spider_size)
        self.webs: list[Web] = []
        self.active_web: Web | None = None
        self.completed_version = 0
        self.state = SceneState.TRAVELING
        self._wanderer = Wanderer(start, rng)
        self._pending: Web | None = None
        self._targets: list[Vec] = []
        self._plan_next_web(first=True)

    # -- planning ------------------------------------------------------
    def _corner_point(self, corner: str) -> Vec:
        m = self.settings.spider_size * 3.0
        x = -m if corner.endswith("left") else self.width + m
        y = -m if corner.startswith("top") else self.height + m
        return (x, y)

    def _choose_site(self, radius: float) -> Vec:
        margin = radius * 1.2
        best, best_gap = (self.width / 2, self.height / 2), -math.inf
        for _ in range(40):
            p = (self.rng.uniform(margin, self.width - margin),
                 self.rng.uniform(margin, self.height - margin))
            gap = min((dist(p, w.center) - w.radius - radius for w in self.webs),
                      default=math.inf)
            if gap >= -0.2 * radius:
                return p
            if gap > best_gap:
                best, best_gap = p, gap
        return best

    def _plan_next_web(self, first: bool = False) -> None:
        radius = self.base_radius * self.rng.uniform(0.8, 1.1)
        center = self._choose_site(radius)
        self._pending = Web(center, radius, self.settings.density, self.rng)
        self._targets = []
        if not first and self.rng.random() < 0.6:   # look around before settling
            self._targets.append((self.rng.uniform(0, self.width), self.rng.uniform(0, self.height)))
        self._targets.append(self._pending.start_point)
        self.state = SceneState.TRAVELING
        self._next_leg()

    def _next_leg(self) -> None:
        target = self._targets.pop(0)
        self._wanderer.travel_to(target, WALK_SPEED * self.settings.speed)
        if self.spider.pos != target:
            self.spider.face(target)

    # -- simulation ----------------------------------------------------
    @property
    def settled(self) -> bool:
        return self.state is SceneState.RESTING

    def update(self, dt: float) -> None:
        if self.state is SceneState.TRAVELING:
            arrived = self._wanderer.update(dt)
            self.spider.update(dt, self._wanderer.pos)
            if arrived:
                if self._targets:
                    self._next_leg()
                else:
                    self.active_web, self._pending = self._pending, None
                    self.state = SceneState.BUILDING
        elif self.state is SceneState.BUILDING:
            web = self.active_web
            assert web is not None
            speed = (BUILD_SPEED if web.current_visible else RETRACE_SPEED) * self.settings.speed
            done = web.advance(speed * dt)
            self.spider.update(dt, web.position())
            if done:
                self.webs.append(web)
                self.active_web = None
                self.completed_version += 1
                self._wanderer.pos = self.spider.pos
                if len(self.webs) >= self.settings.max_webs:
                    self.state = SceneState.RESTING
                else:
                    self._plan_next_web()

    def dirty_rect(self) -> tuple[float, float, float, float]:
        """(x, y, w, h) that may change this frame: spider + active web."""
        pad = self.spider.size * 2.4
        x0, y0 = self.spider.pos[0] - pad, self.spider.pos[1] - pad
        x1, y1 = self.spider.pos[0] + pad, self.spider.pos[1] + pad
        if self.active_web is not None:
            bx0, by0, bx1, by1 = self.active_web.bounds
            x0, y0, x1, y1 = min(x0, bx0 - 3), min(y0, by0 - 3), max(x1, bx1 + 3), max(y1, by1 + 3)
        return (x0, y0, x1 - x0, y1 - y0)


class AnimationController:
    """Owns the scenes and the global fade-out."""

    def __init__(self, settings: AnimationSettings, rng: random.Random | None = None) -> None:
        self.settings = settings
        self.rng = rng or random.Random()
        self.scenes: dict[int, Scene] = {}
        self.running = False
        self.fading = False
        self.fade_alpha = 1.0
        self._fade_elapsed = 0.0
        self._fade_duration = FADE_SECONDS

    def start(self, screens: list[ScreenInfo]) -> None:
        self.scenes = {s.index: Scene(s, self.settings, self.rng) for s in screens}
        self.running = True
        self.fading = False
        self.fade_alpha = 1.0
        self._fade_elapsed = 0.0

    def update(self, dt: float) -> None:
        if not self.running:
            return
        dt = clamp(dt, 0.0, 0.1)          # never let a stall teleport the spider
        if not self.fading:
            for scene in self.scenes.values():
                scene.update(dt)
        else:
            self._fade_elapsed += dt
            self.fade_alpha = 1.0 - ease_out_cubic(self._fade_elapsed / self._fade_duration)

    def begin_fade(self, duration: float = FADE_SECONDS) -> None:
        if self.running and not self.fading:
            self.fading = True
            self._fade_duration = max(duration, 0.01)
            self._fade_elapsed = 0.0

    @property
    def fade_finished(self) -> bool:
        return self.fading and self._fade_elapsed >= self._fade_duration

    @property
    def settled(self) -> bool:
        return self.running and bool(self.scenes) and all(s.settled for s in self.scenes.values())

    def stop(self) -> None:
        self.scenes.clear()
        self.running = False
        self.fading = False
        self.fade_alpha = 1.0
