"""Home page object for the demo web application."""

from __future__ import annotations

from pages.base_page import BasePage


class HomePage(BasePage):
    url_path = "/"

    # Locators
    HEADING = "h1[data-testid='home-heading']"
    NAV_LINKS = "nav[data-testid='main-nav'] a"
    WELCOME_BANNER = "[data-testid='welcome-banner']"
    FEATURE_CARDS = "[data-testid='feature-card']"
    FOOTER = "footer[data-testid='page-footer']"

    def heading_text(self) -> str:
        return self.text(self.HEADING)

    def nav_link_texts(self) -> list[str]:
        return [t.strip() for t in self.locate(self.NAV_LINKS).all_inner_texts()]

    def click_nav(self, name: str) -> None:
        self.page.get_by_role("link", name=name).click()

    def feature_card_count(self) -> int:
        return self.count(self.FEATURE_CARDS)
