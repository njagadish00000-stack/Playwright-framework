"""Root pytest configuration: options, fixtures, timing and reporting hooks.

This module implements the shared test-execution infrastructure:

* CLI options: ``--browser`` / ``--headed`` / ``--headless`` / ``--env`` /
  ``--device`` / ``--base-url`` / ``--api-base-url`` / artifact modes /
  ``--run-id`` / ``--dump-tests``.
* Session fixtures: resolved :class:`~config.settings.Settings`, demo-app
  lifecycle, effective URLs, run id.
* Precise per-test timing via ``pytest_runtest_makereport`` (uses the real
  ``call.start``/``call.stop`` perf-counter measurements, xdist-safe).
* Suite wall-clock timing via ``pytest_sessionstart``/``pytest_sessionfinish``
  (never derived from summed test durations).
* Live progress events (JSONL per worker) consumed by the dashboard.
* Execution-history JSON written for every run.
* Allure environment metadata.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytest_plugins = ["fixtures.api_fixtures", "fixtures.ui_fixtures"]

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.environments import list_environments  # noqa: E402
from config.settings import VALID_BROWSERS, get_settings  # noqa: E402
from utils.artifact_utils import (  # noqa: E402
    HISTORY_DIR,
    LAST_RUN_DIR,
    LIVE_DIR,
    ensure_report_dirs,
)
from utils.logging_utils import bind_test_context, configure_logging, get_logger  # noqa: E402
from utils.timing import Timer, format_duration, utc_now_iso  # noqa: E402

logger = get_logger("conftest")

CATEGORY_DIRS = {
    "api_tests": "api",
    "ui_tests": "ui",
    "api_ui_tests": "api_ui",
    "e2e_tests": "e2e",
}

# ---------------------------------------------------------------------------
# In-memory per-process state (workers each have their own copy -- by design).
# ---------------------------------------------------------------------------
_SUITE_TIMER: Timer | None = None
_SUITE_RUN_ID: str = ""
_TEST_STARTS: dict[str, dict] = {}
_TEST_PHASES: dict[str, dict] = {}
_FINISHED: set[str] = set()


def _worker_id(config) -> str:
    return getattr(config, "workerinput", {}).get("workerid", "master")


def _using_xdist_workers(config) -> bool:
    return bool(getattr(config.option, "numprocesses", None))


def _is_duplicate_controller(config) -> bool:
    """True on the xdist controller (reports already emitted by workers)."""
    return _using_xdist_workers(config) and not hasattr(config, "workerinput")


def _category_for_nodeid(nodeid: str) -> str:
    first = nodeid.split("::")[0].replace("\\", "/")
    for directory, category in CATEGORY_DIRS.items():
        if first == directory or first.startswith(directory + "/"):
            return category
    return "unknown"


def _run_live_dir(run_id: str) -> Path:
    path = LIVE_DIR / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _emit_event(config, payload: dict) -> None:
    """Append a live-progress event (JSONL, one file per worker)."""
    try:
        run_id = getattr(config, "_fw_run_id", "") or "no-run-id"
        worker = _worker_id(config)
        path = _run_live_dir(run_id) / f"events-{worker}.jsonl"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except Exception as exc:  # pragma: no cover - progress must never break runs
        print(f"[fw] live event write failed: {exc}")


def _test_info(item) -> dict:
    nodeid = item.nodeid
    file_part = nodeid.split("::")[0]
    cls = getattr(item, "cls", None)
    # Exclude internal plugin markers (e.g. allure's ``allure_label`` marks).
    markers = sorted({m.name for m in item.iter_markers()
                      if not m.name.startswith("allure")})
    return {
        "nodeid": nodeid,
        "category": _category_for_nodeid(nodeid),
        "file": file_part,
        "class": cls.__name__ if cls else "",
        "test_name": item.name,
        "markers": markers,
    }


# ---------------------------------------------------------------------------
# CLI options
# ---------------------------------------------------------------------------
def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("framework", "Unified automation framework options")
    group.addoption("--browser", default=os.environ.get("BROWSER", "chromium"),
                    choices=list(VALID_BROWSERS), help="Playwright browser.")
    group.addoption("--headed", action="store_true", default=None,
                    help="Run browsers with a visible window.")
    group.addoption("--headless", action="store_true", default=None,
                    help="Run browsers headless (default).")
    group.addoption("--env", default=os.environ.get("ENVIRONMENT", "local"),
                    help=f"Environment profile: {', '.join(list_environments())}.")
    group.addoption("--device", default=os.environ.get("DEVICE", ""),
                    help="Playwright device descriptor (e.g. 'iPhone 13'), '' = none.")
    group.addoption("--base-url", default=os.environ.get("BASE_URL", ""),
                    help="Web UI base URL (overrides environment profile).")
    group.addoption("--api-base-url", default=os.environ.get("API_BASE_URL", ""),
                    help="REST API base URL (overrides environment profile).")
    group.addoption("--screenshot-mode", default=os.environ.get("SCREENSHOT_MODE", "on-failure"),
                    choices=["on-failure", "always", "never"])
    group.addoption("--video-mode", default=os.environ.get("VIDEO_MODE", "retain-on-failure"),
                    choices=["off", "on", "retain-on-failure"])
    group.addoption("--trace-mode", default=os.environ.get("TRACE_MODE", "retain-on-failure"),
                    choices=["off", "on", "on-first-retry", "retain-on-failure"])
    group.addoption("--run-id", default="",
                    help="Run identifier (generated if omitted). Used for history/live files.")
    group.addoption("--dump-tests", default="",
                    help="Write collected test list as JSON to PATH and exit (discovery).")


def _settings_from_options(config) -> "Settings":
    from config.settings import Settings  # local import for typing only

    headed = config.option.headed
    headless = config.option.headless
    if headed and headless:
        raise pytest.UsageError("Pass only one of --headed or --headless.")
    if headed:
        resolved_headless: bool | None = False
    elif headless:
        resolved_headless = True
    else:
        resolved_headless = None  # fall back to env/.env default
    overrides = {
        "browser": config.option.browser,
        "environment": config.option.env,
        "device": config.option.device,
        "base_url": config.option.base_url or None,
        "api_base_url": config.option.api_base_url or None,
        "screenshot_mode": config.option.screenshot_mode,
        "video_mode": config.option.video_mode,
        "trace_mode": config.option.trace_mode,
    }
    if resolved_headless is not None:
        overrides["headless"] = resolved_headless
    return get_settings(overrides)


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def run_id(pytestconfig) -> str:
    return getattr(pytestconfig, "_fw_run_id", "no-run-id")


@pytest.fixture(scope="session")
def fw_settings(pytestconfig):
    return _settings_from_options(pytestconfig)


@pytest.fixture(scope="session")
def demo_app_info(fw_settings, request):
    """Start (or reuse) the bundled demo app when targeting localhost."""
    from urllib.parse import urlparse

    from server.demo_app import ensure_demo_app_running

    parsed = urlparse(fw_settings.base_url)
    host = parsed.hostname or "127.0.0.1"
    if host not in {"127.0.0.1", "localhost"}:
        # Remote system under test -- never auto-start the demo app.
        return {"base_url": fw_settings.base_url,
                "api_base_url": fw_settings.api_base_url,
                "port": parsed.port, "started_here": False, "local": False}
    # xdist workers each start a PRIVATE server (OS-assigned port) so parallel
    # workers never share mutable demo data and never contend on one port.
    is_xdist_worker = hasattr(request.config, "workerinput")
    if is_xdist_worker:
        info = ensure_demo_app_running(fw_settings.demo_app_host, 0, prefer_own=True)
    else:
        preferred = parsed.port or fw_settings.demo_app_port
        info = ensure_demo_app_running(fw_settings.demo_app_host, preferred)
        # Reset seeded data at session start (serial runs only -- resetting
        # while parallel workers run would corrupt their data).
        if not _using_xdist_workers(request.config):
            try:
                import requests

                requests.post(f"{info['api_base_url']}/_reset", timeout=10)
            except Exception as exc:
                logger.warning("Demo app reset failed (continuing): %s", exc)
    info["local"] = True
    return info


@pytest.fixture(scope="session")
def effective_base_url(fw_settings, demo_app_info) -> str:
    if demo_app_info.get("local"):
        return demo_app_info["base_url"]
    return fw_settings.base_url


@pytest.fixture(scope="session")
def effective_api_base_url(fw_settings, demo_app_info) -> str:
    if demo_app_info.get("local"):
        return demo_app_info["api_base_url"]
    return fw_settings.api_base_url


@pytest.fixture(scope="function", autouse=True)
def _bind_log_context(request):
    bind_test_context(request.node.nodeid, _category_for_nodeid(request.node.nodeid))
    yield
    bind_test_context("", "")


@pytest.fixture(scope="function")
def test_context(request):
    """Small dict with node id / category / markers for the current test."""
    return {
        "nodeid": request.node.nodeid,
        "category": _category_for_nodeid(request.node.nodeid),
        "markers": sorted({m.name for m in request.node.iter_markers()}),
    }


# ---------------------------------------------------------------------------
# Configuration / collection hooks
# ---------------------------------------------------------------------------
def pytest_configure(config: pytest.Config) -> None:
    ensure_report_dirs()
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    run_id = config.option.run_id or (
        "run-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    )
    config._fw_run_id = run_id  # type: ignore[attr-defined]
    # Resolve settings early so invalid values fail fast with a clear message.
    try:
        settings = _settings_from_options(config)
    except ValueError as exc:
        raise pytest.UsageError(str(exc)) from exc
    config._fw_settings = settings  # type: ignore[attr-defined]


def pytest_report_header(config: pytest.Config) -> list[str]:
    settings = getattr(config, "_fw_settings", None)
    if settings is None:
        return []
    from config.settings import framework_version

    return [
        f"framework: v{framework_version()}",
        f"environment: {settings.environment} | browser: {settings.browser} "
        f"| mode: {'headless' if settings.headless else 'headed'} "
        f"| device: {settings.device or 'default'}",
        f"base_url: {settings.base_url} | api_base_url: {settings.api_base_url}",
        f"run_id: {getattr(config, '_fw_run_id', '')}",
    ]


def pytest_collection_finish(session: pytest.Session) -> None:
    if _is_duplicate_controller(session.config):
        return
    items = [_test_info(item) for item in session.items]
    dump_path = getattr(session.config.option, "dump_tests", "")
    if dump_path:
        Path(dump_path).parent.mkdir(parents=True, exist_ok=True)
        with open(dump_path, "w", encoding="utf-8") as fh:
            json.dump(items, fh, indent=2)
    # Expected-tests file drives live progress totals (controller/master only,
    # real executions only -- never for --collect-only discovery).
    if not hasattr(session.config, "workerinput") and not getattr(
            session.config.option, "collectonly", False):
        run_id = getattr(session.config, "_fw_run_id", "no-run-id")
        live = _run_live_dir(run_id)
        with open(live / "expected.json", "w", encoding="utf-8") as fh:
            json.dump({"total": len(items), "tests": items}, fh, indent=2)


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Attach dynamic Allure labels/parameters (browser, mode, env, category)."""
    try:
        import allure

        settings = getattr(item.config, "_fw_settings", None)
        info = _test_info(item)
        epic = {"api": "API", "ui": "UI", "api_ui": "API + UI",
                "e2e": "End-to-End"}.get(info["category"], info["category"])
        allure.dynamic.epic(epic)
        if settings is not None:
            allure.dynamic.parameter(
                "browser", f"{settings.browser} ({'headless' if settings.headless else 'headed'})")
            allure.dynamic.parameter("environment", settings.environment)
            if settings.device:
                allure.dynamic.parameter("device", settings.device)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Timing hooks (the precise measurement engine)
# ---------------------------------------------------------------------------
@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    # Expose the call-phase report to fixtures (artifact decisions).
    if report.when == "call":
        item.rep_call = report
    elif report.when == "setup":
        item.rep_setup = report
    config = item.config
    # NOTE: makereport runs only where the test actually executes (worker or
    # plain master), never duplicated on the xdist controller. No dedupe needed.
    nodeid = item.nodeid
    phases = _TEST_PHASES.setdefault(nodeid, {})
    try:
        raw_longrepr = report.longrepr
        if (report.outcome == "skipped" and isinstance(raw_longrepr, tuple)
                and len(raw_longrepr) == 3):
            longrepr_text = f"{raw_longrepr[0]}:{raw_longrepr[1]}: {raw_longrepr[2]}"
        else:
            longrepr_text = str(raw_longrepr) if raw_longrepr else ""
    except Exception:
        longrepr_text = ""
    phases[report.when] = {
        "outcome": report.outcome,
        "duration": round(max(0.0, (call.stop or 0) - (call.start or 0)), 4),
        "detail": longrepr_text[-4000:],
    }
    if report.when == "setup":
        _TEST_STARTS[nodeid] = {
            "start_perf": call.start,
            "start_epoch": time.time(),
            "start_iso": utc_now_iso(),
        }
        info = _test_info(item)
        _emit_event(config, {"event": "started", **info,
                             "start": _TEST_STARTS[nodeid]["start_iso"],
                             "start_epoch": _TEST_STARTS[nodeid]["start_epoch"],
                             "worker": _worker_id(config)})
    elif report.when == "teardown" and nodeid not in _FINISHED:
        _FINISHED.add(nodeid)
        started = _TEST_STARTS.pop(nodeid, None)
        start_perf = (started or {}).get("start_perf", call.start)
        start_epoch = (started or {}).get("start_epoch", time.time())
        start_iso = (started or {}).get("start_iso", utc_now_iso())
        stop_perf = call.stop or start_perf
        duration = round(max(0.0, stop_perf - start_perf), 4)
        end_epoch = round(start_epoch + duration, 4)
        from datetime import datetime as _dt

        end_iso = _dt.fromtimestamp(end_epoch, tz=timezone.utc).isoformat(
            timespec="milliseconds")
        status = _resolve_status(phases)
        # Failure/skip detail: prefer the most informative phase report
        # (the teardown report alone often carries no longrepr, e.g. skips).
        failure = ""
        for phase_name in ("call", "setup", "teardown"):
            detail = (phases.get(phase_name) or {}).get("detail", "")
            if detail:
                failure = detail
                break
        if status in {"failed", "error"} and not failure:
            failure = "test failed (no details captured)"
        if status == "skipped" and not failure:
            failure = "skipped"
        info = _test_info(item)
        _emit_event(config, {"event": "finished", **info, "status": status,
                             "start": start_iso, "start_epoch": start_epoch,
                             "end": end_iso, "end_epoch": end_epoch,
                             "duration": duration,
                             "duration_formatted": format_duration(duration),
                             "failure": failure,
                             "phases": dict(phases),
                             "worker": _worker_id(config)})
    _TEST_PHASES[nodeid] = phases


def _resolve_status(phases: dict) -> str:
    setup = (phases.get("setup") or {}).get("outcome")
    call = (phases.get("call") or {}).get("outcome")
    teardown = (phases.get("teardown") or {}).get("outcome")
    if setup == "failed":
        return "error"
    if call == "failed":
        return "failed"
    if teardown == "failed":
        return "error"
    if "skipped" in {setup, call, teardown}:
        return "skipped"
    if call == "passed" or (call is None and setup == "passed"):
        return "passed"
    if setup == "passed" and call is None:
        return "passed"
    return "failed" if "failed" in {setup, call, teardown} else "skipped"


# ---------------------------------------------------------------------------
# Session hooks: suite wall-clock timing + history
# ---------------------------------------------------------------------------
def pytest_sessionstart(session: pytest.Session) -> None:
    global _SUITE_TIMER, _SUITE_RUN_ID
    if hasattr(session.config, "workerinput"):
        return  # workers do not own the suite clock
    if getattr(session.config.option, "collectonly", False):
        return  # collection is not an execution: no timing, no live files
    _SUITE_TIMER = Timer()
    _SUITE_RUN_ID = getattr(session.config, "_fw_run_id", "no-run-id")
    live = _run_live_dir(_SUITE_RUN_ID)
    # Fresh live dir for this run id.
    for child in live.glob("events-*.jsonl"):
        child.unlink(missing_ok=True)
    settings = getattr(session.config, "_fw_settings", None)
    with open(live / "suite.json", "w", encoding="utf-8") as fh:
        json.dump({
            "run_id": _SUITE_RUN_ID,
            "status": "running",
            "suite_start": _SUITE_TIMER.start_iso,
            "suite_start_epoch": _SUITE_TIMER.start_epoch,
            "settings": settings.to_safe_dict() if settings else {},
            "command": " ".join(sys.argv),
        }, fh, indent=2)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if hasattr(session.config, "workerinput"):
        return  # only controller/master aggregates + writes history
    if getattr(session.config.option, "collectonly", False):
        return  # collection is not an execution: no results, no history
    global _SUITE_TIMER
    timer = _SUITE_TIMER or Timer()
    timer.stop()
    run_id = getattr(session.config, "_fw_run_id", "no-run-id") or "no-run-id"
    settings = getattr(session.config, "_fw_settings", None)
    results = _aggregate_results(run_id)
    counts = _count_results(results)
    status_map = {0: "completed", 1: "completed", 2: "interrupted",
                  3: "internal-error", 4: "usage-error", 5: "no-tests"}
    status = status_map.get(exitstatus, "completed")
    if status == "completed" and any(r["status"] == "interrupted" for r in results):
        status = "interrupted"
    suite = {
        "run_id": run_id,
        "status": status,
        "exitstatus": exitstatus,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "suite_start": timer.start_iso,
        "suite_start_epoch": timer.start_epoch,
        "suite_end": timer.end_iso,
        "suite_end_epoch": timer.end_epoch,
        "suite_duration": round(timer.end_perf - timer.start_perf, 4),  # wall clock
        "suite_duration_formatted": format_duration(timer.end_perf - timer.start_perf),
        "counts": counts,
        "settings": settings.to_safe_dict() if settings else {},
        "command": " ".join(sys.argv),
        "results": results,
    }
    # Per-test stats for the summary (fastest/slowest/average).
    durations = [(r["nodeid"], r.get("duration") or 0) for r in results
                 if r.get("duration") is not None]
    if durations:
        slowest = max(durations, key=lambda t: t[1])
        fastest = min(durations, key=lambda t: t[1])
        suite["stats"] = {
            "average_duration": round(sum(d for _, d in durations) / len(durations), 4),
            "average_duration_formatted": format_duration(
                sum(d for _, d in durations) / len(durations)),
            "slowest_test": slowest[0], "slowest_duration": slowest[1],
            "slowest_duration_formatted": format_duration(slowest[1]),
            "fastest_test": fastest[0], "fastest_duration": fastest[1],
            "fastest_duration_formatted": format_duration(fastest[1]),
            "by_category": _count_by_category(results),
        }
    else:
        suite["stats"] = {"by_category": _count_by_category(results)}
    ensure_report_dirs()
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    LAST_RUN_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_DIR / f"{run_id}.json", "w", encoding="utf-8") as fh:
        json.dump(suite, fh, indent=2)
    with open(LAST_RUN_DIR / "results.json", "w", encoding="utf-8") as fh:
        json.dump(suite, fh, indent=2)
    failed = [r["nodeid"] for r in results if r["status"] in {"failed", "error"}]
    with open(PROJECT_ROOT / "reports" / ".last_failed.json", "w", encoding="utf-8") as fh:
        json.dump({"run_id": run_id, "failed": failed}, fh, indent=2)
    # Mark live suite file final.
    live_suite = _run_live_dir(run_id) / "suite.json"
    try:
        data = json.loads(live_suite.read_text(encoding="utf-8")) if live_suite.exists() else {}
        data.update({"status": status, "suite_end": timer.end_iso,
                     "suite_end_epoch": timer.end_epoch,
                     "suite_duration": suite["suite_duration"],
                     "suite_duration_formatted": suite["suite_duration_formatted"],
                     "counts": counts})
        live_suite.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Live suite finalization failed: %s", exc)
    _write_allure_environment(session)
    logger.info("Run %s finished: %s (exit=%s, duration=%s)", run_id, status,
                exitstatus, suite["suite_duration_formatted"])


def _aggregate_results(run_id: str) -> list[dict]:
    live = LIVE_DIR / run_id
    finished: dict[str, dict] = {}
    started: dict[str, dict] = {}
    if live.exists():
        for events_file in sorted(live.glob("events-*.jsonl")):
            try:
                lines = events_file.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("event") == "finished":
                    finished[event["nodeid"]] = event
                elif event.get("event") == "started":
                    started.setdefault(event["nodeid"], event)
    results = list(finished.values())
    # Expected but never finished -> interrupted (honest statuses for stops).
    expected: list[dict] = []
    expected_file = live / "expected.json"
    if expected_file.exists():
        try:
            expected = json.loads(expected_file.read_text(encoding="utf-8")).get("tests", [])
        except ValueError:
            expected = []
    for item in expected:
        if item["nodeid"] in finished:
            continue
        entry = dict(item)
        entry["status"] = "interrupted"
        entry["failure"] = "Test did not finish (run stopped or worker lost)."
        entry["duration"] = 0.0
        entry["duration_formatted"] = format_duration(0)
        entry["start"] = (started.get(item["nodeid"]) or {}).get("start")
        entry["start_epoch"] = (started.get(item["nodeid"]) or {}).get("start_epoch")
        entry["end"] = utc_now_iso()
        entry["end_epoch"] = time.time()
        results.append(entry)
    # Stable order: follow collection order when known.
    order = {item["nodeid"]: i for i, item in enumerate(expected)}
    results.sort(key=lambda r: order.get(r["nodeid"], 10_000))
    return results


def _count_results(results: list[dict]) -> dict:
    counts = {"total": len(results), "passed": 0, "failed": 0, "skipped": 0,
              "error": 0, "interrupted": 0}
    for result in results:
        status = result.get("status", "failed")
        if status == "failed":
            counts["failed"] += 1
        elif status == "error":
            counts["error"] += 1
            counts["failed"] += 1  # errors also count as failures in totals
        elif status in counts:
            counts[status] += 1
        else:
            counts["failed"] += 1
    return counts


def _count_by_category(results: list[dict]) -> dict:
    by_category: dict[str, int] = {}
    for result in results:
        category = result.get("category", "unknown")
        by_category[category] = by_category.get(category, 0) + 1
    return by_category


def _write_allure_environment(session: pytest.Session) -> None:
    try:
        alluredir = getattr(session.config.option, "allure_report_dir", "")
        if not alluredir:
            return
        import playwright  # noqa: F401
        from importlib.metadata import version as _pkg_version

        def _version(name: str) -> str:
            try:
                return _pkg_version(name)
            except Exception:
                return "unknown"

        from config.settings import framework_version

        settings = getattr(session.config, "_fw_settings", None)
        workers = getattr(session.config.option, "numprocesses", None)
        lines = [
            f"Framework.version={framework_version()}",
            f"Run.id={getattr(session.config, '_fw_run_id', '')}",
            f"Environment={settings.environment if settings else ''}",
            f"Browser={settings.browser if settings else ''}",
            f"Browser.mode={'headless' if (settings and settings.headless) else 'headed'}",
            f"Device={(settings.device if settings and settings.device else 'default viewport')}",
            f"Python.version={platform.python_version()}",
            f"Playwright.version={_version('playwright')}",
            f"Pytest.version={_version('pytest')}",
            f"OS={platform.system()} {platform.release()}",
            f"Execution.mode={'parallel xdist (' + str(workers) + ')' if workers else 'serial'}",
        ]
        target = Path(str(alluredir)) / "environment.properties"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as exc:  # pragma: no cover - metadata must never break runs
        logger.warning("Allure environment.properties write failed: %s", exc)
