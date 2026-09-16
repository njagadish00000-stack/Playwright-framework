"""Dashboard backend: Flask app serving the UI and the execution API.

Run:
    python -m server.app [--host 127.0.0.1] [--port 5000]

Then open http://127.0.0.1:5000 in a browser.
"""

from __future__ import annotations

import json
import os
import platform
import re
import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.environments import list_environments  # noqa: E402
from config.settings import framework_version  # noqa: E402
from server import allure_helper, discovery  # noqa: E402
from server.history import get_last_failed, get_last_run, get_run, list_runs  # noqa: E402
from server.packaging import build_package  # noqa: E402
from server.runner import RUNNER, RunValidationError, build_pytest_command  # noqa: E402
from utils.artifact_utils import (  # noqa: E402
    REPORTS_DIR,
    ensure_report_dirs,
    safe_filename,
    safe_join,
)
from utils.logging_utils import get_logger  # noqa: E402

logger = get_logger("server")
ensure_report_dirs()

app = Flask("dashboard-backend", static_folder=None)

DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
_TESTS_CACHE: dict = {"tests": [], "total": 0, "at": ""}


# ------------------------------------------------------------------ helpers
def _pkg_version(name: str) -> str:
    try:
        from importlib.metadata import version

        return version(name)
    except Exception:
        return "unknown"


def _known_nodeids() -> set[str]:
    if not _TESTS_CACHE["tests"]:
        refresh_cache()
    return {t["nodeid"] for t in _TESTS_CACHE["tests"]}


def refresh_cache() -> dict:
    global _TESTS_CACHE
    from utils.timing import utc_now_iso

    data = discovery.discover_tests()
    _TESTS_CACHE = {"tests": data["tests"], "total": data["total"],
                    "at": utc_now_iso()}
    return _TESTS_CACHE


def _run_options(payload: dict, fallback: dict | None = None) -> dict:
    """Extract + normalize run options, falling back to last-run settings."""
    fallback = fallback or {}
    headless = payload.get("headless", fallback.get("headless", True))
    if isinstance(headless, str):
        headless = headless.lower() not in {"false", "0", "headed", "no"}
    device = payload.get("device", fallback.get("device", ""))
    if device == "default viewport":  # tolerate legacy display string
        device = ""
    return {
        "browser": payload.get("browser", fallback.get("browser", "chromium")),
        "headless": bool(headless),
        "environment": payload.get("environment", fallback.get("environment", "local")),
        "device": device,
        "base_url": payload.get("base_url", ""),
        "api_base_url": payload.get("api_base_url", ""),
        "workers": str(payload.get("workers", "0")),
    }


def _error(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


# ------------------------------------------------------------------ pages
@app.get("/")
def index():
    return send_from_directory(DASHBOARD_DIR, "index.html")


@app.get("/css/<path:name>")
def css(name: str):
    return send_from_directory(DASHBOARD_DIR / "css", name)


@app.get("/js/<path:name>")
def js(name: str):
    return send_from_directory(DASHBOARD_DIR / "js", name)


# ------------------------------------------------------------------ meta
@app.get("/api/info")
def api_info():
    return jsonify({
        "ok": True,
        "framework_version": framework_version(),
        "python_version": platform.python_version(),
        "playwright_version": _pkg_version("playwright"),
        "pytest_version": _pkg_version("pytest"),
        "backend": f"Flask {_pkg_version('Flask')}",
        "environments": list_environments(),
        "browsers": ["chromium", "firefox", "webkit"],
        "allure": allure_helper.report_status(),
    })


# ------------------------------------------------------------------ discovery
@app.get("/api/tests")
def api_tests():
    try:
        data = _TESTS_CACHE if _TESTS_CACHE["tests"] else refresh_cache()
        grouped = discovery.group_by_category_and_file(data["tests"])
        return jsonify({"ok": True, "total": data["total"],
                        "collected_at": data["at"], "grouped": grouped,
                        "tests": data["tests"]})
    except RuntimeError as exc:
        return _error(str(exc), 500)


@app.post("/api/tests/refresh")
def api_tests_refresh():
    try:
        data = refresh_cache()
        grouped = discovery.group_by_category_and_file(data["tests"])
        return jsonify({"ok": True, "total": data["total"],
                        "collected_at": data["at"], "grouped": grouped,
                        "tests": data["tests"]})
    except RuntimeError as exc:
        return _error(str(exc), 500)


# ------------------------------------------------------------------ execution
@app.post("/api/run")
def api_run():
    payload = request.get_json(silent=True) or {}
    mode = (payload.get("mode") or "selected").lower()
    options = _run_options(payload)
    try:
        known = _known_nodeids()
        if mode == "selected":
            nodeids = payload.get("nodeids") or []
            if not nodeids:
                return _error("No tests selected. Select at least one test.")
            started = RUNNER.start(mode="selected", nodeids=nodeids,
                                   known_nodeids=known, **options)
        elif mode == "all":
            started = RUNNER.start(mode="all", known_nodeids=known, **options)
        elif mode in {"smoke", "regression"}:
            started = RUNNER.start(mode=mode, marker=mode,
                                   known_nodeids=known, **options)
        else:
            return _error(f"Invalid run mode: {mode!r}")
    except RunValidationError as exc:
        return _error(str(exc))
    except RuntimeError as exc:
        return _error(str(exc), 409)
    logger.info("Run started: %s (%s)", started["run_id"], mode)
    return jsonify({"ok": True, **started})


@app.post("/api/rerun-failed")
def api_rerun_failed():
    payload = request.get_json(silent=True) or {}
    last_failed = get_last_failed()
    if not last_failed["failed"]:
        return _error("No failed tests to rerun. Run some tests first, or all "
                      "tests in the last run passed.", 404)
    last_run = get_last_run() or {}
    options = _run_options(payload, last_run.get("settings", {}))
    try:
        started = RUNNER.start(mode="rerun-failed",
                               nodeids=last_failed["failed"],
                               known_nodeids=None, **options)
    except RunValidationError as exc:
        return _error(str(exc))
    except RuntimeError as exc:
        return _error(str(exc), 409)
    return jsonify({"ok": True, **started,
                    "reran": last_failed["failed"]})


@app.post("/api/rerun-all")
def api_rerun_all():
    payload = request.get_json(silent=True) or {}
    last_run = get_last_run()
    if not last_run or not last_run.get("results"):
        return _error("No previous execution to rerun. Run some tests first.", 404)
    nodeids = [r["nodeid"] for r in last_run["results"]]
    options = _run_options(payload, last_run.get("settings", {}))
    try:
        started = RUNNER.start(mode="rerun-all", nodeids=nodeids,
                               known_nodeids=None, **options)
    except RunValidationError as exc:
        return _error(str(exc))
    except RuntimeError as exc:
        return _error(str(exc), 409)
    return jsonify({"ok": True, **started, "reran_count": len(nodeids)})


@app.post("/api/stop")
def api_stop():
    result = RUNNER.stop()
    return jsonify({"ok": True, **result})


@app.get("/api/status")
def api_status():
    return jsonify({"ok": True, **RUNNER.status()})


@app.post("/api/command")
def api_command():
    """Preview the exact pytest command for a selection (command generator)."""
    payload = request.get_json(silent=True) or {}
    options = _run_options(payload)
    try:
        known = _known_nodeids()
        _argv, display = build_pytest_command(
            nodeids=payload.get("nodeids") or [],
            marker=payload.get("marker") or None,
            known_nodeids=known,
            run_id="<run-id>",
            **{k: v for k, v in options.items()},
        )
    except RunValidationError as exc:
        return _error(str(exc))
    return jsonify({"ok": True, "command": display})


# ------------------------------------------------------------------ results
@app.get("/api/results")
def api_results():
    run_id = request.args.get("run_id", "")
    data = get_run(run_id) if run_id else get_last_run()
    if not data:
        return _error("No execution results yet. Run some tests first.", 404)
    return jsonify({"ok": True, "run": data})


@app.get("/api/history")
def api_history():
    try:
        limit = max(1, min(int(request.args.get("limit", "30")), 200))
    except ValueError:
        limit = 30
    return jsonify({"ok": True, "runs": list_runs(limit)})


@app.get("/api/history/<run_id>")
def api_history_one(run_id: str):
    data = get_run(run_id)
    if not data:
        return _error(f"Unknown run id: {run_id}", 404)
    return jsonify({"ok": True, "run": data})


# ------------------------------------------------------------------ allure
@app.get("/api/allure/status")
def api_allure_status():
    return jsonify({"ok": True, **allure_helper.report_status()})


@app.post("/api/allure/generate")
def api_allure_generate():
    try:
        info = allure_helper.generate_report()
    except RuntimeError as exc:
        return _error(str(exc), 500)
    return jsonify({"ok": True, **info})


@app.get("/api/allure/")
def api_allure_index():
    from server.fallback_report import OUTPUT_FILE as FALLBACK_FILE

    info = allure_helper.report_status()
    if info["report_exists"]:
        return send_from_directory(allure_helper.REPORT_DIR, "index.html")
    if info["fallback_exists"]:
        return send_file(FALLBACK_FILE, mimetype="text/html")
    return _error("No report generated yet. Click 'Open Allure Report' first.", 404)


@app.get("/api/allure/fallback")
def api_allure_fallback():
    from server.fallback_report import OUTPUT_FILE as FALLBACK_FILE

    if not FALLBACK_FILE.exists():
        return _error("No fallback report yet. Generate it first.", 404)
    return send_file(FALLBACK_FILE, mimetype="text/html")


@app.get("/api/allure/report/<path:name>")
def api_allure_report_files(name: str):
    try:
        safe_join(allure_helper.REPORT_DIR, name)
    except ValueError:
        return _error("Invalid report path.", 400)
    return send_from_directory(allure_helper.REPORT_DIR, name)


# ------------------------------------------------------------------ artifacts
_ARTIFACT_DIRS = {
    "screenshots": REPORTS_DIR / "screenshots",
    "videos": REPORTS_DIR / "videos",
    "traces": REPORTS_DIR / "traces",
}


@app.get("/api/artifacts")
def api_artifacts():
    kind = request.args.get("type", "")
    if kind not in _ARTIFACT_DIRS:
        return _error("Unknown artifact type. Use screenshots, videos or traces.")
    directory = _ARTIFACT_DIRS[kind]
    files = []
    if directory.exists():
        for path in sorted(directory.iterdir(), key=lambda p: p.stat().st_mtime,
                           reverse=True):
            if path.is_file():
                files.append({"name": path.name, "size": path.stat().st_size,
                              "modified": path.stat().st_mtime})
    return jsonify({"ok": True, "type": kind, "files": files})


@app.get("/api/artifacts/for-test")
def api_artifacts_for_test():
    nodeid = request.args.get("nodeid", "")
    if not nodeid:
        return _error("Missing nodeid parameter.")
    stem = safe_filename(nodeid)
    found: dict[str, list[str]] = {}
    for kind, directory in _ARTIFACT_DIRS.items():
        matches = []
        if directory.exists():
            for path in directory.iterdir():
                if path.is_file() and path.name.startswith(stem):
                    matches.append(path.name)
        found[kind] = sorted(matches)
    return jsonify({"ok": True, "nodeid": nodeid, "artifacts": found})


@app.get("/api/artifacts/file")
def api_artifact_file():
    kind = request.args.get("type", "")
    name = request.args.get("name", "")
    if kind not in _ARTIFACT_DIRS or not name or "/" in name or "\\" in name:
        return _error("Invalid artifact request.", 400)
    try:
        target = safe_join(_ARTIFACT_DIRS[kind], name)
    except ValueError:
        return _error("Invalid artifact path.", 400)
    if not target.is_file():
        return _error("Artifact not found.", 404)
    return send_file(target)


@app.get("/api/logs")
def api_logs():
    logs_dir = PROJECT_ROOT / "logs"
    files = []
    if logs_dir.exists():
        for path in sorted(logs_dir.glob("*.log*"), key=lambda p: p.stat().st_mtime,
                           reverse=True):
            files.append({"name": path.name, "size": path.stat().st_size})
    return jsonify({"ok": True, "files": files})


@app.get("/api/logs/content")
def api_log_content():
    name = request.args.get("name", "framework.log")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.log(\.\d+)?", name):
        return _error("Invalid log file name.", 400)
    try:
        target = safe_join(PROJECT_ROOT / "logs", name)
    except ValueError:
        return _error("Invalid log path.", 400)
    if not target.is_file():
        return _error("Log file not found.", 404)
    try:
        tail = max(1, min(int(request.args.get("tail", "2000")), 20000))
    except ValueError:
        tail = 2000
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    return jsonify({"ok": True, "name": name, "lines": lines[-tail:],
                    "total_lines": len(lines)})


# ------------------------------------------------------------------ docs
@app.get("/api/documentation")
def api_documentation():
    readme = PROJECT_ROOT / "README.md"
    if not readme.exists():
        return _error("README.md not found.", 404)
    try:
        import markdown

        html = markdown.markdown(
            readme.read_text(encoding="utf-8"),
            extensions=["toc", "tables", "fenced_code"],
        )
    except ImportError:
        # Fallback: plain pre-formatted text (still readable, never broken).
        import html as _html

        html = "<pre>" + _html.escape(readme.read_text(encoding="utf-8")) + "</pre>"
    return jsonify({"ok": True, "html": html})


# ------------------------------------------------------------------ packaging
@app.get("/api/download/complete")
def api_download_complete():
    try:
        info = build_package(without_examples=False)
    except ValueError as exc:
        return _error(f"Packaging failed validation: {exc}", 500)
    return send_file(PROJECT_ROOT / "dist" / info["filename"],
                     as_attachment=True)


@app.get("/api/download/no-examples")
def api_download_no_examples():
    try:
        info = build_package(without_examples=True)
    except ValueError as exc:
        return _error(f"Packaging failed validation: {exc}", 500)
    return send_file(PROJECT_ROOT / "dist" / info["filename"],
                     as_attachment=True)


# ------------------------------------------------------------------ cleanup
@app.post("/api/cleanup")
def api_cleanup():
    from server.history import prune_history
    from utils.artifact_utils import cleanup_old_artifacts

    payload = request.get_json(silent=True) or {}
    if RUNNER.state != "idle":
        return _error("Cannot clean up while an execution is running.", 409)
    action = (payload.get("action") or "old").lower()
    if action == "results":
        # Clear current generated run artifacts (history is preserved).
        removed = 0
        for dirname in ("screenshots", "videos", "traces", ".live",
                        ".last_run", "allure-results", "allure-report"):
            directory = REPORTS_DIR / dirname
            if not directory.exists():
                continue
            for item in directory.iterdir():
                try:
                    if item.is_dir() and not item.is_symlink():
                        import shutil

                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                    removed += 1
                except OSError:
                    continue
        for extra in ("framework-report.html", ".last_failed.json"):
            try:
                (REPORTS_DIR / extra).unlink(missing_ok=True)
            except OSError:
                pass
        return jsonify({"ok": True, "removed": removed})
    try:
        max_age = max(0, min(int(payload.get("max_age_days", 14)), 3650))
    except ValueError:
        max_age = 14
    removed = cleanup_old_artifacts(
        max_age, include_history=bool(payload.get("include_history", False)),
        include_logs=bool(payload.get("include_logs", False)))
    pruned = prune_history(keep=50)
    return jsonify({"ok": True, "removed": removed, "history_pruned": pruned})


# ------------------------------------------------------------------ errors
@app.errorhandler(404)
def not_found(_exc):
    if request.path.startswith("/api/"):
        return _error("Unknown API endpoint.", 404)
    return send_from_directory(DASHBOARD_DIR, "index.html")


def main() -> None:  # pragma: no cover - manual entry point
    import argparse

    parser = argparse.ArgumentParser(description="Start the framework dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    if os.name == "posix":  # ensure Ctrl+C works even under odd parent launchers
        import signal as _signal

        for _name in ("SIGINT", "SIGTERM"):
            try:
                _signal.signal(getattr(_signal, _name), _signal.SIG_DFL)
            except (OSError, ValueError):
                pass
    print(f"Dashboard: http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        app.run(host="0.0.0.0", port=args.port, threaded=True)
    except OSError as exc:
        print(f"Could not start the dashboard on port {args.port}: {exc}")
        print("The port may be in use -- retry with: python -m server.app --port 5001")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
