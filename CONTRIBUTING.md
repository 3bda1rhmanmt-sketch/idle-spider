# Contributing

1. Fork, then `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`.
2. Keep the core (`animation/`, `idle/`, `config.py`, `state.py`) free of GUI code so it stays unit-testable.
3. Run `pytest` and `ruff check src tests` before opening a PR.
4. New idle backends: subclass `idle.base.IdleDetector`, add it to `idle/detector.py`, and add tests with fakes (no real compositor needed).
5. Be honest in the README about what a backend can and cannot do on each compositor.

Bug reports: include `idle-spider --debug` output (it never logs personal data), your distro, session type (`echo $XDG_SESSION_TYPE`) and desktop (`echo $XDG_CURRENT_DESKTOP`).
