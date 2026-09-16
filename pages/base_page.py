"""Base page object with shared Playwright helpers.

All page objects inherit from :class:`BasePage`, which relies on Playwright's
automatic waiting and adds explicit-wait, screenshot, download, upload and
locator utilities on top.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.sync_api import Locator, Page, expect

from utils.logging_utils import get_logger

logger = get_logger(__name__)


class BasePage:
    """Base class for all page objects."""

    url_path: str = "/"

    def __init__(self, page: Page, base_url: str = "") -> None:
        self.page = page
        self.base_url = (base_url or "").rstrip("/")

    # -- navigation --------------------------------------------------------
    @property
    def url(self) -> str:
        return f"{self.base_url}{self.url_path}"

    def open(self) -> "BasePage":
        logger.info("Opening %s", self.url)
        self.page.goto(self.url)
        self.wait_for_load()
        return self

    def wait_for_load(self, state: str = "domcontentloaded") -> None:
        self.page.wait_for_load_state(state)

    # -- locators ----------------------------------------------------------
    def locate(self, selector: str, **kwargs) -> Locator:
        return self.page.locator(selector, **kwargs)

    def by_role(self, role: str, **kwargs) -> Locator:
        return self.page.get_by_role(role, **kwargs)  # type: ignore[arg-type]

    def by_text(self, text: str, **kwargs) -> Locator:
        return self.page.get_by_text(text, **kwargs)

    def by_label(self, label: str, **kwargs) -> Locator:
        return self.page.get_by_label(label, **kwargs)

    def by_test_id(self, test_id: str) -> Locator:
        return self.page.get_by_test_id(test_id)

    # -- interactions (auto-waiting; explicit waits only when needed) ------
    def click(self, selector: str, **kwargs) -> None:
        logger.info("Click: %s", selector)
        self.locate(selector).click(**kwargs)

    def fill(self, selector: str, value: str, **kwargs) -> None:
        logger.info("Fill: %s", selector)
        self.locate(selector).fill(value, **kwargs)

    def type(self, selector: str, value: str, **kwargs) -> None:
        self.locate(selector).press_sequentially(value, **kwargs)

    def select_option(self, selector: str, value: str | list[str], **kwargs) -> None:
        self.locate(selector).select_option(value, **kwargs)

    def check(self, selector: str, **kwargs) -> None:
        self.locate(selector).check(**kwargs)

    def uncheck(self, selector: str, **kwargs) -> None:
        self.locate(selector).uncheck(**kwargs)

    def hover(self, selector: str, **kwargs) -> None:
        self.locate(selector).hover(**kwargs)

    def wait_for_visible(self, selector: str, timeout: int | None = None) -> Locator:
        locator = self.locate(selector)
        locator.wait_for(state="visible", timeout=timeout)
        return locator

    def wait_for_text(self, selector: str, text: str, timeout: int | None = None) -> None:
        expect(self.locate(selector)).to_contain_text(text, timeout=timeout)

    # -- reads --------------------------------------------------------------
    def text(self, selector: str) -> str:
        return (self.locate(selector).inner_text() or "").strip()

    def input_value(self, selector: str) -> str:
        return self.locate(selector).input_value()

    def is_visible(self, selector: str) -> bool:
        return self.locate(selector).is_visible()

    def count(self, selector: str) -> int:
        return self.locate(selector).count()

    def title(self) -> str:
        return self.page.title()

    # -- assertions ----------------------------------------------------------
    def assert_visible(self, selector: str, timeout: int | None = None) -> None:
        expect(self.locate(selector)).to_be_visible(timeout=timeout)

    def assert_text(self, selector: str, text: str, timeout: int | None = None) -> None:
        expect(self.locate(selector)).to_contain_text(text, timeout=timeout)

    def assert_title_contains(self, text: str, timeout: int | None = None) -> None:
        expect(self.page).to_have_title(f".*{text}.*", timeout=timeout)

    def assert_url_contains(self, text: str, timeout: int | None = None) -> None:
        expect(self.page).to_have_url(f".*{text}.*", timeout=timeout)

    # -- files ----------------------------------------------------------------
    def upload_file(self, selector: str, file_path: str | Path) -> None:
        logger.info("Upload %s -> %s", file_path, selector)
        self.locate(selector).set_input_files(str(file_path))

    def download(self, selector: str, save_as: str | Path) -> Path:
        logger.info("Download via %s", selector)
        with self.page.expect_download() as download_info:
            self.locate(selector).click()
        download = download_info.value
        target = Path(save_as)
        download.save_as(str(target))
        return target

    # -- screenshots ------------------------------------------------------------
    def screenshot(self, name: str) -> Path:
        from utils.artifact_utils import SCREENSHOTS_DIR, ensure_report_dirs
        from utils.screenshot_utils import attach_screenshot_to_allure

        ensure_report_dirs()
        target = SCREENSHOTS_DIR / f"{name}.png"
        self.page.screenshot(path=str(target), full_page=True)
        attach_screenshot_to_allure(target, name=name)
        return target

    # -- storage / session -------------------------------------------------------
    def storage_state(self, path: str | Path) -> Path:
        target = Path(path)
        self.page.context.storage_state(path=str(target))
        return target

    def evaluate(self, expression: str, arg: Any = None) -> Any:
        return self.page.evaluate(expression, arg)
