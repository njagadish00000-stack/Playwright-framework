"""UI example tests: navigation, content and download."""

import allure
import pytest

pytestmark = [pytest.mark.ui, allure.epic("UI"), allure.feature("Home page")]


@allure.story("Navigation and content")
class TestHomePage:
    @pytest.mark.smoke
    @allure.severity(allure.severity_level.CRITICAL)
    def test_home_heading_and_banner(self, home_page):
        """Home page shows its heading and welcome banner."""
        with allure.step("Open the home page"):
            home_page.open()
        with allure.step("Verify heading and banner"):
            assert "Welcome to the Demo App" in home_page.heading_text()
            home_page.assert_visible(home_page.WELCOME_BANNER)
            assert home_page.feature_card_count() == 3

    @pytest.mark.smoke
    def test_main_navigation_links(self, home_page):
        """All main navigation links are present and clickable."""
        home_page.open()
        assert home_page.nav_link_texts() == ["Home", "Forms", "Login", "Users"]
        with allure.step("Navigate to the Forms page via the nav"):
            home_page.click_nav("Forms")
            home_page.assert_url_contains("/forms")

    @pytest.mark.regression
    def test_page_title_and_footer(self, home_page):
        home_page.open()
        home_page.assert_title_contains("Demo App")
        home_page.assert_visible(home_page.FOOTER)

    @pytest.mark.regression
    def test_sample_file_download(self, home_page, tmp_path):
        """A file can be downloaded via the UI."""
        home_page.open()
        target = tmp_path / "sample.txt"
        home_page.download("[data-testid='link-download']", target)
        assert target.exists()
        assert "automation testing" in target.read_text(encoding="utf-8")
