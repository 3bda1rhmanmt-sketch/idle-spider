# Architecture

```text
MONITORING -> IDLE_DETECTED -> ANIMATING -> USER_ACTIVITY -> FADE_OUT -> MONITORING
```

* `idle/` – `IdleDetector` ABC + `X11IdleDetector`, `WaylandIdleDetector` (Mutter / swayidle),
  `FallbackIdleDetector`; `detector.select_detector()` picks one at runtime.
* `animation/` – GUI-free engine: `movement` (Bezier/easing/Wanderer), `web` (geometry +
  progressive construction), `spider` (heading + gait), `controller` (Scene per monitor, fade).
* `ui/` – `overlay` (transparent click-through window, cached finished webs, dirty-rect updates),
  `tray`, `settings`, `painting`, `icons`.
* `app.py` – coordinator (timers, state machine, overlays). `state.py`, `config.py` are pure Python.

Efficiency: monitoring is one cheap query per second (zero timers when paused/disabled/fallback);
the 16 ms frame timer exists only while animating and stops once all webs are finished.
