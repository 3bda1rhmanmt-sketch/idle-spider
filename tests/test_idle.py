from idle_spider.idle.base import IdleDetector
from idle_spider.idle.detector import default_factories, select_detector
from idle_spider.idle.fallback import FallbackIdleDetector
from idle_spider.idle.wayland import WaylandIdleDetector
from idle_spider.utils.platform import SessionType, detect_session, normalize_desktop


class Fake(IdleDetector):
    def __init__(self, name, ok, idle=1.0):
        self.name, self._ok, self._idle = name, ok, idle

    def is_available(self):
        return self._ok

    def get_idle_seconds(self):
        return self._idle if self._ok else None

    @property
    def unavailable_reason(self):
        return None if self._ok else f"{self.name} broken"


class FakeBackend:
    def __init__(self, label, ok, idle=3.0):
        self.label, self._ok, self._idle, self.failure = label, ok, idle, None if ok else "nope"
        self.timeout = None
        self.closed = False

    def probe(self):
        return self._ok

    def idle_seconds(self):
        return self._idle

    def set_timeout(self, s):
        self.timeout = s

    def close(self):
        self.closed = True


def test_session_detection():
    s = detect_session({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0",
                        "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "ubuntu:GNOME"})
    assert s.session is SessionType.WAYLAND and s.desktop == "GNOME" and s.has_x_display
    assert detect_session({"DISPLAY": ":0"}).session is SessionType.X11
    assert detect_session({}).session is SessionType.UNKNOWN
    assert normalize_desktop("X-Cinnamon") == "CINNAMON"
    assert normalize_desktop("KDE") == "KDE"


def test_default_factories_never_use_x11_on_wayland():
    wl = detect_session({"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"})
    assert len(default_factories(wl, 60)) == 1
    assert default_factories(detect_session({}), 60) == []


def test_select_first_available():
    s = detect_session({"DISPLAY": ":0"})
    d = select_detector(s, factories=[lambda: Fake("a", False), lambda: Fake("b", True)])
    assert d.name == "b"


def test_select_survives_crashing_backend_and_falls_back():
    def boom():
        raise RuntimeError("x")

    d = select_detector(detect_session({}), factories=[boom, lambda: Fake("a", False)])
    assert isinstance(d, FallbackIdleDetector)
    assert d.get_idle_seconds() is None and not d.reports_activity
    assert "unavailable" in d.status_message


def test_wayland_detector_picks_first_working_backend():
    bad, good, extra = FakeBackend("bad", False), FakeBackend("good", True), FakeBackend("x", True)
    d = WaylandIdleDetector("KDE", backends=[bad, good, extra])
    assert d.is_available() and "good" in d.name
    assert d.get_idle_seconds() == 3.0
    d.set_timeout(90)
    assert good.timeout == 90
    assert bad.closed and extra.closed


def test_wayland_detector_unavailable_has_actionable_reason():
    d = WaylandIdleDetector("KDE", backends=[FakeBackend("a", False)])
    assert not d.is_available() and d.get_idle_seconds() is None
    assert "swayidle" in d.unavailable_reason
