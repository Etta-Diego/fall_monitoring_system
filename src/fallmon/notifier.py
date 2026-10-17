"""Alert notifications (PRD 12.4). Every message says [SIMULATED]; failures are logged, never raised.

Console is always available. Email and Telegram are added in Phase 5.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fallmon.config import Config
from fallmon.reporting import DATA_SOURCE

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Alert:
    title: str  # e.g. "Verified fall alert" or "Probable fall alert (unverified, baseline)"
    subject_id: str
    trial_id: str
    t_s: float
    reason: str


def format_message(alert: Alert) -> str:
    return (
        f"[SIMULATED] {alert.title}\n"
        f"Source: {DATA_SOURCE}\n"
        f"Subject: {alert.subject_id} | Trial: {alert.trial_id}\n"
        f"Time in trial: {alert.t_s:.2f} s\n"
        f"Reason: {alert.reason}"
    )


class Notifier:
    channel = "base"

    def send(self, alert: Alert) -> bool:
        raise NotImplementedError


class ConsoleNotifier(Notifier):
    channel = "console"

    def send(self, alert: Alert) -> bool:
        print("\n" + format_message(alert) + "\n", flush=True)
        return True


class MultiNotifier:
    """Sends to every configured channel; returns (channel, delivered) per channel."""

    def __init__(self, notifiers: list[Notifier]):
        self.notifiers = notifiers

    def send(self, alert: Alert) -> list[tuple[str, bool]]:
        results = []
        for n in self.notifiers:
            try:
                ok = n.send(alert)
            except Exception as exc:  # a failed channel must never stop the stream
                log.error("notifier %s failed: %s", n.channel, exc)
                ok = False
            results.append((n.channel, ok))
        return results


def build_notifier(cfg: Config) -> MultiNotifier:
    notifiers: list[Notifier] = []
    for ch in cfg.notifier.channels:
        if ch == "console":
            notifiers.append(ConsoleNotifier())
        else:
            log.warning("notifier channel %r is not implemented yet (Phase 5); skipped", ch)
    return MultiNotifier(notifiers)
