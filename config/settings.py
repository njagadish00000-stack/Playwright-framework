"""Central framework settings.

Resolution order (highest priority first):
    1. Explicit CLI options (passed to :class:`Settings` via ``overrides``).
    2. OS environment variables / ``.env`` file values.
    3. Environment-profile defaults from :mod:`config.environments`.
    4. Hard-coded safe demo defaults.

Both the pytest run (``conftest.py``) and the dashboard backend
(``server/app.py``) build their configuration from this module, so CLI and
dashboard always share one consistent configuration mechanism.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from config.environments import DEFAULT_ENVIRONMENT, get_environment_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent

VALID_BROWSERS = ("chromium", "firefox", "webkit")
VALID_SCREENSHOT_MODES = ("on-failure", "always", "never")
VALID_VIDEO_MODES = ("off", "on", "retain-on-failure")
VALID_TRACE_MODES = ("off", "on", "on-first-retry", "retain-on-failure")


def _str_to_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _load_dotenv() -> None:
    """Load ``.env`` from the project root if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dotenv is a hard dependency
        return
    load_dotenv(PROJECT_ROOT / ".env", override=False)


_load_dotenv()


def framework_version() -> str:
    try:
        return (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


@dataclass
class Settings:
    """Resolved, validated framework settings."""

    environment: str = DEFAULT_ENVIRONMENT
    base_url: str = ""
    api_base_url: str = ""
    username: str = "demo"
    password: str = "demo123"
    api_token: str = ""
    browser: str = "chromium"
    headless: bool = True
    device: str = ""
    slow_mo: int = 0
    timeout: int = 30000
    api_timeout: int = 15
    expect_timeout: int = 10000
    screenshot_mode: str = "on-failure"
    video_mode: str = "retain-on-failure"
    trace_mode: str = "retain-on-failure"
    workers: str = "0"
    skip_if_no_browser: bool = True
    log_level: str = "INFO"
    demo_app_host: str = "127.0.0.1"
    demo_app_port: int = 8765

    def __post_init__(self) -> None:
        self.environment = (self.environment or DEFAULT_ENVIRONMENT).lower()
        self.browser = (self.browser or "chromium").lower()
        if self.browser not in VALID_BROWSERS:
            raise ValueError(
                f"Invalid browser '{self.browser}'. Valid: {', '.join(VALID_BROWSERS)}"
            )
        if self.screenshot_mode not in VALID_SCREENSHOT_MODES:
            raise ValueError(f"Invalid screenshot mode: {self.screenshot_mode}")
        if self.video_mode not in VALID_VIDEO_MODES:
            raise ValueError(f"Invalid video mode: {self.video_mode}")
        if self.trace_mode not in VALID_TRACE_MODES:
            raise ValueError(f"Invalid trace mode: {self.trace_mode}")
        # Profile defaults fill in URLs that were not explicitly provided.
        profile = get_environment_config(self.environment)
        self.base_url = (self.base_url or profile["base_url"]).rstrip("/")
        self.api_base_url = (self.api_base_url or profile["api_base_url"]).rstrip("/")

    @property
    def headed(self) -> bool:
        return not self.headless

    def playwright_launch_options(self) -> dict:
        """Options passed to ``browser_type.launch()`` -- single source of truth.

        Both headed/headless dashboard + CLI selections flow through here, so
        the configured mode is what Playwright actually receives.
        """
        options: dict = {"headless": self.headless}
        if self.slow_mo:
            options["slow_mo"] = self.slow_mo
        return options

    def to_safe_dict(self) -> dict:
        """Settings as a dict with secrets masked (safe for logs/dashboard)."""
        from utils.masking import mask_secret

        return {
            "environment": self.environment,
            "base_url": self.base_url,
            "api_base_url": self.api_base_url,
            "username": self.username,
            "password": mask_secret(self.password),
            "api_token": mask_secret(self.api_token),
            "browser": self.browser,
            "headless": self.headless,
            "headed": self.headed,
            "device": self.device,  # raw value ("" = default viewport); display layers map it
            "timeout": self.timeout,
            "api_timeout": self.api_timeout,
            "screenshot_mode": self.screenshot_mode,
            "video_mode": self.video_mode,
            "trace_mode": self.trace_mode,
            "framework_version": framework_version(),
        }

    def to_env(self) -> dict[str, str]:
        """Export settings as environment variables for subprocess runs."""
        return {
            "ENVIRONMENT": self.environment,
            "BASE_URL": self.base_url,
            "API_BASE_URL": self.api_base_url,
            "BROWSER": self.browser,
            "HEADLESS": "true" if self.headless else "false",
            "DEVICE": self.device,
            "TIMEOUT": str(self.timeout),
            "API_TIMEOUT": str(self.api_timeout),
            "SCREENSHOT_MODE": self.screenshot_mode,
            "VIDEO_MODE": self.video_mode,
            "TRACE_MODE": self.trace_mode,
        }


def get_settings(overrides: dict | None = None) -> Settings:
    """Build :class:`Settings` from env vars + optional explicit overrides.

    Args:
        overrides: Highest-priority values (e.g. parsed CLI options or
            dashboard selections). ``None`` values are ignored.
    """
    env = os.environ
    data: dict = {
        "environment": env.get("ENVIRONMENT", DEFAULT_ENVIRONMENT),
        "base_url": env.get("BASE_URL", ""),
        "api_base_url": env.get("API_BASE_URL", ""),
        "username": env.get("USERNAME", "demo"),
        "password": env.get("PASSWORD", "demo123"),
        "api_token": env.get("API_TOKEN", ""),
        "browser": env.get("BROWSER", "chromium"),
        "headless": _str_to_bool(env.get("HEADLESS", "true"), True),
        "device": env.get("DEVICE", ""),
        "slow_mo": int(env.get("SLOW_MO", "0") or 0),
        "timeout": int(env.get("TIMEOUT", "30000") or 30000),
        "api_timeout": int(env.get("API_TIMEOUT", "15") or 15),
        "expect_timeout": int(env.get("EXPECT_TIMEOUT", "10000") or 10000),
        "screenshot_mode": env.get("SCREENSHOT_MODE", "on-failure"),
        "video_mode": env.get("VIDEO_MODE", "retain-on-failure"),
        "trace_mode": env.get("TRACE_MODE", "retain-on-failure"),
        "workers": env.get("WORKERS", "0"),
        "skip_if_no_browser": _str_to_bool(env.get("SKIP_IF_NO_BROWSER", "true"), True),
        "log_level": env.get("LOG_LEVEL", "INFO"),
        "demo_app_host": env.get("DEMO_APP_HOST", "127.0.0.1"),
        "demo_app_port": int(env.get("DEMO_APP_PORT", "8765") or 8765),
    }
    for key, value in (overrides or {}).items():
        if value is not None and key in data:
            data[key] = value
    return Settings(**data)


@lru_cache(maxsize=1)
def cached_settings() -> Settings:
    """Cached default settings (no overrides)."""
    return get_settings()
