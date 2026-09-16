"""Test-execution engine: builds safe pytest commands, runs them, tracks live state.

Security: pytest commands are constructed ONLY from validated selections and
allow-listed options. Arbitrary shell commands are never accepted or executed
(``shell=False`` always; node ids are validated against real discovery).
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIVE_DIR = PROJECT_ROOT / "reports" / ".live"
LAST_RUN_FILE = PROJECT_ROOT / "reports" / ".last_run" / "results.json"

VALID_BROWSERS = ("chromium", "firefox", "webkit")
VALID_ENVS = ("local", "dev", "qa", "staging", "prodlike")
TEST_DIRS = ("api_tests", "ui_tests", "api_ui_tests", "e2e_tests")
FIXED_MARKERS = {"smoke": "smoke", "regression": "regression",
                 "api": "api", "ui": "ui", "api_ui": "api_ui", "e2e": "e2e"}

_NODEID_UNSAFE = re.compile(r"[;&|$`!\\><\n\r]|\.\.")


def _reset_child_signals() -> None:
    """Reset signal dispositions to defaults in the pytest child (posix).

    Background launchers (CI agents, process supervisors, ``nohup``-style
    runners) often start us with SIGINT/SIGTERM set to SIG_IGN. Ignored
    dispositions are inherited across fork+exec, and ``subprocess`` only
    restores SIGPIPE/SIGXFSZ -- so without this reset, pytest would inherit
    "ignore SIGINT" and graceful Stop would be impossible (Python keeps
    SIG_IGN instead of installing its KeyboardInterrupt handler).
    """
    import signal as _signal

    for name in ("SIGINT", "SIGTERM", "SIGQUIT", "SIGHUP"):
        try:
            _signal.signal(getattr(_signal, name), _signal.SIG_DFL)
        except (OSError, ValueError, AttributeError, RuntimeError):
            continue


class RunValidationError(ValueError):
    """Raised when a run request fails validation (user-facing message)."""


def _validate_nodeid(nodeid: str, known: set[str] | None) -> str:
    cleaned = (nodeid or "").strip().replace("\\", "/")
    if not cleaned:
        raise RunValidationError("Empty test selection entry.")
    if _NODEID_UNSAFE.search(cleaned):
        raise RunValidationError(f"Invalid test selection: {nodeid!r}")
    first = cleaned.split("::")[0].split("/")[0]
    if first not in TEST_DIRS:
        raise RunValidationError(f"Invalid test selection (unknown directory): {nodeid!r}")
    if known is not None and cleaned not in known:
        # Allow file / class / parametrized-function prefixes (pytest semantics:
        # "file.py::test_func" runs all "file.py::test_func[param]" variants).
        if not any(k == cleaned or k.startswith(cleaned + "::")
                   or k.startswith(cleaned + "[") for k in known):
            raise RunValidationError(f"Unknown test selection: {nodeid!r}")
    return cleaned


def _validate_workers(workers: str) -> list[str]:
    value = (workers or "0").strip().lower()
    if value in {"", "0", "1"}:
        return []
    if value == "auto":
        return ["-n", "auto"]
    try:
        number = int(value)
    except ValueError:
        raise RunValidationError(f"Invalid workers value: {workers!r}") from None
    if not 1 <= number <= 32:
        raise RunValidationError(f"Invalid workers value: {workers!r} (1-32 or auto)")
    if number == 1:
        return []
    return ["-n", str(number)]


def build_pytest_command(
    *,
    nodeids: list[str] | None = None,
    marker: str | None = None,
    browser: str = "chromium",
    headless: bool = True,
    environment: str = "local",
    device: str = "",
    base_url: str = "",
    api_base_url: str = "",
    workers: str = "0",
    run_id: str = "",
    known_nodeids: set[str] | None = None,
) -> tuple[list[str], str]:
    """Build a validated pytest argv list + human-readable command string."""
    browser = (browser or "chromium").lower()
    if browser not in VALID_BROWSERS:
        raise RunValidationError(f"Invalid browser: {browser!r}")
    environment = (environment or "local").lower()
    if environment not in VALID_ENVS:
        raise RunValidationError(f"Invalid environment: {environment!r}")
    if device and not re.fullmatch(r"[A-Za-z0-9 .,'()+-]+", device):
        raise RunValidationError(f"Invalid device name: {device!r}")

    argv = [sys.executable, "-m", "pytest"]
    if marker:
        if marker not in FIXED_MARKERS.values():
            raise RunValidationError(f"Invalid marker: {marker!r}")
        argv += ["-m", marker]
    validated: list[str] = []
    for nodeid in nodeids or []:
        validated.append(_validate_nodeid(nodeid, known_nodeids))
    argv += validated
    argv += ["--browser", browser, "--headless" if headless else "--headed",
            "--env", environment]
    if device:
        argv += ["--device", device]
    if base_url:
        argv += ["--base-url", base_url]
    if api_base_url:
        argv += ["--api-base-url", api_base_url]
    argv += _validate_workers(workers)
    if run_id:
        argv += ["--run-id", run_id]
    argv += ["--alluredir", "reports/allure-results", "--clean-alluredir"]
    display = " ".join(argv[3:])  # hide the "python -m" prefix for readability
    return argv, f"pytest {display}"


class _LiveReader:
    """Incremental reader for a run's live event files."""

    def __init__(self, run_id: str) -> None:
        self.run_dir = LIVE_DIR / run_id
        self._offsets: dict[str, int] = {}
        self.finished: dict[str, dict] = {}
        self.started: dict[str, dict] = {}
        self.expected_total: int | None = None

    def poll(self) -> None:
        try:
            expected_file = self.run_dir / "expected.json"
            if expected_file.exists() and self.expected_total is None:
                data = json.loads(expected_file.read_text(encoding="utf-8"))
                self.expected_total = int(data.get("total", 0))
        except (OSError, ValueError):
            pass
        if not self.run_dir.exists():
            return
        for events_file in sorted(self.run_dir.glob("events-*.jsonl")):
            key = events_file.name
            offset = self._offsets.get(key, 0)
            try:
                with open(events_file, encoding="utf-8") as fh:
                    fh.seek(offset)
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        if event.get("event") == "finished":
                            self.finished[event["nodeid"]] = event
                        elif event.get("event") == "started":
                            self.started.setdefault(event["nodeid"], event)
                    self._offsets[key] = fh.tell()
            except OSError:
                continue


class TestRunner:
    """Owns at most one active pytest subprocess; exposes live status."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._run_id = ""
        self._run_meta: dict = {}
        self._reader: _LiveReader | None = None
        self._state = "idle"  # idle | running | stopping
        self._runner_start = 0.0
        self._last_summary: dict | None = None
        self._output_tail: list[str] = []
        self._waiter: threading.Thread | None = None

    # -- public API ---------------------------------------------------------
    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def active_run_id(self) -> str:
        with self._lock:
            return self._run_id

    def start(self, *, mode: str, nodeids: list[str] | None = None,
              marker: str | None = None, browser: str = "chromium",
              headless: bool = True, environment: str = "local",
              device: str = "", base_url: str = "", api_base_url: str = "",
              workers: str = "0", known_nodeids: set[str] | None = None) -> dict:
        """Start a run. Raises RunValidationError / RuntimeError."""
        with self._lock:
            if self._state in {"running", "stopping"}:
                raise RuntimeError("Another execution is already running. "
                                   "Stop it before starting a new one.")
            run_id = "dash-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            argv, display = build_pytest_command(
                nodeids=nodeids, marker=marker, browser=browser,
                headless=headless, environment=environment, device=device,
                base_url=base_url, api_base_url=api_base_url,
                workers=workers, run_id=run_id, known_nodeids=known_nodeids)
            LIVE_DIR.mkdir(parents=True, exist_ok=True)
            env = dict(os.environ)
            env["PYTHONUNBUFFERED"] = "1"
            popen_kwargs: dict = {"cwd": str(PROJECT_ROOT), "env": env,
                                  "stdout": subprocess.PIPE,
                                  "stderr": subprocess.STDOUT, "text": True}
            if os.name == "posix":
                popen_kwargs["start_new_session"] = True
                popen_kwargs["preexec_fn"] = _reset_child_signals
            else:  # Windows: new process group so a Ctrl-Break reaches children
                popen_kwargs["creationflags"] = getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            proc = subprocess.Popen(argv, **popen_kwargs)  # noqa: S603 (argv validated)
            self._proc = proc
            self._run_id = run_id
            self._state = "running"
            self._runner_start = time.time()
            self._reader = _LiveReader(run_id)
            self._output_tail = []
            self._run_meta = {
                "run_id": run_id, "mode": mode, "command": display,
                "browser": browser, "headless": headless,
                "environment": environment, "device": device,
                "nodeids": list(nodeids or []), "marker": marker or "",
                "workers": workers,
                "runner_start": datetime.now(timezone.utc).isoformat(
                    timespec="milliseconds"),
            }
            self._waiter = threading.Thread(target=self._drain_output,
                                            args=(proc,), daemon=True)
            self._waiter.start()
            threading.Thread(target=self._watchdog, args=(proc, run_id),
                             daemon=True).start()
            return {"run_id": run_id, "command": display, "mode": mode}

    def stop(self) -> dict:
        """Request graceful termination: SIGINT, then TERM, then KILL."""
        with self._lock:
            if self._state != "running" or self._proc is None:
                return {"stopped": False, "message": "No execution is running."}
            self._state = "stopping"
            proc = self._proc
        try:
            if os.name == "posix":
                try:
                    os.killpg(proc.pid, signal.SIGINT)
                except (ProcessLookupError, PermissionError):
                    proc.send_signal(signal.SIGINT)
            else:
                proc.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM))
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        return {"stopped": True, "message": "Stop requested (graceful shutdown)."}

    def status(self) -> dict:
        """Live status snapshot (polled by the dashboard)."""
        with self._lock:
            state = self._state
            meta = dict(self._run_meta)
            reader = self._reader
            proc = self._proc
            tail = list(self._output_tail[-30:])
        if state == "idle":
            payload = {"state": "idle", "active": None,
                       "last_summary": self._last_summary, "log_tail": tail}
            return payload
        assert reader is not None
        reader.poll()
        counts = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
        for event in reader.finished.values():
            status = event.get("status", "failed")
            if status == "passed":
                counts["passed"] += 1
            elif status == "skipped":
                counts["skipped"] += 1
            elif status == "error":
                counts["error"] += 1
                counts["failed"] += 1
            else:
                counts["failed"] += 1
        running_now = [n for n in reader.started if n not in reader.finished]
        total = reader.expected_total
        finished_count = len(reader.finished)
        alive = proc is not None and proc.poll() is None
        elapsed = time.time() - self._runner_start
        return {
            "state": "stopping" if state == "stopping" else ("running" if alive else state),
            "active": {
                **meta,
                "total": total,
                "finished": finished_count,
                "counts": counts,
                "running_now": running_now[:5],
                "running_count": len(running_now),
                "elapsed": round(elapsed, 3),
                "results": sorted(reader.finished.values(),
                                  key=lambda e: e.get("end_epoch") or 0),
            },
            "last_summary": self._last_summary,
            "log_tail": tail,
        }

    def last_summary(self) -> dict | None:
        with self._lock:
            return self._last_summary

    # -- internals ----------------------------------------------------------
    def _drain_output(self, proc: subprocess.Popen) -> None:
        try:
            for line in proc.stdout or []:
                with self._lock:
                    self._output_tail.append(line.rstrip("\n")[-500:])
                    if len(self._output_tail) > 200:
                        self._output_tail = self._output_tail[-200:]
        except Exception:
            pass

    def _watchdog(self, proc: subprocess.Popen, run_id: str) -> None:
        """Wait for exit, escalate signals on stop, then finalize history."""
        exit_code: int | None = None
        stopped_early = False
        while True:
            try:
                exit_code = proc.wait(timeout=1.0)
                break
            except subprocess.TimeoutExpired:
                with self._lock:
                    stopping = self._state == "stopping"
                if stopping:
                    stopped_early = True
                    break
        if stopped_early:
            # Grace period for pytest to handle SIGINT and write history.
            try:
                exit_code = proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                try:
                    if os.name == "posix":
                        try:
                            os.killpg(proc.pid, signal.SIGTERM)
                        except (ProcessLookupError, PermissionError):
                            proc.terminate()
                    else:
                        proc.terminate()
                except Exception:
                    pass
                try:
                    exit_code = proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    try:
                        if os.name == "posix":
                            try:
                                os.killpg(proc.pid, signal.SIGKILL)
                            except (ProcessLookupError, PermissionError):
                                proc.kill()
                        else:
                            proc.kill()
                    except Exception:
                        pass
                    try:
                        exit_code = proc.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        exit_code = None
        self._finalize(run_id, exit_code, stopped_early)

    def _finalize(self, run_id: str, exit_code: int | None, stopped: bool) -> None:
        from server.history import save_history_entry
        from utils.timing import format_duration, utc_now_iso

        runner_end = time.time()
        # Prefer pytest's own history file (written by conftest sessionfinish).
        pytest_history = PROJECT_ROOT / "reports" / "execution-history" / f"{run_id}.json"
        summary: dict | None = None
        if pytest_history.exists():
            try:
                summary = json.loads(pytest_history.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                summary = None
        if summary is None:
            # Fallback: pytest died before writing history (SIGKILL/crash) --
            # reconstruct from live events, marking the unfinished interrupted.
            summary = self._fallback_history(run_id, stopped, exit_code)
            save_history_entry(summary)
        summary["runner_start_epoch"] = self._runner_start
        summary["runner_end_epoch"] = runner_end
        summary["runner_duration"] = round(runner_end - self._runner_start, 4)
        summary["runner_duration_formatted"] = format_duration(
            runner_end - self._runner_start)
        if stopped and summary.get("status") == "running":
            summary["status"] = "stopped"
        try:
            pytest_history.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
            LAST_RUN_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        except OSError:
            pass
        with self._lock:
            self._state = "idle"
            self._proc = None
            self._run_id = ""
            self._last_summary = {
                "run_id": summary.get("run_id", run_id),
                "status": summary.get("status", ""),
                "counts": summary.get("counts", {}),
                "suite_duration_formatted": summary.get("suite_duration_formatted", ""),
                "finished_at": utc_now_iso(),
            }
            self._run_meta = {}

    def _fallback_history(self, run_id: str, stopped: bool, exit_code: int | None) -> dict:
        from utils.timing import format_duration, utc_now_iso

        reader = _LiveReader(run_id)
        reader.poll()
        finished = list(reader.finished.values())
        expected: list[dict] = []
        try:
            raw = (LIVE_DIR / run_id / "expected.json").read_text(encoding="utf-8")
            expected = json.loads(raw).get("tests", [])
        except (OSError, ValueError):
            expected = []
        done_ids = {e["nodeid"] for e in finished}
        for item in expected:
            if item["nodeid"] in done_ids:
                continue
            entry = dict(item)
            entry.update({"status": "interrupted",
                          "failure": "Run ended before this test finished.",
                          "duration": 0.0, "duration_formatted": format_duration(0),
                          "start": None, "end": utc_now_iso()})
            finished.append(entry)
        counts = {"total": len(finished), "passed": 0, "failed": 0,
                  "skipped": 0, "error": 0, "interrupted": 0}
        for event in finished:
            status = event.get("status", "failed")
            if status == "passed":
                counts["passed"] += 1
            elif status == "skipped":
                counts["skipped"] += 1
            elif status == "error":
                counts["error"] += 1
                counts["failed"] += 1
            elif status == "interrupted":
                counts["interrupted"] += 1
            else:
                counts["failed"] += 1
        duration = max(0.0, time.time() - self._runner_start)
        with self._lock:
            meta = dict(self._run_meta)
        return {
            "run_id": run_id,
            "status": "stopped" if stopped else ("crashed" if exit_code not in (None, 0, 1, 5) else "completed"),
            "exitstatus": exit_code,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "suite_start": meta.get("runner_start", utc_now_iso()),
            "suite_end": utc_now_iso(),
            "suite_duration": round(duration, 4),
            "suite_duration_formatted": format_duration(duration),
            "counts": counts,
            "settings": {"browser": meta.get("browser", ""),
                         "headless": meta.get("headless", True),
                         "environment": meta.get("environment", ""),
                         "device": meta.get("device", "")},
            "command": meta.get("command", ""),
            "results": finished,
            "stats": {},
        }


RUNNER = TestRunner()
