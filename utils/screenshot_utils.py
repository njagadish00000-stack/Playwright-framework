"""Screenshot capture helpers (used by fixtures and page objects)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from utils.artifact_utils import SCREENSHOTS_DIR, ensure_report_dirs, safe_filename
from utils.logging_utils import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from playwright.sync_api import Page

logger = get_logger(__name__)


def capture_screenshot(page: "Page", nodeid: str, suffix: str = "") -> Path | None:
    """Capture a full-page screenshot for *nodeid*; returns the file path."""
    ensure_report_dirs()
    target = SCREENSHOTS_DIR / f"{safe_filename(nodeid, suffix)}.png"
    try:
        page.screenshot(path=str(target), full_page=True)
        logger.info("Screenshot saved: %s", target.name)
        return target
    except Exception as exc:  # screenshots must never break the test run
        logger.warning("Screenshot failed for %s: %s", nodeid, exc)
        return None


def attach_screenshot_to_allure(path: Path | None, name: str = "Screenshot") -> None:
    if path is None or not Path(path).exists():
        return
    try:
        import allure

        allure.attach.file(str(path), name=name, attachment_type=allure.attachment_type.PNG)
    except Exception as exc:  # pragma: no cover
        logger.warning("Allure screenshot attach failed: %s", exc)
