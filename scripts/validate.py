"""Acceptance validation for the Unified Automation Framework.

Runs the core checklist end to end (CLI + dashboard API + packaging),
prints a PASS/FAIL/SKIP table, and exits non-zero on any failure.
Self-cleaning: temporary validation files and the test server it spawns are
always removed/stopped.

Usage:
    .venv/bin/python scripts/validate.py [--port 5055] [--quick]
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PYTHON = sys.executable
RESULTS: list[tuple[str, str, str]] = []  # (check, PASS/FAIL/SKIP, detail)


def check(name: str, status: str, detail: str = "") -> None:
    RESULTS.append((name, status, detail))
    mark = {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "SKIP"}[status]
    print(f"[{mark}] {name}" + (f" -- {detail}" if detail else ""), flush=True)


def run_pytest(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, "-m", "pytest", *args, "-p", "no:cacheprovider"],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=timeout)


def last_run() -> dict:
    return json.loads(
        (PROJECT_ROOT / "reports" / ".last_run" / "results.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ checks
def check_environment() -> None:
    import flask  # noqa: F401
    import playwright  # noqa: F401
    import pytest  # noqa: F401
    from importlib.metadata import version

    detail = (f"py={platform_py()} pytest={version('pytest')} "
              f"pw={version('playwright')} flask={version('Flask')}")
    check("environment-imports", "PASS", detail)


def platform_py() -> str:
    import platform

    return platform.python_version()


def check_discovery() -> dict:
    from server.discovery import discover_tests

    data = discover_tests()
    by_cat: dict[str, int] = {}
    for t in data["tests"]:
        by_cat[t["category"]] = by_cat.get(t["category"], 0) + 1
    ok = (by_cat.get("api", 0) >= 30 and by_cat.get("ui", 0) >= 10
          and by_cat.get("api_ui", 0) >= 4 and by_cat.get("e2e", 0) >= 2)
    check("discovery", "PASS" if ok else "FAIL",
          f"total={data['total']} by_cat={by_cat}")
    return data


def check_cli_api_runs() -> None:
    proc = run_pytest(["api_tests/", "-q", "--run-id", "validate-serial"])
    data = last_run()
    ok = proc.returncode == 0 and data["counts"]["failed"] == 0 and data["counts"]["passed"] > 0
    check("cli-api-serial", "PASS" if ok else "FAIL",
          f"counts={data['counts']} dur={data['suite_duration_formatted']}")
    proc = run_pytest(["api_tests/", "-q", "-n", "2", "--run-id", "validate-parallel"])
    data = last_run()
    ok = proc.returncode == 0 and data["counts"]["failed"] == 0
    check("cli-api-parallel", "PASS" if ok else "FAIL", f"counts={data['counts']}")


def check_cli_selection() -> None:
    cases = [
        (["-m", "smoke", "--co", "-q"], "smoke-marker"),
        (["-m", "regression", "--co", "-q"], "regression-marker"),
        (["api_tests/test_users.py", "-q", "--run-id", "validate-file"], "file-selection"),
        (["api_tests/test_users.py::TestGetUsers", "-q", "--run-id", "validate-class"], "class-selection"),
        (["api_tests/test_users.py::TestGetUsers::test_list_users", "-q",
          "--run-id", "validate-test"], "test-selection"),
    ]
    for args, name in cases:
        proc = run_pytest(args)
        check(f"cli-{name}", "PASS" if proc.returncode == 0 else "FAIL",
              f"rc={proc.returncode}")


def check_timing_integrity() -> None:
    run_pytest(["api_tests/test_users.py", "-q", "--run-id", "validate-timing"])
    data = last_run()
    bad = [r["nodeid"] for r in data["results"]
           if abs((r["end_epoch"] - r["start_epoch"]) - r["duration"]) > 0.002
           or r["start_epoch"] > r["end_epoch"]]
    suite_ok = (data["suite_start_epoch"] < data["suite_end_epoch"]
                and abs((data["suite_end_epoch"] - data["suite_start_epoch"])
                        - data["suite_duration"]) < 0.002)
    summed = sum(r["duration"] for r in data["results"])
    check("timing-per-test", "PASS" if not bad else "FAIL",
          f"mismatches={len(bad)}")
    check("timing-suite-wallclock", "PASS" if suite_ok else "FAIL",
          f"suite={data['suite_duration']}s summed={summed:.3f}s "
          f"(must differ under overhead/parallelism, wall-clock is authoritative)")


def check_config_paths() -> None:
    from unittest.mock import MagicMock

    from config.settings import get_settings
    from fixtures import browser_manager as bm
    from playwright.sync_api import sync_playwright

    ok = True
    for browser in ("chromium", "firefox", "webkit"):
        for headless in (True, False):
            s = get_settings({"browser": browser, "headless": headless})
            if s.playwright_launch_options() != {"headless": headless}:
                ok = False
            pw = MagicMock()
            bm.launch_browser(pw, s)
            getattr(pw, browser).launch.assert_called_once_with(headless=headless)
    try:
        get_settings({"browser": "safari"})
        ok = False
    except ValueError:
        pass
    with sync_playwright() as pw:
        opts = bm.build_context_options(pw, get_settings({"device": "iPhone 13"}),
                                        Path(tempfile.gettempdir()))
        if opts.get("viewport", {}).get("width") != 390:
            ok = False
        try:
            bm.build_context_options(pw, get_settings({"device": "Nope 999"}),
                                     Path(tempfile.gettempdir()))
            ok = False
        except ValueError:
            pass
    check("config-browser-mode-device", "PASS" if ok else "FAIL",
          "3 browsers x headed/headless dispatch + device merge + rejections")


def check_browser_dependent() -> None:
    from playwright.sync_api import sync_playwright

    from fixtures.browser_manager import browser_executable_info

    with sync_playwright() as pw:
        installed, _ = browser_executable_info(pw, "chromium")
    proc = run_pytest(["ui_tests/test_home.py", "-q", "--run-id", "validate-ui"])
    data = last_run()
    if installed:
        ok = data["counts"]["failed"] == 0 and data["counts"]["passed"] > 0
        check("ui-real-browser", "PASS" if ok else "FAIL", f"counts={data['counts']}")
    else:
        reasons = [r.get("failure", "") for r in data["results"]]
        ok = (proc.returncode == 0 and data["counts"]["passed"] == 0
              and all("not installed" in (reason or "") for reason in reasons))
        check("ui-skip-without-browser", "PASS" if ok else "FAIL",
              f"counts={data['counts']} (browser binaries absent; honest skips)")


# ------------------------------------------------------------- dashboard API
def _http(base: str, method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload or {}).encode() if payload is not None or method == "POST" else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode()
            return {"status": resp.status, "json": json.loads(body) if body else {}}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return {"status": exc.code, "json": json.loads(body)}
        except ValueError:
            return {"status": exc.code, "json": {"error": body[:200]}}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_idle(base: str, timeout: int = 180) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = _http(base, "GET", "/api/status")["json"]
        if status.get("state") == "idle":
            return status
        time.sleep(0.5)
    raise TimeoutError("run did not finish in time")


def check_dashboard(port: int) -> None:
    proc = subprocess.Popen(
        [PYTHON, "-m", "server.app", "--port", str(port)],
        cwd=str(PROJECT_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    temp_files: list[Path] = []
    try:
        for _ in range(60):
            try:
                if _http(base, "GET", "/api/info")["status"] == 200:
                    break
            except OSError:
                time.sleep(0.5)
        else:
            check("dashboard-start", "FAIL", "server did not answer")
            return
        check("dashboard-start", "PASS", f"port={port}")

        info = _http(base, "GET", "/api/info")["json"]
        check("dashboard-info", "PASS" if info.get("ok") else "FAIL",
              f"fw={info.get('framework_version')}")
        tests = _http(base, "POST", "/api/tests/refresh")["json"]
        check("dashboard-discovery", "PASS" if tests.get("total", 0) >= 50 else "FAIL",
              f"total={tests.get('total')}")

        # Run-selected (exactly 2 tests) -------------------------------------
        nodeids = [t["nodeid"] for t in tests["tests"]
                   if t["category"] == "api"][:2]
        started = _http(base, "POST", "/api/run",
                        {"mode": "selected", "nodeids": nodeids,
                         "browser": "chromium", "headless": True,
                         "environment": "qa", "workers": "0"})["json"]
        mid = _http(base, "GET", "/api/status")["json"]
        live_ok = mid.get("state") in {"running", "idle"}  # fast suite may finish instantly
        _wait_idle(base)
        run = _http(base, "GET", "/api/results")["json"]["run"]
        ok = (run["counts"]["total"] == 2 and run["counts"]["passed"] == 2
              and run["settings"]["environment"] == "qa")
        check("dashboard-run-selected", "PASS" if ok else "FAIL",
              f"counts={run['counts']} live_seen={live_ok}")

        # Controlled failure -> rerun-failed -> fix -> rerun -> none-left -----
        failing = PROJECT_ROOT / "api_tests" / "test_temp_validate_fail.py"
        failing.write_text(
            "import pytest\npytestmark = pytest.mark.api\n"
            "def test_temp_validate_ok(): assert True\n"
            "def test_temp_validate_bad(): assert False, 'CONTROLLED'\n",
            encoding="utf-8")
        temp_files.append(failing)
        _http(base, "POST", "/api/tests/refresh")
        _http(base, "POST", "/api/run",
              {"mode": "selected",
               "nodeids": ["api_tests/test_temp_validate_fail.py"]})
        _wait_idle(base)
        run = _http(base, "GET", "/api/results")["json"]["run"]
        fail_ok = run["counts"]["failed"] == 1 and run["counts"]["passed"] == 1
        check("dashboard-controlled-failure", "PASS" if fail_ok else "FAIL",
              f"counts={run['counts']}")
        rerun = _http(base, "POST", "/api/rerun-failed", {})["json"]
        only_failed = rerun.get("reran", []) == [
            "api_tests/test_temp_validate_fail.py::test_temp_validate_bad"]
        _wait_idle(base)
        check("dashboard-rerun-failed-only", "PASS" if only_failed else "FAIL",
              f"reran={rerun.get('reran')}")
        failing.write_text(
            "import pytest\npytestmark = pytest.mark.api\n"
            "def test_temp_validate_ok(): assert True\n"
            "def test_temp_validate_bad(): assert True\n",
            encoding="utf-8")
        _http(base, "POST", "/api/rerun-failed", {})
        _wait_idle(base)
        run = _http(base, "GET", "/api/results")["json"]["run"]
        check("dashboard-rerun-after-fix", "PASS" if run["counts"]["passed"] == 1 else "FAIL",
              f"counts={run['counts']}")
        none = _http(base, "POST", "/api/rerun-failed", {})
        check("dashboard-rerun-none-left",
              "PASS" if none["status"] == 404 else "FAIL", str(none["json"])[:100])
        rall = _http(base, "POST", "/api/rerun-all", {})["json"]
        _wait_idle(base)
        check("dashboard-rerun-all", "PASS" if rall.get("ok") else "FAIL",
              f"reran_count={rall.get('reran_count')}")

        # Stop ----------------------------------------------------------------
        slow = PROJECT_ROOT / "api_tests" / "test_temp_validate_slow.py"
        slow.write_text(
            "import time\nimport pytest\npytestmark = pytest.mark.api\n"
            "def test_temp_validate_slow():\n    time.sleep(30)\n",
            encoding="utf-8")
        temp_files.append(slow)
        _http(base, "POST", "/api/tests/refresh")
        _http(base, "POST", "/api/run",
              {"mode": "selected",
               "nodeids": ["api_tests/test_temp_validate_slow.py"]})
        time.sleep(6)
        mid = _http(base, "GET", "/api/status")["json"]
        running_seen = mid.get("state") == "running"
        stop = _http(base, "POST", "/api/stop", {})["json"]
        t0 = time.time()
        _wait_idle(base, timeout=60)
        stop_secs = time.time() - t0
        run = _http(base, "GET", "/api/results")["json"]["run"]
        interrupted = [r for r in run["results"] if r["status"] == "interrupted"]
        ok = (running_seen and stop.get("stopped") and run["status"] in
              {"interrupted", "stopped"} and len(interrupted) == 1 and stop_secs < 25)
        check("dashboard-stop", "PASS" if ok else "FAIL",
              f"{stop_secs:.1f}s status={run['status']}")

        # Allure + docs + packaging + history -------------------------------
        gen = _http(base, "POST", "/api/allure/generate", {})["json"]
        check("dashboard-allure", "PASS" if gen.get("ok") else "FAIL",
              f"engine={gen.get('engine')}")
        docs = _http(base, "GET", "/api/documentation")["json"]
        check("dashboard-docs",
              "PASS" if docs.get("ok") and len(docs.get("html", "")) > 5000 else "FAIL",
              f"html_chars={len(docs.get('html', ''))}")
        hist = _http(base, "GET", "/api/history")["json"]
        check("dashboard-history",
              "PASS" if hist.get("ok") and len(hist.get("runs", [])) >= 3 else "FAIL",
              f"runs={len(hist.get('runs', []))}")
        bad = _http(base, "POST", "/api/run",
                    {"mode": "selected", "nodeids": ["../../x"]})["json"]
        check("dashboard-input-validation",
              "PASS" if not bad.get("ok") else "FAIL", str(bad)[:80])
    finally:
        for path in temp_files:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def check_packaging() -> None:
    import zipfile

    from server.packaging import build_package

    for without in (False, True):
        info = build_package(without_examples=without)
        names = zipfile.ZipFile(PROJECT_ROOT / "dist" / info["filename"]).namelist()
        tests = [n for n in names if n.split("/")[0] in
                 {"api_tests", "ui_tests", "api_ui_tests", "e2e_tests"}
                 and n.endswith(".py") and "__init__" not in n]
        forbidden = [n for n in names if ".venv" in n or "__pycache__" in n
                     or "allure-results" in n or n.endswith("/.env")]
        ok = info["valid"] and not forbidden and (
            (len(tests) > 0 and not without) or (len(tests) == 0 and without))
        check("package-" + ("no-examples" if without else "complete"),
              "PASS" if ok else "FAIL",
              f"{info['filename']} entries={info['entries']} tests={len(tests)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the framework end to end")
    parser.add_argument("--port", type=int, default=0,
                        help="Dashboard port for API checks (0 = free port)")
    parser.add_argument("--quick", action="store_true",
                        help="Skip the slower dashboard stop/rerun checks")
    args = parser.parse_args()

    print("=== Unified Framework acceptance validation ===", flush=True)
    try:
        check_environment()
        check_discovery()
        check_cli_api_runs()
        check_cli_selection()
        check_timing_integrity()
        check_config_paths()
        check_browser_dependent()
        if not args.quick:
            check_dashboard(args.port or _free_port())
        check_packaging()
    except Exception as exc:  # never crash silently; record the failure
        check("unexpected-error", "FAIL", f"{type(exc).__name__}: {exc}")

    print("\n=== Summary ===", flush=True)
    failed = 0
    for name, status, detail in RESULTS:
        print(f"{status:4}  {name}" + (f"  ({detail})" if detail else ""))
        if status == "FAIL":
            failed += 1
    print(f"\n{len(RESULTS) - failed}/{len(RESULTS)} checks passed.", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
