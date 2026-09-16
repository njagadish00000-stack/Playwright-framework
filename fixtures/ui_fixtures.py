"""UI fixtures: Playwright browser / context / page lifecycle.

Scopes:
    * ``pw`` (session): the Playwright driver instance.
    * ``pw_browser`` (session): one launched browser per worker process.
    * ``pw_context`` (function): isolated browser context per test
      (video + tracing configured here).
    * ``pw_page`` (function): fresh page per test with failure artifacts.

Failure artifacts (screenshot always attempted; video/trace per settings) are
captured in ``pw_page`` finalization and attached to Allure.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from fixtures.browser_manager import (
    browser_executable_info,
    build_context_options,
    launch_browser,
    should_keep_trace,
    should_keep_video,
)
from utils.artifact_utils import (
    SCREENSHOTS_DIR,
    TRACES_DIR,
    VIDEOS_DIR,
    ensure_report_dirs,
    safe_filename,
)
from utils.logging_utils import get_logger

logger = get_logger(__name__)


@pytest.fixture(scope="session")
def pw():
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="session")
def pw_browser(pw, fw_settings, request):
    """Launch the configured browser once per worker (skips if missing)."""
    installed, details = browser_executable_info(pw, fw_settings.browser)
    logger.info("Browser check: %s", details)
    if not installed:
        if fw_settings.skip_if_no_browser:
            pytest.skip(
                f"SKIPPED: Playwright browser '{fw_settings.browser}' is not "
                f"installed in this environment. {details}",
                allow_module_level=True,
            )
        raise RuntimeError(details)
    browser = launch_browser(pw, fw_settings)
    yield browser
    try:
        browser.close()
    except Exception as exc:  # pragma: no cover - best effort cleanup
        logger.warning("Browser close failed: %s", exc)


@pytest.fixture(scope="function")
def pw_context(pw_browser, fw_settings, request):
    """Isolated context per test with video/tracing per settings."""
    ensure_report_dirs()
    from playwright.sync_api import sync_playwright as _sp  # noqa: F401

    # Device descriptors come from the Playwright instance; rebuild via registry.
    with sync_playwright() as playwright:
        options = build_context_options(playwright, fw_settings, VIDEOS_DIR)
        context = pw_browser.new_context(**options)
        context.set_default_timeout(fw_settings.timeout)
        tracing = fw_settings.trace_mode != "off"
        if tracing:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
        yield context
        nodeid = request.node.nodeid
        stem = safe_filename(nodeid)
        try:
            # ``request.node.rep_call`` is set by conftest's makereport hook.
            rep_call = getattr(request.node, "rep_call", None)
            passed = bool(rep_call and rep_call.passed)
        except Exception:
            passed = True
        if tracing:
            trace_path = TRACES_DIR / f"{stem}.zip"
            try:
                if should_keep_trace(fw_settings.trace_mode, passed):
                    context.tracing.stop(path=str(trace_path))
                    _attach_allure_file(trace_path, "Playwright trace", "application/zip")
                else:
                    context.tracing.stop()
            except Exception as exc:
                logger.warning("Tracing stop failed for %s: %s", nodeid, exc)
        # Retain or discard videos recorded by this context's pages.
        try:
            for page in context.pages:
                video = getattr(page, "video", None)
                if video is None:
                    continue
                try:
                    video_path = Path(video.path())
                except Exception:
                    continue
                if should_keep_video(fw_settings.video_mode, passed):
                    try:
                        page.close()
                    except Exception:
                        pass
                    try:
                        final = VIDEOS_DIR / f"{stem}.webm"
                        if video_path.exists():
                            shutil.move(str(video_path), str(final))
                            _attach_allure_file(final, "Page video", "video/webm")
                    except Exception as exc:
                        logger.warning("Video save failed: %s", exc)
                else:
                    try:
                        page.close()
                        video.delete()
                    except Exception:
                        pass
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Video handling failed for %s: %s", nodeid, exc)
        try:
            context.close()
        except Exception as exc:  # pragma: no cover
            logger.warning("Context close failed: %s", exc)


@pytest.fixture(scope="function")
def pw_page(pw_context, fw_settings, request, effective_base_url):
    """A fresh page per test; captures screenshots per settings."""
    page = pw_context.new_page()
    page.set_default_timeout(fw_settings.timeout)
    yield page
    nodeid = request.node.nodeid
    try:
        rep_call = getattr(request.node, "rep_call", None)
        failed = bool(rep_call and rep_call.failed)
        mode = fw_settings.screenshot_mode
        if mode == "always" or (mode == "on-failure" and failed):
            target = SCREENSHOTS_DIR / f"{safe_filename(nodeid)}.png"
            try:
                page.screenshot(path=str(target), full_page=True)
                _attach_allure_file(target, "Failure screenshot", "image/png")
                logger.info("Screenshot saved: %s", target.name)
            except Exception as exc:
                logger.warning("Screenshot failed for %s: %s", nodeid, exc)
    finally:
        try:
            page.close()
        except Exception:
            pass


def _attach_allure_file(path: Path, name: str, content_type: str) -> None:
    try:
        import allure

        if Path(path).exists():
            with open(path, "rb") as fh:
                allure.attach(fh.read(), name=name, attachment_type=content_type)
    except Exception as exc:  # pragma: no cover - attachments never break runs
        logger.warning("Allure attach failed for %s: %s", path, exc)


# -- Page-object fixtures -------------------------------------------------------
@pytest.fixture(scope="function")
def home_page(pw_page, effective_base_url):
    from pages.home_page import HomePage

    return HomePage(pw_page, effective_base_url)


@pytest.fixture(scope="function")
def forms_page(pw_page, effective_base_url):
    from pages.forms_page import FormsPage

    return FormsPage(pw_page, effective_base_url)


@pytest.fixture(scope="function")
def login_page(pw_page, effective_base_url):
    from pages.login_page import LoginPage

    return LoginPage(pw_page, effective_base_url)


@pytest.fixture(scope="function")
def users_page(pw_page, effective_base_url):
    from pages.users_page import UsersPage

    return UsersPage(pw_page, effective_base_url)
