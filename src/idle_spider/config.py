"""User configuration: validated dataclass + JSON persistence (XDG)."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right", "random")
MONITOR_MODES = ("current", "all", "random")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "idle-spider"


def config_path() -> Path:
    return config_dir() / "config.json"


def _as_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, number))


def _as_float(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, number))


@dataclass
class Config:
    """All user-tunable settings."""

    enabled: bool = True
    idle_timeout: int = 60          # seconds
    spider_color: str = "#000000"
    web_color: str = "#bdbdbd"
    web_opacity: float = 0.55       # 0.05 .. 1.0
    spider_size: int = 14           # body scale in logical px
    animation_speed: float = 1.0    # multiplier
    web_density: int = 5            # 1 .. 10
    start_corner: str = "top_left"
    monitor_mode: str = "current"
    autostart: bool = False
    max_webs: int = 4

    def normalize(self) -> Config:
        """Clamp / repair every field in place and return self."""
        d = Config.__new__(Config)
        d.__dict__.update({f.name: f.default for f in fields(Config)})
        self.enabled = bool(self.enabled)
        self.autostart = bool(self.autostart)
        self.idle_timeout = _as_int(self.idle_timeout, d.idle_timeout, 5, 86_400)
        self.spider_size = _as_int(self.spider_size, d.spider_size, 8, 48)
        self.web_density = _as_int(self.web_density, d.web_density, 1, 10)
        self.max_webs = _as_int(self.max_webs, d.max_webs, 1, 12)
        self.web_opacity = _as_float(self.web_opacity, d.web_opacity, 0.05, 1.0)
        self.animation_speed = _as_float(self.animation_speed, d.animation_speed, 0.25, 3.0)
        for name in ("spider_color", "web_color"):
            if not (isinstance(getattr(self, name), str) and _HEX.match(getattr(self, name))):
                setattr(self, name, getattr(d, name))
        if self.start_corner not in CORNERS:
            self.start_corner = d.start_corner
        if self.monitor_mode not in MONITOR_MODES:
            self.monitor_mode = d.monitor_mode
        return self

    @classmethod
    def from_dict(cls, data: Any) -> Config:
        cfg = cls()
        if isinstance(data, dict):
            for f in fields(cls):
                if f.name in data:
                    setattr(cfg, f.name, data[f.name])
        return cfg.normalize()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConfigStore:
    """Loads and atomically saves the configuration file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config_path()
        self.config = self.load()

    def load(self) -> Config:
        if not self.path.exists():
            return Config()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Invalid config %s (%s); using defaults", self.path, exc)
            try:
                self.path.replace(self.path.with_suffix(".json.bak"))
            except OSError:
                pass
            return Config()
        return Config.from_dict(data)

    def save(self, config: Config | None = None) -> bool:
        if config is not None:
            self.config = config
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".config-", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self.config.to_dict(), handle, indent=2)
                handle.write("\n")
            os.replace(tmp, self.path)
            return True
        except OSError as exc:
            log.error("Cannot save config %s: %s", self.path, exc)
            return False
