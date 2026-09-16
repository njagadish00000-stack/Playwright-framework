"""UI example tests: login flow (success, failure, logout)."""

import allure
import pytest

pytestmark = [pytest.mark.ui, allure.epic("UI"), allure.feature("Login page")]


@allure.story("Login flow")
class TestLogin:
    @pytest.mark.smoke
    @allure.severity(allure.severity_level.CRITICAL)
    def test_login_with_valid_credentials(self, login_page, fw_settings):
        """Valid credentials show the profile greeting."""
        login_page.open()
        with allure.step("Log in with demo credentials"):
            login_page.login(fw_settings.username, fw_settings.password)
        with allure.step("Verify the greeting"):
            assert fw_settings.username in login_page.greeting()

    @pytest.mark.regression
    def test_login_with_bad_password_shows_error(self, login_page):
        login_page.open()
        login_page.login("demo", "wrong-password")
        assert "invalid credentials" in login_page.login_error().lower()

    @pytest.mark.regression
    def test_logout_returns_to_login_form(self, login_page, fw_settings):
        login_page.open()
        login_page.login(fw_settings.username, fw_settings.password)
        assert fw_settings.username in login_page.greeting()
        with allure.step("Log out"):
            login_page.logout()
        login_page.assert_visible(login_page.USERNAME_INPUT)
