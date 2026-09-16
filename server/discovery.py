"""Dynamic test discovery via real pytest collection.

Discovery shells out to ``pytest --collect-only --dump-tests <tmpfile>`` and
reads the machine-readable JSON written by ``conftest.pytest_collection_finish``.
Test names are NEVER hard-coded anywhere -- a new test file appears in the
dashboard automatically after refresh.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TEST_DIRS = ("api_tests", "ui_tests", "api_ui_tests", "e2e_tests")


def discover_tests(timeout: int = 180) -> dict:
    """Collect all tests. Returns ``{"tests": [...], "total": N}``.

    Raises:
        RuntimeError: If pytest collection fails (message includes details).
    """
    python = sys.executable
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        dump_path = tmp.name
    cmd = [
        python, "-m", "pytest", "--collect-only", "-q",
        f"--dump-tests={dump_path}", "-p", "no:cacheprovider",
        *TEST_DIRS,
    ]
    try:
        proc = subprocess.run(
            cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Test discovery timed out after {timeout}s") from exc
    try:
        raw = Path(dump_path).read_text(encoding="utf-8")
        tests = json.loads(raw) if raw.strip() else []
    except (OSError, ValueError):
        tests = []
    finally:
        try:
            Path(dump_path).unlink(missing_ok=True)
        except OSError:
            pass
    if proc.returncode != 0 and not tests:
        detail = (proc.stderr or proc.stdout or "")[-2000:]
        raise RuntimeError(f"Test collection failed.\n{detail}")
    return {"tests": tests, "total": len(tests)}


def group_by_category_and_file(tests: list[dict]) -> dict:
    """Group flat test list into ``{category: {file: [tests]}}`` for the UI tree."""
    grouped: dict[str, dict[str, list[dict]]] = {}
    for test in tests:
        grouped.setdefault(test.get("category", "unknown"), {}).setdefault(
            test.get("file", "unknown"), []).append(test)
    return grouped
