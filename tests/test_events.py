from fallmon.events import EventChange, EventTracker

GAP, COOL = 1.0, 10.0


def _feed(tracker, steps):
    """steps: list of (t, is_ood); returns list of change values."""
    return [tracker.update(t, ood, 0.5 if ood else 0.99)[0] for t, ood in steps]


def test_open_on_first_ood_step():
    tr = EventTracker(GAP, COOL)
    assert _feed(tr, [(3.0, False), (3.5, True)]) == [None, EventChange.OPENED]
    assert tr.current.t_open == 3.5


def test_ood_steps_within_gap_merge_into_one_event():
    tr = EventTracker(GAP, COOL)
    changes = _feed(tr, [(3.0, True), (3.5, True), (4.0, False), (4.5, True)])  # 4.5 - 3.5 = 1.0 <= gap
    assert changes == [EventChange.OPENED, EventChange.EXTENDED, None, EventChange.EXTENDED]
    assert tr.count == 1


def test_event_closes_after_gap_without_ood():
    tr = EventTracker(GAP, COOL)
    changes = _feed(tr, [(3.0, True), (3.5, False), (4.0, False)])
    assert changes == [EventChange.OPENED, None, EventChange.CLOSED]
    assert tr.current is None


def test_new_event_after_close_when_no_alert():
    tr = EventTracker(GAP, COOL)
    changes = _feed(tr, [(3.0, True), (4.0, False), (6.0, True)])
    assert changes == [EventChange.OPENED, EventChange.CLOSED, EventChange.OPENED]
    assert tr.count == 2


def test_min_confidence_tracked():
    tr = EventTracker(GAP, COOL)
    tr.update(3.0, True, 0.7)
    tr.update(3.5, True, 0.4)
    tr.update(4.0, True, 0.6)
    assert tr.current.min_confidence == 0.4


def test_cooldown_suppresses_new_events_after_alert():
    tr = EventTracker(GAP, COOL)
    tr.update(3.0, True, 0.5)
    tr.start_cooldown(3.0)  # alert raised at 3.0 -> cooldown until 13.0
    changes = _feed(tr, [(4.0, False), (8.0, True), (12.5, True), (13.0, True)])
    assert changes == [EventChange.CLOSED, EventChange.SUPPRESSED, EventChange.SUPPRESSED, EventChange.OPENED]


def test_event_can_extend_during_cooldown():
    tr = EventTracker(GAP, COOL)
    tr.update(3.0, True, 0.5)
    tr.start_cooldown(3.0)
    assert tr.update(3.5, True, 0.5)[0] == EventChange.EXTENDED


def test_reset_clears_event_and_cooldown():
    tr = EventTracker(GAP, COOL)
    tr.update(3.0, True, 0.5)
    tr.start_cooldown(3.0)
    tr.reset()
    assert tr.current is None and not tr.in_cooldown(4.0)
    assert tr.update(4.0, True, 0.5)[0] == EventChange.OPENED


def test_close_at_end():
    tr = EventTracker(GAP, COOL)
    tr.update(3.0, True, 0.5)
    ev = tr.close_at_end(3.5)
    assert ev.t_close == 3.5 and tr.current is None
    assert tr.close_at_end(4.0) is None
