"""XDG autostart (``~/.config/autostart``) management."""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_TEMPLATE = """[Desktop Entry]
Type=Application
Name=Idle Spider
Comment=A tiny spider weaves webs while you are away
Exec={exec_line}
Icon=idle-spider
Terminal=false
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""


def autostart_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / "idle-spider.desktop"


def _quote(arg: str) -> str:
    if any(c in arg for c in ' \t"\\`$'):
        escaped = (
            arg.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
        )
        return f'"{escaped}"'
    return arg


def build_exec_line() -> str:
    """Prefer the installed ``idle-spider`` script, else ``python -m idle_spider``."""
    script = shutil.which("idle-spider")
    if script:
        return _quote(script)
    return f"{_quote(sys.executable)} -m idle_spider"


def is_autostart_enabled() -> bool:
    return autostart_path().is_file()


def set_autostart(enabled: bool) -> bool:
    """Create or remove the autostart entry. Returns True on success."""
    path = autostart_path()
    try:
        if enabled:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_TEMPLATE.format(exec_line=build_exec_line()), encoding="utf-8")
            log.info("Autostart enabled (%s)", path)
        elif path.exists():
            path.unlink()
            log.info("Autostart disabled")
        return True
    except OSError as exc:
        log.warning("Cannot update autostart entry: %s", exc)
        return False
