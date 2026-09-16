"""Execution-history storage helpers (JSON per run)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = PROJECT_ROOT / "reports" / "execution-history"
LAST_RUN_FILE = PROJECT_ROOT / "reports" / ".last_run" / "results.json"
LAST_FAILED_FILE = PROJECT_ROOT / "reports" / ".last_failed.json"


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def list_runs(limit: int = 30) -> list[dict]:
    """Recent runs, newest first (summary fields for the history table)."""
    if not HISTORY_DIR.exists():
        return []
    files = sorted(HISTORY_DIR.glob("*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    summaries = []
    for path in files:
        data = _read_json(path)
        if not data:
            continue
        settings = data.get("settings", {})
        summaries.append({
            "run_id": data.get("run_id", path.stem),
            "date": data.get("date", ""),
            "status": data.get("status", ""),
            "suite_start": data.get("suite_start", ""),
            "suite_end": data.get("suite_end", ""),
            "suite_duration": data.get("suite_duration", 0),
            "suite_duration_formatted": data.get("suite_duration_formatted", ""),
            "counts": data.get("counts", {}),
            "environment": settings.get("environment", ""),
            "browser": settings.get("browser", ""),
            "headless": settings.get("headless", True),
            "device": settings.get("device", ""),
            "command": data.get("command", ""),
        })
    return summaries


def get_run(run_id: str) -> dict | None:
    """Full recorded data for one run (results + timings + settings)."""
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        return None
    return _read_json(HISTORY_DIR / f"{run_id}.json")


def get_last_run() -> dict | None:
    return _read_json(LAST_RUN_FILE)


def get_last_failed() -> dict:
    data = _read_json(LAST_FAILED_FILE)
    if not data:
        return {"run_id": "", "failed": []}
    return {"run_id": data.get("run_id", ""),
            "failed": list(data.get("failed", []))}


def save_history_entry(entry: dict[str, Any]) -> Path:
    """Persist a history entry (used as fallback when pytest can't)."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    run_id = entry.get("run_id", "unknown")
    safe = "".join(c for c in str(run_id) if c.isalnum() or c in "-_.") or "unknown"
    path = HISTORY_DIR / f"{safe}.json"
    path.write_text(json.dumps(entry, indent=2), encoding="utf-8")
    LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_FILE.write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return path


def prune_history(keep: int = 50) -> int:
    """Keep only the newest *keep* history files. Returns removed count."""
    if not HISTORY_DIR.exists():
        return 0
    files = sorted(HISTORY_DIR.glob("*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for path in files[keep:]:
        try:
            path.unlink()
            removed += 1
        except OSError:
            continue
    return removed
