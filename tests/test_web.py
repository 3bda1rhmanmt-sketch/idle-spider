import math
import random

from idle_spider.animation.web import Web


def make(seed=1, density=5):
    return Web((300, 300), 120, density, random.Random(seed))


def test_deterministic_for_seed():
    assert make(4).anchors == make(4).anchors
    assert make(4).anchors != make(5).anchors


def test_density_changes_complexity():
    assert len(make(1, 10).segments) > len(make(1, 1).segments)


def test_path_is_continuous():
    w = make()
    for a, b in zip(w.segments, w.segments[1:], strict=False):
        assert a.b == b.a
    assert w.position() == w.start_point


def test_progressive_construction():
    w = make()
    assert list(w.lines()) == []
    w.advance(5)
    partial = list(w.lines())
    assert len(partial) == 1
    x1, y1, x2, y2 = partial[0]
    assert abs(math.hypot(x2 - x1, y2 - y1) - 5) < 1e-6
    assert not w.complete
    counts = []
    while not w.complete:
        w.advance(200)
        counts.append(len(list(w.lines())))
    assert counts == sorted(counts)
    assert w.complete and w.advance(10)
    assert abs(w.progress - w.total_length) < 1e-9


def test_retrace_is_not_drawn():
    w = make()
    visible_total = sum(s.length for s in w.segments if s.visible)
    w.advance(w.total_length)
    drawn = sum(math.hypot(x2 - x1, y2 - y1) for x1, y1, x2, y2 in w.lines())
    assert abs(drawn - visible_total) < 1e-6
    assert visible_total < w.total_length


def test_web_stays_within_radius_envelope():
    w = make()
    x0, y0, x1, y1 = w.bounds
    assert x0 >= 300 - 120 * 1.15 and x1 <= 300 + 120 * 1.15
    assert y0 >= 300 - 120 * 1.15 and y1 <= 300 + 120 * 1.15
