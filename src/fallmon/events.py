"""Turn per-step OOD flags into events, shared by baseline and proposed modes (PRD Section 10).

One physical movement should produce at most one event, and so at most one alert:
- an event opens at the first OOD step when no event is open and no cooldown is active;
- OOD steps within merge_gap_s of the last OOD step extend it;
- it closes once no OOD step has occurred for merge_gap_s;
- after an alert, a cooldown of cooldown_s suppresses new events;
- in proposed mode, no new event opens while a verification is pending (`blocked`).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EventChange(str, Enum):
    OPENED = "opened"
    EXTENDED = "extended"
    CLOSED = "closed"
    SUPPRESSED = "suppressed"  # OOD step during cooldown (or while blocked), no event open


@dataclass
class Event:
    number: int  # 1, 2, ... within the current trial
    t_open: float
    t_last_ood: float
    min_confidence: float
    t_close: float | None = None


class EventTracker:
    def __init__(self, merge_gap_s: float, cooldown_s: float):
        self.merge_gap_s = merge_gap_s
        self.cooldown_s = cooldown_s
        self.reset()

    def reset(self) -> None:
        """Start of a new trial/stream: no open event, no cooldown."""
        self.current: Event | None = None
        self.cooldown_until = float("-inf")
        self.count = 0
        self.blocked = False

    def start_cooldown(self, t_alert: float) -> None:
        """Called by the pipeline when an alert is emitted."""
        self.cooldown_until = t_alert + self.cooldown_s

    def in_cooldown(self, t: float) -> bool:
        return t < self.cooldown_until

    def update(self, t: float, is_ood: bool, confidence: float) -> tuple[EventChange | None, Event | None]:
        """Feed one decision step. Returns what happened to the event state, and the event concerned."""
        ev = self.current
        if is_ood:
            if ev is not None and t - ev.t_last_ood <= self.merge_gap_s:
                ev.t_last_ood = t
                ev.min_confidence = min(ev.min_confidence, confidence)
                return EventChange.EXTENDED, ev
            if self.in_cooldown(t) or self.blocked:
                return EventChange.SUPPRESSED, None
            self.count += 1
            self.current = Event(self.count, t_open=t, t_last_ood=t, min_confidence=confidence)
            return EventChange.OPENED, self.current
        if ev is not None and t - ev.t_last_ood >= self.merge_gap_s:
            return EventChange.CLOSED, self._close(t)
        return None, None

    def close_at_end(self, t: float) -> Event | None:
        """Trial ended: close any open event."""
        return self._close(t) if self.current is not None else None

    def end_current(self, t: float) -> Event | None:
        """Close the open event now (used after a rejected verification when re-arming, D-012)."""
        return self._close(t) if self.current is not None else None

    def _close(self, t: float) -> Event:
        ev, self.current = self.current, None
        ev.t_close = t
        return ev
