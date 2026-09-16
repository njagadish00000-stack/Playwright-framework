"""Allure report handling with an honest fallback.

Strategy:
    1. If the Allure CLI (``allure``) is installed AND runnable (needs Java),
       use ``allure generate`` to build the full static report (primary path).
    2. Otherwise build the framework HTML fallback report (pure Python, real
       data, clearly labeled as NOT Allure) so "Open report" still does
       something genuinely useful, and tell the user exactly why Allure
       itself is unavailable and how to install it.

Nothing is faked: callers always learn which engine produced the report.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "reports" / "allure-results"
REPORT_DIR = PROJECT_ROOT / "reports" / "allure-report"

ALLURE_INSTALL_HINT = (
    "Install the Allure CLI (https://allurereport.org/docs/install) "
    "and a Java runtime, then retry. Manual commands: "
    "`allure generate reports/allure-results -o reports/allure-report --clean`, "
    "`allure open reports/allure-report`, `allure serve reports/allure-results`."
)


def allure_cli_path() -> str | None:
    """Return the Allure CLI path if installed, else None."""
    return shutil.which("allure")


def allure_cli_works(timeout: int = 30) -> tuple[bool, str]:
    """Check that ``allure --version`` actually runs (Java present, etc.)."""
    binary = allure_cli_path()
    if not binary:
        return False, "Allure CLI is not installed (no `allure` on PATH). " + ALLURE_INSTALL_HINT
    try:
        proc = subprocess.run([binary, "--version"], capture_output=True,
                              text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Allure CLI failed to run: {exc}. " + ALLURE_INSTALL_HINT
    if proc.returncode != 0:
        return False, f"Allure CLI error: {(proc.stderr or proc.stdout).strip()[-300:]}. " + ALLURE_INSTALL_HINT
    return True, (proc.stdout or "").strip() or "Allure CLI available"


def results_present() -> bool:
    if not RESULTS_DIR.exists():
        return False
    return any(RESULTS_DIR.glob("*-result.json"))


def generate_report(timeout: int = 300) -> dict:
    """Generate a viewable report. Returns info about what was produced.

    Raises:
        RuntimeError: If no results exist at all.
    """
    from server.fallback_report import OUTPUT_FILE as FALLBACK_FILE
    from server.fallback_report import generate_framework_report
    from server.history import get_last_run

    if not results_present():
        raise RuntimeError(
            "No Allure results found. Run some tests first, then open the report.")
    ok, version_info = allure_cli_works()
    if ok:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [allure_cli_path(), "generate", str(RESULTS_DIR),
             "-o", str(REPORT_DIR), "--clean"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(
                f"`allure generate` failed: {(proc.stderr or proc.stdout)[-1000:]}")
        return {"engine": "allure-cli", "engine_info": version_info,
                "mode": "directory", "path": str(REPORT_DIR),
                "url": "/api/allure/",
                "message": "Allure report generated with the Allure CLI."}
    # Fallback: framework HTML report from the recorded run data.
    run = get_last_run()
    if not run:
        raise RuntimeError(
            "No recorded run results found for the fallback report. " + version_info)
    generate_framework_report(run, reason=version_info)
    return {"engine": "framework-fallback", "engine_info": version_info,
            "mode": "single-file", "path": str(FALLBACK_FILE),
            "url": "/api/allure/",
            "message": ("Allure CLI unavailable, so a framework HTML report was "
                        "generated instead. " + ALLURE_INSTALL_HINT)}


def report_status() -> dict:
    """Cheap status probe for the dashboard (no generation)."""
    from server.fallback_report import OUTPUT_FILE as FALLBACK_FILE

    ok, info = allure_cli_works()
    return {
        "cli_installed": ok,
        "cli_info": info,
        "fallback_available": True,
        "results_present": results_present(),
        "report_exists": (REPORT_DIR / "index.html").exists(),
        "fallback_exists": FALLBACK_FILE.exists(),
    }
