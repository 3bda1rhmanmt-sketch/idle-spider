# Idle detection: technical analysis

Wayland intentionally gives ordinary clients **no** global input/idle information (that would
make every app a keylogger). So there is no single method; Idle Spider probes at runtime:

| Session | Method | Notes |
|---|---|---|
| X11 (any DE) | XScreenSaver extension via `libXss` (ctypes), else `xprintidle` | Reliable. Needs `libxss1` (or `xprintidle`). |
| GNOME Wayland | `org.gnome.Mutter.IdleMonitor.GetIdletime` on the session D-Bus (QtDBus) | Polled once per second; nothing extra to install. |
| Sway, Hyprland, river, labwc, KDE Plasma 6 (reported), COSMIC… | `ext-idle-notify-v1` through the `swayidle` helper | Event driven. Needs `swayidle` and a compositor that implements the protocol. Verified at runtime: if `swayidle` exits immediately the backend is rejected. |
| Anything else | `FallbackIdleDetector` | No automatic trigger. Tray / `--test` / *Start Animation Now* still work and auto-stop after a limit. A clear message is shown. |

X11-on-XWayland is deliberately **not** used for Wayland sessions: XScreenSaver on XWayland
only sees input to X11 clients and would report "idle" while you work in native apps.

## The overlay on Wayland

Native Wayland toplevels cannot choose their position or stacking, and a fullscreen one makes
GNOME hide its top bar. On a Wayland session with XWayland present, Idle Spider therefore renders
the overlay through Qt's `xcb` plugin (an input-transparent, focus-less window), which works on
GNOME, KDE and wlroots compositors. `--native-wayland` (or `QT_QPA_PLATFORM=wayland`) forces the
native path (fullscreen, best effort). This is best-effort behaviour that depends on compositor
policy; fractional scaling under XWayland can make thin lines slightly soft.
