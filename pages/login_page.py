"""Login page object."""

from __future__ import annotations

from pages.base_page import BasePage


class LoginPage(BasePage):
    url_path = "/login"

    USERNAME_INPUT = "[data-testid='input-username']"
    PASSWORD_INPUT = "[data-testid='input-password']"
    LOGIN_BUTTON = "[data-testid='btn-login']"
    ERROR_MESSAGE = "[data-testid='login-error']"
    PROFILE_GREETING = "[data-testid='profile-greeting']"
    LOGOUT_BUTTON = "[data-testid='btn-logout']"

    def login(self, username: str, password: str) -> None:
        self.fill(self.USERNAME_INPUT, username)
        self.fill(self.PASSWORD_INPUT, password)
        self.click(self.LOGIN_BUTTON)

    def login_error(self) -> str:
        self.wait_for_visible(self.ERROR_MESSAGE)
        return self.text(self.ERROR_MESSAGE)

    def greeting(self) -> str:
        self.wait_for_visible(self.PROFILE_GREETING)
        return self.text(self.PROFILE_GREETING)

    def logout(self) -> None:
        self.click(self.LOGOUT_BUTTON)
