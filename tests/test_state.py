from idle_spider.state import State, StateMachine


def test_full_cycle():
    sm = StateMachine()
    seen = []
    sm.add_listener(lambda a, b: seen.append((a, b)))
    for target in (State.IDLE_DETECTED, State.ANIMATING, State.USER_ACTIVITY,
                   State.FADE_OUT, State.MONITORING):
        assert sm.transition(target)
    assert sm.state is State.MONITORING
    assert len(seen) == 5


def test_illegal_transitions_are_rejected():
    sm = StateMachine()
    assert not sm.transition(State.ANIMATING)
    assert not sm.transition(State.FADE_OUT)
    assert sm.state is State.MONITORING
    sm.transition(State.IDLE_DETECTED)
    sm.transition(State.ANIMATING)
    assert not sm.transition(State.MONITORING)   # must go through USER_ACTIVITY


def test_idle_detected_can_be_cancelled():
    sm = StateMachine()
    sm.transition(State.IDLE_DETECTED)
    assert sm.transition(State.MONITORING)


def test_reset_forces_monitoring():
    sm = StateMachine()
    sm.transition(State.IDLE_DETECTED)
    sm.transition(State.ANIMATING)
    sm.reset()
    assert sm.state is State.MONITORING
