"""Wall-clock timing helpers.

All timings in the framework are real measured wall-clock times captured with
:func:`time.perf_counter` (durations) and :func:`time.time` (timestamps).
Nothing is estimated or derived from other values: suite duration is
``suite_end - suite_start``, never the sum of test durations.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string with milliseconds."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def format_duration(seconds: float) -> str:
    """Format seconds as ``MM:SS.mmm`` or ``HH:MM:SS.mmm`` for long runs."""
    if seconds is None or seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"
    return f"{minutes:02d}:{secs:02d}.{ms:03d}"


class Timer:
    """Simple wall-clock timer (context manager + manual stop)."""

    def __init__(self) -> None:
        self.start_perf = time.perf_counter()
        self.start_epoch = time.time()
        self.start_iso = utc_now_iso()
        self.end_perf: float | None = None
        self.end_epoch: float | None = None
        self.end_iso: str | None = None

    def stop(self) -> "Timer":
        self.end_perf = time.perf_counter()
        self.end_epoch = time.time()
        self.end_iso = utc_now_iso()
        return self

    @property
    def elapsed(self) -> float:
        end = self.end_perf if self.end_perf is not None else time.perf_counter()
        return max(0.0, end - self.start_perf)

    @property
    def elapsed_formatted(self) -> str:
        return format_duration(self.elapsed)

    def __enter__(self) -> "Timer":
        return self

    def __exit__(self, *exc_info) -> None:
        self.stop()

    def as_dict(self) -> dict:
        self.stop()
        duration = self.end_perf - self.start_perf  # type: ignore[operator]
        return {
            "start": self.start_iso,
            "start_epoch": self.start_epoch,
            "end": self.end_iso,
            "end_epoch": self.end_epoch,
            "duration": round(duration, 4),
            "duration_formatted": format_duration(duration),
        }
