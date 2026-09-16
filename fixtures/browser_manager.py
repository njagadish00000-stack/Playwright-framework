"""Playwright browser lifecycle helpers (single implementation).

The dashboard and the CLI share this code path: settings flow
``dashboard/CLI -> Settings -> playwright_launch_options() -> launch`` so the
selected browser and headed/headless mode are what Playwright receives.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.logging_utils import get_logger

logger = get_logger(__name__)


def browser_executable_info(playwright, browser_name: str) -> tuple[bool, str]:
    """Check whether the Playwright browser binary exists (no launch).

    Returns:
        (installed, details_message)
    """
    try:
        browser_type = getattr(playwright, browser_name)
    except AttributeError:
        return False, f"Unknown browser '{browser_name}'"
    try:
        exe_path = str(browser_type.executable_path)
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"Could not resolve executable path: {exc}"
    exists = Path(exe_path).exists()
    if exists:
        return True, f"{browser_name} executable found: {exe_path}"
    return (
        False,
        f"{browser_name} executable NOT found at {exe_path}. "
        f"Install with: playwright install {browser_name}",
    )


def launch_browser(playwright, settings):
    """Launch the configured browser. Raises a clear error if it fails."""
    browser_type = getattr(playwright, settings.browser)
    options = settings.playwright_launch_options()
    logger.info(
        "Launching Playwright browser=%s headless=%s options=%s",
        settings.browser, settings.headless, options,
    )
    try:
        browser = browser_type.launch(**options)
    except Exception as exc:
        message = str(exc)
        if "Executable doesn't exist" in message or "Has the browser been installed" in message:
            raise RuntimeError(
                f"Playwright browser '{settings.browser}' is not installed. "
                f"Run: playwright install {settings.browser} "
                f"(docs: README 'Install Playwright browsers'). Original error: {exc}"
            ) from exc
        raise
    return browser


def build_context_options(playwright, settings, videos_dir: Path) -> dict[str, Any]:
    """Build ``browser.new_context()`` kwargs from settings + device."""
    options: dict[str, Any] = {}
    if settings.device:
        devices = playwright.devices
        if settings.device not in devices:
            available = ", ".join(sorted(devices.keys()))
            raise ValueError(
                f"Unknown device '{settings.device}'. "
                f"Available devices include: {available[:500]}..."
            )
        options.update(devices[settings.device])
        logger.info("Using Playwright device descriptor: %s", settings.device)
    else:
        options.setdefault("viewport", {"width": 1280, "height": 720})
    if settings.video_mode != "off":
        videos_dir.mkdir(parents=True, exist_ok=True)
        options["record_video_dir"] = str(videos_dir)
        options.setdefault("record_video_size", {"width": 1280, "height": 720})
    options.setdefault("accept_downloads", True)
    return options


def should_keep_video(video_mode: str, passed: bool) -> bool:
    if video_mode == "on":
        return True
    if video_mode == "retain-on-failure":
        return not passed
    return False


def should_keep_trace(trace_mode: str, passed: bool) -> bool:
    if trace_mode == "on":
        return True
    if trace_mode in {"retain-on-failure", "on-first-retry"}:
        return not passed
    return False
