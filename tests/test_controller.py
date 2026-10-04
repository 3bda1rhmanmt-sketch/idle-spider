import random

from idle_spider.animation.controller import (
    AnimationController,
    AnimationSettings,
    SceneState,
    ScreenInfo,
)
from idle_spider.animation.spider import Spider


def run_until(controller, predicate, limit=900.0, dt=1 / 30):
    t = 0.0
    while not predicate() and t < limit:
        controller.update(dt)
        t += dt
    assert t < limit, "simulation did not converge"
    return t


def test_starts_offscreen_in_chosen_corner():
    for corner, (sx, sy) in {"top_left": (-1, -1), "bottom_right": (1, 1)}.items():
        c = AnimationController(AnimationSettings(start_corner=corner), random.Random(1))
        c.start([ScreenInfo(0, 1280, 720)])
        x, y = c.scenes[0].spider.pos
        assert (x < 0) == (sx < 0) and (y < 0) == (sy < 0)
        assert (x > 1280) == (sx > 0) and (y > 720) == (sy > 0)


def test_builds_webs_up_to_limit_then_settles():
    c = AnimationController(AnimationSettings(max_webs=2, speed=3.0), random.Random(2))
    c.start([ScreenInfo(0, 1280, 720)])
    scene = c.scenes[0]
    run_until(c, lambda: c.settled)
    assert len(scene.webs) == 2 and scene.state is SceneState.RESTING
    assert scene.completed_version == 2 and scene.active_web is None
    assert all(w.complete for w in scene.webs)


def test_webs_fit_on_screen():
    c = AnimationController(AnimationSettings(max_webs=3, speed=3.0), random.Random(5))
    c.start([ScreenInfo(0, 800, 600)])
    run_until(c, lambda: c.settled)
    for web in c.scenes[0].webs:
        x0, y0, x1, y1 = web.bounds
        assert x0 >= 0 and y0 >= 0 and x1 <= 800 and y1 <= 600


def test_multi_monitor_scenes_are_independent():
    c = AnimationController(AnimationSettings(), random.Random(3))
    c.start([ScreenInfo(0, 1920, 1080), ScreenInfo(1, 1280, 1024)])
    assert set(c.scenes) == {0, 1}
    c.update(0.05)
    assert c.scenes[0] is not c.scenes[1]


def test_fade_out_finishes_and_stop_clears():
    c = AnimationController(AnimationSettings(), random.Random(4))
    c.start([ScreenInfo(0, 1280, 720)])
    c.update(0.05)
    c.begin_fade(0.5)
    assert c.fading and not c.fade_finished
    run_until(c, lambda: c.fade_finished, limit=5)
    assert c.fade_alpha < 0.01
    c.stop()
    assert not c.running and not c.scenes


def test_large_dt_is_clamped():
    c = AnimationController(AnimationSettings(), random.Random(6))
    c.start([ScreenInfo(0, 1280, 720)])
    before = c.scenes[0].spider.pos
    c.update(60.0)                       # a stalled frame must not teleport the spider
    after = c.scenes[0].spider.pos
    assert abs(after[0] - before[0]) + abs(after[1] - before[1]) < 100


def test_spider_has_eight_legs_and_smooth_turning():
    s = Spider((0, 0), 14)
    legs = s.legs()
    assert len(legs) == 8 and all(len(leg) == 3 for leg in legs)
    s.update(0.016, (0, 5))               # target is 90 degrees away
    assert 0 < s.heading < 1.57           # turned only partially
