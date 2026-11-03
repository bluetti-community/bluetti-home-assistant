"""What each cloud poll of a device actually got, before any ride-out."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

# Polls kept per device: 24 h at the fastest rate a coordinator polls. A
# websocket message asks for a refresh, which Home Assistant's debouncer lets
# through at most once every 10 s, and every refresh pushes the 30 s interval
# back - so a device that pushes all day is polled every 10 s, 8640 times.
# Memory only: the history starts again empty after a restart.
POLL_HISTORY_SIZE = 8640


class PollOutcome(StrEnum):
    """How a poll ended, after its one retry."""

    OK = "ok"
    NO_READINGS = "no_readings"
    EMPTY_RESPONSE = "empty_response"
    AUTH_REJECTED = "auth_rejected"
    API_ERROR = "api_error"
    HTTP_ERROR = "http_error"
    TIMEOUT = "timeout"
    DNS_ERROR = "dns_error"
    CONNECT_ERROR = "connect_error"
    NETWORK_ERROR = "network_error"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PollRecord:
    """One poll: when it started, how long it took, how it ended."""

    started: datetime
    duration_ms: int
    outcome: PollOutcome
    attempts: int
    msg_code: int | None = None
    http_status: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """The record as plain JSON values, for a diagnostics dump."""
        return {
            "started": self.started.isoformat(),
            "duration_ms": self.duration_ms,
            "outcome": self.outcome.value,
            "attempts": self.attempts,
            "msg_code": self.msg_code,
            "http_status": self.http_status,
        }


class PollHistory:
    """The last POLL_HISTORY_SIZE polls of one device, oldest first."""

    def __init__(self, size: int = POLL_HISTORY_SIZE) -> None:
        self._records: deque[PollRecord] = deque(maxlen=size)

    def add(self, record: PollRecord) -> None:
        """Keep a poll, dropping the oldest one once the history is full."""
        self._records.append(record)

    @property
    def latest(self) -> PollRecord | None:
        """The most recent poll, or None before the first one."""
        return self._records[-1] if self._records else None

    def snapshot(self) -> tuple[PollRecord, ...]:
        """Every poll kept, oldest first."""
        return tuple(self._records)


def failure_windows(records: Iterable[PollRecord]) -> list[dict[str, Any]]:
    """
    Runs of polls that did not end in ``ok``, oldest first.

    ``no_readings`` counts as a failure here: the cloud answered, but with no
    reading the unit could have sent - the overnight pattern owners report -
    and the window's outcomes say which kind it was. ``end`` is when the last
    poll of the run finished; ``ongoing`` is true when no ``ok`` poll has
    come after it yet.
    """
    windows: list[dict[str, Any]] = []
    run: list[PollRecord] = []

    def close(ongoing: bool) -> None:
        last = run[-1]
        windows.append({
            "start": run[0].started.isoformat(),
            "end": (last.started + timedelta(milliseconds=last.duration_ms)).isoformat(),
            "count": len(run),
            "outcomes": sorted({record.outcome.value for record in run}),
            "ongoing": ongoing,
        })

    for record in records:
        if record.outcome is not PollOutcome.OK:
            run.append(record)
        elif run:
            close(ongoing=False)
            run = []
    if run:
        close(ongoing=True)
    return windows
