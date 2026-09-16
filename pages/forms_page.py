"""Forms page object: inputs, dropdowns, checkboxes, submission."""

from __future__ import annotations

from pages.base_page import BasePage


class FormsPage(BasePage):
    url_path = "/forms"

    NAME_INPUT = "[data-testid='input-name']"
    EMAIL_INPUT = "[data-testid='input-email']"
    ROLE_SELECT = "[data-testid='select-role']"
    NEWSLETTER_CHECKBOX = "[data-testid='check-newsletter']"
    BIO_TEXTAREA = "[data-testid='textarea-bio']"
    SUBMIT_BUTTON = "[data-testid='btn-submit']"
    SUCCESS_MESSAGE = "[data-testid='form-success']"
    VALIDATION_ERROR = "[data-testid='form-error']"
    RESULT_TABLE = "[data-testid='submitted-data']"

    def submit_form(
        self,
        name: str,
        email: str,
        role: str = "user",
        bio: str = "",
        newsletter: bool = True,
    ) -> None:
        self.fill(self.NAME_INPUT, name)
        self.fill(self.EMAIL_INPUT, email)
        self.select_option(self.ROLE_SELECT, role)
        if bio:
            self.fill(self.BIO_TEXTAREA, bio)
        if newsletter:
            self.check(self.NEWSLETTER_CHECKBOX)
        else:
            self.uncheck(self.NEWSLETTER_CHECKBOX)
        self.click(self.SUBMIT_BUTTON)

    def success_message(self) -> str:
        self.wait_for_visible(self.SUCCESS_MESSAGE)
        return self.text(self.SUCCESS_MESSAGE)

    def error_message(self) -> str:
        self.wait_for_visible(self.VALIDATION_ERROR)
        return self.text(self.VALIDATION_ERROR)
