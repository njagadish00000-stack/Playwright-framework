# Unified Playwright Automation Framework (v1.0.0)

One professional framework for **API**, **UI**, **API + UI**, and **End-to-End** test automation —
Python + Playwright + Pytest + Page Object Model + reusable API clients + Allure reporting +
precise timing + execution history + a live web dashboard.

> **New to automation or the command line?** Start with [Installation](#installation),
> then [Running tests](#running-tests), then [Writing your first test](#writing-your-first-test).
> Every command below explains **what it does**, **where to run it**, and **what to expect**.

---

## Table of contents

- [1. What this framework gives you](#1-what-this-framework-gives-you)
- [2. Project structure](#2-project-structure)
- [3. Prerequisites](#3-prerequisites)
- [4. Installation](#4-installation)
- [5. Configuration](#5-configuration)
- [6. Running tests](#6-running-tests)
- [7. The web dashboard](#7-the-web-dashboard)
- [8. Allure reporting](#8-allure-reporting)
- [9. Timing & execution history](#9-timing--execution-history)
- [10. Writing your first test](#10-writing-your-first-test)
- [11. API client guide](#11-api-client-guide)
- [12. Page Object guide](#12-page-object-guide)
- [13. Test data guide](#13-test-data-guide)
- [14. Markers guide](#14-markers-guide)
- [15. Mobile device emulation](#15-mobile-device-emulation)
- [16. Parallel execution](#16-parallel-execution)
- [17. Screenshots, videos & traces](#17-screenshots-videos--traces)
- [18. Packaging (ZIP downloads)](#18-packaging-zip-downloads)
- [19. Cleanup](#19-cleanup)
- [20. Troubleshooting](#20-troubleshooting)
- [21. Command reference (cheat sheet)](#21-command-reference-cheat-sheet)

---

## 1. What this framework gives you

| Capability | Details |
|---|---|
| **4 test categories, 1 engine** | `api_tests/`, `ui_tests/`, `api_ui_tests/`, `e2e_tests/` share config, logging, fixtures, timing, reporting |
| **API automation** | Reusable clients (`GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS`), auth, retries, schema validation, masked logging, Allure request/response attachments |
| **UI automation** | Playwright + Page Object Model, Chromium/Firefox/WebKit, headed/headless, device emulation, auto-waiting |
| **Example tests** | 54 working examples across all 4 categories, runnable offline via the bundled demo app |
| **Precise timing** | Every test: start/end/duration. Suite: real wall-clock (never summed durations) |
| **Execution history** | Every run recorded as JSON: counts, durations, settings, per-test results |
| **Failed-test rerun** | Rerun only failures; rerun-all; graceful stop — via CLI or dashboard |
| **Live dashboard** | 5 tabs (4 categories + docs), dynamic discovery, search, checkboxes, live progress, results, history, Allure, ZIP downloads |
| **Allure** | Results on every run, screenshots/videos/traces attached, environment metadata |
| **Security** | Secret masking in logs/Allure/dashboard; no arbitrary command execution; path-traversal protection |
| **Cross-platform** | Windows (CMD/PowerShell), Linux, macOS install + run scripts |

---

## 2. Project structure

```
project-root/
├── api_tests/            # API-only tests (example: test_users.py, test_posts.py, ...)
├── ui_tests/             # UI-only tests (example: test_home.py, test_forms.py, ...)
├── api_ui_tests/         # Combined API + UI tests
├── e2e_tests/            # End-to-end workflow tests
├── api/                  # Reusable API clients (base_api_client.py, users_api.py, ...)
├── pages/                # Page Objects (base_page.py, home_page.py, ...)
├── fixtures/             # Pytest fixtures (api_fixtures.py, ui_fixtures.py, browser_manager.py)
├── config/               # Settings + environment profiles
├── utils/                # Logging, timing, masking, screenshots, artifacts, test data
├── test_data/            # JSON + CSV test data (code stays data-free)
├── server/               # Dashboard backend + bundled demo app (demo_app.py)
├── dashboard/            # Dashboard frontend (index.html, css/, js/)
├── scripts/              # Acceptance/validation script (validate.py)
├── reports/              # Generated: allure-results/, screenshots/, videos/, traces/, execution-history/
├── logs/                 # Rotating framework logs
├── dist/                 # Built ZIP packages (created on demand)
├── conftest.py           # Pytest options, fixtures, timing engine, history writer
├── pytest.ini            # Markers + defaults (allure results on every run)
├── requirements.txt      # Python dependencies
├── .env.example          # Copy to .env and adjust (never commit real secrets)
├── VERSION               # Framework version (1.0.0)
├── install.sh/.bat/.ps1 # One-command installers
└── run_*.sh/.bat         # One-command test runners + start_dashboard.*
```

The four test directories (`api_tests/`, `ui_tests/`, `api_ui_tests/`, `e2e_tests/`) are the
category contract: the dashboard, markers, and history all key off them.

---

## 3. Prerequisites

| Requirement | Minimum | Notes |
|---|---|---|
| **Python** | 3.10+ (3.11 recommended) | `python --version` / `python3 --version` |
| **pip** | 23+ | Ships with Python |
| **Git** | any recent | Only needed to clone the repo |
| **OS** | Windows 10/11, Linux, macOS | All documented below |
| **Browsers** | Playwright browsers | Installed via `playwright install` (needs internet once) |
| **Allure CLI** | 2.x + Java 8+ | Optional but recommended for the full HTML report |
| **Disk / RAM** | ~1 GB free / 2 GB RAM | Browsers are the bulk of it |

Check your setup:

```bash
python3 --version     # or: python --version   (want 3.10+)
pip --version
git --version
allure --version      # optional; ok if missing (fallback report is used)
```

---

## 4. Installation

> Run all commands from the **project root** (the folder containing `requirements.txt`).
> In a terminal, `cd` there first. Example: `cd Playwright-framework`.

### 4.1 Option A — one-command installer (recommended)

**Linux / macOS (Terminal):**

```bash
./install.sh
```

**Windows (CMD):**

```bat
install.bat
```

**Windows (PowerShell):**

```powershell
.\install.ps1
```

**What it does:** creates `.venv/`, installs `requirements.txt`, installs the
Chromium/Firefox/WebKit browsers, then validates with a test collection.
**Expected result:** ends with `Installation complete` and next-step hints.
If browser download fails (offline), API tests still work; rerun the browser
command later when online.

### 4.2 Option B — manual installation (step by step)

**Step 1 — Get the code** (clone or unzip the ZIP, then enter the folder):

```bash
git clone <your-repo-url> Playwright-framework
cd Playwright-framework
```

**Step 2 — Create a virtual environment:**

Linux/macOS:
```bash
python3 -m venv .venv
```
Windows (CMD or PowerShell):
```bat
python -m venv .venv
```

**Step 3 — Activate it** (optional but convenient):

Linux/macOS: `source .venv/bin/activate` · Windows CMD: `.venv\Scripts\activate.bat` ·
Windows PowerShell: `.venv\Scripts\Activate.ps1`

> The `run_*.sh` / `run_*.bat` scripts and all examples below call
> `.venv/bin/python` (or `.venv\Scripts\python`) directly, so activation is optional.

**Step 4 — Install Python dependencies:**

Linux/macOS:
```bash
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
```
Windows:
```bat
.venv\Scripts\pip install -U pip
.venv\Scripts\pip install -r requirements.txt
```

**Step 5 — Install Playwright browsers** (one-time, needs internet):

```bash
.venv/bin/python -m playwright install chromium firefox webkit
```

Windows: replace `.venv/bin/python` with `.venv\Scripts\python`.
**Expected result:** `✔ Chromium / Firefox / WebKit installed`. On Linux you may also
need OS libraries: `.venv/bin/python -m playwright install-deps chromium firefox webkit`
(requires sudo).

**Step 6 — (Optional) Configure `.env`:**

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

The defaults already run the examples offline (bundled demo app), so this step is
only needed when pointing at your own systems. Never commit real secrets.

**Step 7 — Validate:**

```bash
.venv/bin/python -m pytest --collect-only -q | tail -2
.venv/bin/python scripts/validate.py
```

**Expected result:** collection lists **54 tests**; the validator prints a PASS table.

### 4.3 Installing Allure CLI (for the full interactive report)

The framework works without it (a fallback HTML report is generated), but the real
Allure report needs the Allure CLI + Java:

- **macOS:** `brew install allure`
- **Linux:** download from <https://allurereport.org/docs/install> (requires Java 8+)
- **Windows:** `scoop install allure` (requires Java 8+)

Verify: `allure --version`. Manual commands are in [Allure reporting](#8-allure-reporting).

---

## 5. Configuration

### 5.1 Resolution order (highest priority first)

1. **CLI flags** (`--browser firefox --headed --env qa`, …)
2. **OS environment / `.env` file** (`BROWSER=firefox`, …)
3. **Environment profile** (`config/environments.py`: `local/dev/qa/staging/prodlike`)
4. **Safe demo defaults** (bundled demo app on `127.0.0.1:8765`)

CLI and dashboard share the same `config/settings.py`, so both always agree.

### 5.2 `.env` variables (see `.env.example` for all of them)

| Variable | Default | Meaning |
|---|---|---|
| `ENVIRONMENT` | `local` | Profile name: `local/dev/qa/staging/prodlike` |
| `BASE_URL` | demo app | Web UI under test |
| `API_BASE_URL` | demo app `/api` | REST API under test |
| `USERNAME` / `PASSWORD` / `API_TOKEN` | demo creds | Auth (override with real secrets via env/CI) |
| `BROWSER` | `chromium` | `chromium/firefox/webkit` |
| `HEADLESS` | `true` | `true/false` |
| `DEVICE` | _(empty)_ | Playwright device, e.g. `iPhone 13` (empty = desktop 1280×720) |
| `TIMEOUT` / `API_TIMEOUT` | `30000` ms / `15` s | UI / API timeouts |
| `SCREENSHOT_MODE` | `on-failure` | `on-failure/always/never` |
| `VIDEO_MODE` | `retain-on-failure` | `off/on/retain-on-failure` |
| `TRACE_MODE` | `retain-on-failure` | `off/on/on-first-retry/retain-on-failure` |
| `WORKERS` | `0` | `0`=serial, `N`=workers, `auto`=all CPUs |
| `SKIP_IF_NO_BROWSER` | `true` | Skip (with reason) vs fail when a browser binary is missing |

### 5.3 Adding a new environment

1. Open `config/environments.py`, add one entry:
   ```python
   "perf": {
       "base_url": "https://perf.myapp.example",
       "api_base_url": "https://perf.myapp.example/api",
       "description": "Performance environment.",
   },
   ```
2. Use it: `pytest --env perf` or pick it in the dashboard (discovered automatically).
3. Put credentials in `.env`/CI secrets — never in the profile file.

### 5.4 Pointing at your own application

```bash
# .env
BASE_URL=https://myapp.example
API_BASE_URL=https://myapp.example/api
USERNAME=svc-automation
PASSWORD=<from CI secret>
```

If the host is not localhost, the bundled demo app is **not** auto-started.

---

## 6. Running tests

> **Where:** project root. **How:** `.venv/bin/python -m pytest …` (Linux/macOS) or
> `.venv\Scripts\python -m pytest …` (Windows). The `run_*` scripts wrap these.

### 6.1 All tests

```bash
.venv/bin/python -m pytest
# or: ./run_all.sh
```

**What:** runs every test in all 4 categories. **Expected:** summary like
`37 passed, 19 skipped` (UI tests skip only when browser binaries are missing;
with browsers installed everything passes).

### 6.2 By category

```bash
.venv/bin/python -m pytest -m api          # API only        (./run_api.sh)
.venv/bin/python -m pytest -m ui           # UI only         (./run_ui.sh)
.venv/bin/python -m pytest -m api_ui       # API+UI combined (./run_api_ui.sh)
.venv/bin/python -m pytest -m e2e          # End-to-end      (./run_e2e.sh)
```

### 6.3 Smoke / regression

```bash
.venv/bin/python -m pytest -m smoke        # fast, critical  (./run_smoke.sh)
.venv/bin/python -m pytest -m regression   # full regression (./run_regression.sh)
```

### 6.4 Marker combinations

```bash
.venv/bin/python -m pytest -m "api or ui"
.venv/bin/python -m pytest -m "smoke and api"
.venv/bin/python -m pytest -m "e2e and regression"
```

### 6.5 Specific file / class / test

```bash
.venv/bin/python -m pytest api_tests/test_users.py
.venv/bin/python -m pytest api_tests/test_users.py::TestGetUsers
.venv/bin/python -m pytest api_tests/test_users.py::TestGetUsers::test_list_users
.venv/bin/python -m pytest api_tests/test_users.py::TestGetUsers::test_list_users "ui_tests/test_home.py::TestHomePage::test_home_heading_and_banner"
```

**What:** runs exactly the given node(s). **Expected:** only those tests execute.

### 6.6 Browser / mode / environment selection

```bash
.venv/bin/python -m pytest -m ui --browser chromium --headless
.venv/bin/python -m pytest -m ui --browser firefox --headed
.venv/bin/python -m pytest -m ui --browser webkit --headless --device "iPhone 13"
.venv/bin/python -m pytest --env qa --browser firefox
```

**What:** `--browser` picks the Playwright engine; `--headed/--headless` picks the
window mode; `--env` picks the profile; `--device` enables mobile emulation.
**Expected:** the header shows the resolved config; UI tests use that browser/mode.
Browser flags are safely ignored by API-only tests.

### 6.7 Parallel execution

```bash
.venv/bin/python -m pytest -n auto
.venv/bin/python -m pytest -m api -n 4
```

**What:** runs tests across CPU cores via pytest-xdist (each worker gets an
isolated demo-app server). **Expected:** faster wall-clock; suite duration still
shows true elapsed time. See [Parallel execution](#16-parallel-execution).

### 6.8 Failed tests (CLI)

```bash
.venv/bin/python -m pytest --lf        # rerun failures from the last run (pytest cache)
.venv/bin/python -m pytest --ff        # failures first, then the rest
```

The dashboard additionally offers **Rerun Failed** / **Rerun All** backed by the
framework's own result tracking (`reports/.last_failed.json` + history).

### 6.9 Useful extras

```bash
.venv/bin/python -m pytest --collect-only -q     # list tests without running
.venv/bin/python -m pytest -m api -q             # quiet output
.venv/bin/python -m pytest --run-id my-run-1     # custom run id for history/live files
```

---

## 7. The web dashboard

Start it:

```bash
.venv/bin/python -m server.app            # → http://127.0.0.1:5000
.venv/bin/python -m server.app --port 5001   # if 5000 is busy
# or: ./start_dashboard.sh
```

**Expected:** `Dashboard: http://127.0.0.1:5000` — open that URL in a browser.

### 7.1 The five tabs

| Tab | Discovers | Notes |
|---|---|---|
| **API Tests** | `api_tests/` | via real `pytest --collect-only` |
| **UI Tests** | `ui_tests/` | same engine |
| **API + UI Tests** | `api_ui_tests/` | same engine |
| **End-to-End Tests** | `e2e_tests/` | same engine |
| **Documentation / Help** | this README | rendered HTML: headings, tables, code blocks with Copy buttons, sidebar TOC, search |

Add a test file, press **Refresh Tests** — it appears. Test names are never hard-coded.

### 7.2 Selecting tests

- Tree: category → file → test, with **Expand All / Collapse All** and per-file twisties.
- Checkboxes: single test, whole file, whole tab, or **across tabs** (selection is global).
- **Search** filters by name/file/class/category/node-id/marker with a match count + **Clear**.
- **Clear Selection** resets. Browser/mode/env/device/selection persist across reloads.

### 7.3 Running from the dashboard

| Control | Action (all real backend operations) |
|---|---|
| Run Selected (N) | Runs exactly the N checked tests |
| Run All | Runs everything collected |
| Run Smoke / Run Regression | Runs `-m smoke` / `-m regression` |
| Rerun Failed | Runs only the last run's failures (clear message if none) |
| Rerun All | Reruns the previous run's full set with its config (overridable) |
| Stop Execution | Graceful SIGINT → TERM → KILL; preserves finished results; marks the rest interrupted (asks for confirmation) |
| Browser / Mode / Env / Device / Workers | Passed into pytest → Playwright on every run |
| Copy Command | Copies the exact equivalent `pytest …` command |
| Open Allure Report | Generates (Allure CLI if present, else the labeled fallback report) and opens it |
| Refresh Results / Refresh History | Reloads results + history panels |
| Open Logs | Views `logs/*.log` with tails |
| Clear Old Results | Deletes generated screenshots/videos/traces/live/allure-results (history preserved) |
| Download … (×2) | Builds + downloads the real ZIP packages (see §18) |

### 7.4 Live execution & results

While running you see: status, run id, browser/mode/env, progress `finished/total`,
passed/failed/skipped/errors, elapsed wall-clock, progress bar, currently-running
tests, and a live runner-output tail — all polled without freezing the UI.

Afterwards: **suite summary** (totals, suite duration, average/slowest/fastest,
per-category counts, browser/mode/env), **failed-test panel** (reason + rerun +
copy names), **results table** (test, category, status with icon+text, duration,
start, end, failure excerpt, artifacts), and **execution history** (click any run
to inspect it).

---

## 8. Allure reporting

Every run writes Allure result files to `reports/allure-results/` (default in
`pytest.ini`, overridable with `--alluredir`): test name, status, real duration,
epic/feature/story labels, severity, browser/mode/env/device parameters, API
request/response/JSON attachments, screenshots, videos, traces, logs, errors,
steps — plus `environment.properties` (framework/Python/Playwright/pytest/OS/
execution-mode versions, no secrets).

**With Allure CLI installed**, the dashboard's **Open Allure Report** runs the
equivalent of:

```bash
allure generate reports/allure-results -o reports/allure-report --clean
allure open reports/allure-report
# or: allure serve reports/allure-results
```

**Without the CLI** (no `allure` binary / no Java), it generates
`reports/framework-report.html` — a clearly-labeled fallback HTML report built
from the same real results — and tells you how to install the CLI.

---

## 9. Timing & execution history

### 9.1 Individual test timing

Measured in `conftest.py::pytest_runtest_makereport` from pytest's own
`call.start`/`call.stop` perf-counters (setup → teardown wall time per test),
recorded for passed/failed/skipped/error/interrupted alike:

```
start, start_epoch | end, end_epoch | duration (= end − start) | MM:SS.mmm
```

Displayed in the dashboard results table, history details, logs, and Allure.

### 9.2 Suite wall-clock timing

Measured with a monotonic timer from `pytest_sessionstart` to
`pytest_sessionfinish` — collection, setup, teardown, xdist overhead included.
It is **never** the sum of test durations (that would be wrong under parallelism).
Displayed in the dashboard, summary, logs, history, and Allure parameters.

### 9.3 Execution history

Every run appends `reports/execution-history/<run-id>.json` (run id, date,
start/end/duration, totals, per-test results with timings, settings snapshot,
command) and updates `reports/.last_run/results.json` + `reports/.last_failed.json`.
The dashboard's history tab lists recent runs; click **View** to inspect any of them.

---

## 10. Writing your first test

### 10.1 API test (step by step)

1. **Check the client**: look in `api/` — `users_api.py`/`posts_api.py` cover the
   demo resources. Need a new one? See [API client guide](#11-api-client-guide).
2. **Add test data** (if any) under `test_data/json/` or `test_data/csv/`.
3. **Create the test** in `api_tests/`, e.g. `api_tests/test_orders.py`:
   ```python
   import allure
   import pytest

   pytestmark = [pytest.mark.api, allure.epic("API"), allure.feature("Orders API")]

   class TestOrders:
       @pytest.mark.smoke
       def test_create_order(self, users_api):
           payload = {"name": "Ann", "username": "ann_x", "email": "ann@example.com"}
           created = users_api.create_user(payload).assert_status(201).json
           assert created["username"] == "ann_x"
   ```
   - **Markers**: `@pytest.mark.api` (+ `smoke`/`regression`) — required for
     category filtering.
   - **Assertions**: use the client's fluent validators (`assert_status`,
     `assert_response_time_under`, `assert_schema`, `assert_json_path`).
4. **Run it**: `.venv/bin/python -m pytest api_tests/test_orders.py -v`
5. **View it**: dashboard results, or regenerate Allure (see §8).

### 10.2 UI test (step by step)

1. **Create the Page Object** in `pages/` (see [Page Object guide](#12-page-object-guide)).
2. **Add locators** as class constants (prefer `data-testid` selectors).
3. **Add page methods** (`open`, `login`, `submit_form`, …) on top of `BasePage`.
4. **Create the test** in `ui_tests/`, e.g. `ui_tests/test_search.py`:
   ```python
   import allure
   import pytest

   pytestmark = [pytest.mark.ui, allure.epic("UI"), allure.feature("Search")]

   class TestSearch:
       @pytest.mark.smoke
       def test_search_filters_users(self, users_page):
           users_page.open()
           users_page.wait_for_users()
           users_page.search("alice")
           assert users_page.has_user("Alice Anderson")
   ```
5. **Add markers** (`ui` + `smoke`/`regression`).
6. **Run it**: `.venv/bin/python -m pytest ui_tests/test_search.py --browser chromium`
7. **View artifacts**: failures auto-capture screenshots (+ video/trace per
   configuration) and attach them to Allure; the dashboard links them per test.

### 10.3 API + UI test (both directions)

**API setup → UI verification** (`api_ui_tests/test_api_ui_users.py` pattern):

```python
@pytest.mark.api_ui
class TestApiSetupUiVerify:
    @pytest.mark.smoke
    def test_user_created_via_api_appears_in_ui(self, users_api, users_page):
        created = users_api.create_user(random_user_payload()).assert_status(201).json
        users_page.open()
        users_page.wait_for_users()
        assert users_page.has_user(created["name"])
```

**UI action → API verification** (`api_ui_tests/test_ui_api_verify.py` pattern):
perform the workflow in the browser, then assert backend state with the API
clients (e.g. read the UI-issued token and call `/profile`).

### 10.4 E2E test (complete workflow design)

Put the journey in `e2e_tests/` with explicit phases and cleanup:

1. **API setup** — create the entities the journey needs (unique names!).
2. **UI workflow** — drive the user journey with Page Objects.
3. **API verification** — assert backend state.
4. **UI verification** — assert what the user sees.
5. **Cleanup** — `try/finally` deletes created entities; verify removal.

See `e2e_tests/test_user_workflow.py` for the full annotated example.

---

## 11. API client guide

**Use an existing client** — fixtures `users_api`, `posts_api`, `auth_api`,
`authenticated_api` are ready in tests (session-scoped, settings-driven).

**Create a new client** (minimal boilerplate — 3 steps):

1. Subclass `BaseApiClient` in `api/`:
   ```python
   from api.base_api_client import ApiResponse, BaseApiClient

   class OrdersApi(BaseApiClient):
       def create_order(self, payload: dict) -> ApiResponse:
           return self.post("/orders", json=payload)

       def get_order(self, order_id: int) -> ApiResponse:
           return self.get("/orders/{id}", path_params={"id": order_id})
   ```
2. (Optional) add a fixture in `fixtures/api_fixtures.py`:
   ```python
   @pytest.fixture(scope="session")
   def orders_api(effective_api_base_url, fw_settings) -> OrdersApi:
       client = OrdersApi(effective_api_base_url, timeout=fw_settings.api_timeout)
       yield client
       client.close()
   ```
3. Use it in tests with fluent validators. Logging, secret-masking, retries,
   timeouts, and Allure attachments come free from the base class.

Supported: query/path params, headers, cookies, JSON/form/multipart/file-upload
bodies, bearer/basic/custom auth, status/header/JSON/response-time/schema validation.

---

## 12. Page Object guide

**Use an existing page** — fixtures `home_page`, `forms_page`, `login_page`,
`users_page` are ready in tests.

**Create a new Page Object** (4 steps):

1. Subclass `BasePage` in `pages/`:
   ```python
   from pages.base_page import BasePage

   class CheckoutPage(BasePage):
       url_path = "/checkout"
       PAY_BUTTON = "[data-testid='btn-pay']"
       TOTAL_LABEL = "[data-testid='order-total']"

       def pay(self) -> None:
           self.click(self.PAY_BUTTON)

       def total(self) -> str:
           return self.text(self.TOTAL_LABEL)
   ```
2. **Locators**: class constants, `data-testid` preferred; role/text fallbacks
   via `by_role`/`by_text` helpers.
3. **Methods**: one user intent per method; rely on Playwright auto-waiting
   (no `time.sleep`); explicit waits only when truly needed.
4. (Optional) add a fixture in `fixtures/ui_fixtures.py` mirroring the existing ones.

`BasePage` provides: navigation, locator shortcuts, click/fill/select/check,
reads, `expect`-based assertions, file upload/download, screenshots, storage
state, and JS evaluation.

---

## 13. Test data guide

| Source | Location | Loader |
|---|---|---|
| JSON | `test_data/json/*.json` | `load_json("users.json")` |
| CSV | `test_data/csv/*.csv` | `load_csv("users.csv")` |
| Generated | — | `random_user_payload()`, `random_post_payload()`, `random_email()` |
| Secrets/env | `.env` / CI | `fw_settings.username/password/api_token` fixtures |

Rules: keep data out of test code; uniquify created entities
(`unique_suffix()`); clean up what you create (`try/finally`); never commit secrets.

---

## 14. Markers guide

Registered in `pytest.ini`: `api`, `ui`, `api_ui`, `e2e`, `smoke`, `regression`.
Every test needs **one category marker** + (usually) `smoke` or `regression`:

```python
@pytest.mark.api
@pytest.mark.smoke
def test_list_users(users_api): ...
```

Markers compose (`-m "smoke and api"`), drive the dashboard tabs, and appear in
discovery, history, and Allure. Adding a marker = 1 line in `pytest.ini` + use it.

---

## 15. Mobile device emulation

```bash
.venv/bin/python -m pytest -m ui --device "iPhone 13"
.venv/bin/python -m pytest -m ui --device "Pixel 5" --browser chromium
```

Or type the device into the dashboard's **Device** box. Uses Playwright's device
descriptors (viewport, user agent, touch, etc.); unknown names fail fast with the
available list. Empty = desktop 1280×720. Works with headed/headless and all browsers.

---

## 16. Parallel execution

```bash
.venv/bin/python -m pytest -n auto     # all CPUs
.venv/bin/python -m pytest -n 4        # fixed workers
```

Powered by pytest-xdist. Design notes: per-test timing stays exact (measured in
each worker); suite duration is true wall-clock; each worker gets a **private
isolated demo-app server** (no shared-state flakes); live progress aggregates all
workers; avoid writing to shared files from tests.

---

## 17. Screenshots, videos & traces

| Artifact | Setting | Values | Where |
|---|---|---|---|
| Screenshots | `SCREENSHOT_MODE` / `--screenshot-mode` | `on-failure` (default), `always`, `never` | `reports/screenshots/` + Allure |
| Video (webm) | `VIDEO_MODE` / `--video-mode` | `off`, `on`, `retain-on-failure` (default) | `reports/videos/` + Allure |
| Trace (zip) | `TRACE_MODE` / `--trace-mode` | `off`, `on`, `on-first-retry`, `retain-on-failure` (default) | `reports/traces/` + Allure |

The dashboard links each test to its artifacts; open traces with
`playwright show-trace reports/traces/<file>.zip`. Disabled modes record nothing.

---

## 18. Packaging (ZIP downloads)

Two real, validated packages (built by `server/packaging.py`, downloadable from
the dashboard or built locally):

```bash
.venv/bin/python -c "from server.packaging import build_package; print(build_package())"
.venv/bin/python -c "from server.packaging import build_package; print(build_package(without_examples=True))"
```

| Package | Contains |
|---|---|
| `dist/playwright-framework-<ver>-complete.zip` | Framework + dashboard + README + scripts + **all example tests** |
| `dist/playwright-framework-<ver>-no-examples.zip` | Framework + dashboard + README + scripts, **no example tests** (empty test dirs kept with `__init__.py`) |

Both exclude: `.venv`, caches, generated reports/logs/history, `.env`/secrets,
browser binaries. Contents are validated programmatically after every build.

---

## 19. Cleanup

- **Dashboard**: **Clear Old Results** removes generated screenshots/videos/traces,
  live files, last-run snapshot, and Allure results (history preserved).
- **API**: `POST /api/cleanup` with `{action: "results"}` (same), or
  `{max_age_days: 14, include_history: false, include_logs: false}` for aged cleanup.
- Source, config, test data, and README are never touched by cleanup.

---

## 20. Troubleshooting

| Symptom | Cause & fix |
|---|---|
| `playwright install …` fails (offline) | API tests + dashboard still work. Install browsers when online; UI tests skip with a clear reason until then. |
| UI tests **skip** with "browser not installed" | Expected without browser binaries. Run `playwright install chromium firefox webkit`. Set `SKIP_IF_NO_BROWSER=false` to turn skips into hard errors. |
| `allure: command not found` | Install Allure CLI + Java (§4.3); until then the labeled fallback HTML report is used. |
| Dashboard port busy | `python -m server.app --port 5001`. |
| `Unknown environment 'x'` | Add it to `config/environments.py` (§5.3). |
| `Unknown device 'x'` | The error lists valid Playwright device names — copy one exactly. |
| Flaky parallel runs in your own tests | Don't share mutable state/files between tests; uniquify entities. |
| Need debug logs | `LOG_LEVEL=DEBUG` in `.env`; see `logs/framework.log` (rotating, secrets masked). |

---

## 21. Command reference (cheat sheet)

```bash
# Install
./install.sh                                   # Linux/macOS
install.bat                                    # Windows CMD
.\install.ps1                                  # Windows PowerShell

# Run (Linux/macOS shown; Windows: .venv\Scripts\python …)
.venv/bin/python -m pytest                     # all tests
.venv/bin/python -m pytest -m api              # API only
.venv/bin/python -m pytest -m ui               # UI only
.venv/bin/python -m pytest -m api_ui           # API+UI only
.venv/bin/python -m pytest -m e2e              # E2E only
.venv/bin/python -m pytest -m smoke            # smoke
.venv/bin/python -m pytest -m regression       # regression
.venv/bin/python -m pytest api_tests/test_users.py::TestGetUsers::test_list_users
.venv/bin/python -m pytest --browser firefox --headed --env qa -n auto
.venv/bin/python -m pytest --lf                # rerun last failures

# Dashboard + Allure + packages
.venv/bin/python -m server.app                 # dashboard → http://127.0.0.1:5000
allure generate reports/allure-results -o reports/allure-report --clean
allure open reports/allure-report
.venv/bin/python scripts/validate.py           # acceptance checks
```

**Versions:** framework v1.0.0 · Python ≥3.10 · Playwright ≥1.40 · Pytest ≥7.4 ·
backend Flask · frontend dependency-free HTML/CSS/JS.
