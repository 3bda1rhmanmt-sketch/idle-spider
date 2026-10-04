"""Logging setup. All project loggers are children of ``idle_spider``."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "idle_spider"
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def log_file_path() -> Path:
    """Return the log file location (XDG state directory)."""
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "idle-spider" / "idle-spider.log"


def setup_logging(debug: bool = False, log_to_file: bool = True) -> None:
    """Configure console (and rotating file) logging. Never logs personal data."""
    root = logging.getLogger(LOGGER_NAME)
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    root.handlers.clear()
    root.propagate = False
    formatter = logging.Formatter(_FORMAT)

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    if log_to_file:
        path = log_file_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                path, maxBytes=256_000, backupCount=2, encoding="utf-8"
            )
            handler.setFormatter(formatter)
            root.addHandler(handler)
        except OSError as exc:
            root.warning("Cannot write log file %s: %s", path, exc)
