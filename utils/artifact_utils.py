"""Artifact paths, safe file serving helpers and cleanup utilities."""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
SCREENSHOTS_DIR = REPORTS_DIR / "screenshots"
VIDEOS_DIR = REPORTS_DIR / "videos"
TRACES_DIR = REPORTS_DIR / "traces"
ALLURE_RESULTS_DIR = REPORTS_DIR / "allure-results"
ALLURE_REPORT_DIR = REPORTS_DIR / "allure-report"
HISTORY_DIR = REPORTS_DIR / "execution-history"
LIVE_DIR = REPORTS_DIR / ".live"
LAST_RUN_DIR = REPORTS_DIR / ".last_run"

SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def ensure_report_dirs() -> None:
    for directory in (
        REPORTS_DIR,
        SCREENSHOTS_DIR,
        VIDEOS_DIR,
        TRACES_DIR,
        ALLURE_RESULTS_DIR,
        ALLURE_REPORT_DIR,
        HISTORY_DIR,
        LIVE_DIR,
        LAST_RUN_DIR,
        PROJECT_ROOT / "logs",
    ):
        directory.mkdir(parents=True, exist_ok=True)


def safe_filename(nodeid: str, suffix: str = "") -> str:
    """Convert a pytest node id into a filesystem-safe file stem."""
    stem = SAFE_NAME_RE.sub("_", nodeid).strip("_")[:180]
    return f"{stem}{suffix}"


def safe_join(base: Path, *parts: str) -> Path:
    """Join *parts* to *base*, raising if the result escapes *base*.

    Used by every dashboard endpoint that serves files (prevents path
    traversal).
    """
    base_resolved = base.resolve()
    target = base_resolved.joinpath(*parts).resolve()
    if target != base_resolved and base_resolved not in target.parents:
        raise ValueError(f"Unsafe path: {'/'.join(parts)}")
    return target


def cleanup_old_artifacts(
    max_age_days: int = 14,
    *,
    include_history: bool = False,
    include_logs: bool = False,
) -> dict[str, int]:
    """Delete generated runtime artifacts older than *max_age_days*.

    Never touches source code, configuration, test data or README -- only
    generated reports/logs/history. Returns counts per area.
    """
    cutoff = time.time() - max_age_days * 86400
    removed = {"reports": 0, "history": 0, "logs": 0}
    report_targets = [SCREENSHOTS_DIR, VIDEOS_DIR, TRACES_DIR, LIVE_DIR, LAST_RUN_DIR]
    if include_history:
        report_targets.append(HISTORY_DIR)
    for directory in report_targets:
        if not directory.exists():
            continue
        for item in directory.iterdir():
            try:
                if item.stat().st_mtime < cutoff:
                    if item.is_dir() and not item.is_symlink():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                    key = "history" if directory == HISTORY_DIR else "reports"
                    removed[key] += 1
            except OSError:
                continue
    if include_logs:
        logs_dir = PROJECT_ROOT / "logs"
        for item in logs_dir.glob("*.log*"):
            try:
                if item.stat().st_mtime < cutoff:
                    item.unlink(missing_ok=True)
                    removed["logs"] += 1
            except OSError:
                continue
    return removed
