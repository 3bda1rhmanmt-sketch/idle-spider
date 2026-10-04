import math
import random

from idle_spider.animation.movement import (
    BezierPath,
    Wanderer,
    bezier_point,
    ease_in_out_sine,
    ease_out_cubic,
    make_wander_path,
    smootherstep,
    wrap_angle,
)


def test_easing_bounds():
    for f in (ease_in_out_sine, ease_out_cubic, smootherstep):
        assert f(0) == 0 and abs(f(1) - 1) < 1e-9
        assert 0 <= f(0.5) <= 1
        assert f(-1) == f(0) and abs(f(2) - 1) < 1e-9


def test_wrap_angle():
    assert abs(wrap_angle(3 * math.pi) - math.pi) < 1e-9 or abs(wrap_angle(3 * math.pi) + math.pi) < 1e-9
    assert abs(wrap_angle(0.5)) == 0.5


def test_bezier_endpoints_and_length():
    p = BezierPath((0, 0), (10, 0), (20, 0), (30, 0))
    assert bezier_point(*p.points, 0) == (0, 0) and bezier_point(*p.points, 1) == (30, 0)
    assert abs(p.length - 30) < 1e-6
    assert abs(p.point_at_distance(15)[0] - 15) < 0.5
    assert p.point_at_distance(999) == p.points[3]


def test_wander_path_is_curved_not_straight():
    rng = random.Random(3)
    path = make_wander_path((0, 0), (400, 0), rng)
    assert path.length > 400 + 1


def test_wanderer_arrives_and_stays_finite():
    w = Wanderer((0, 0), random.Random(1))
    w.travel_to((500, 300), 200)
    t = 0.0
    while not w.update(1 / 60):
        t += 1 / 60
        assert t < 30
    assert w.pos == (500, 300) and not w.moving
    assert w.update(0.1)   # idle wanderer reports "arrived"


def test_frame_independence():
    def arrival(dt):
        w = Wanderer((0, 0), random.Random(7))
        w.travel_to((600, 0), 200)
        t = 0.0
        while not w.update(dt):
            t += dt
        return t

    slow, fast = arrival(1 / 20), arrival(1 / 120)
    assert abs(slow - fast) / fast < 0.1
