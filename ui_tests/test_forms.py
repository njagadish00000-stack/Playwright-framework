"""UI example tests: form interaction, validation, upload."""

import allure
import pytest

pytestmark = [pytest.mark.ui, allure.epic("UI"), allure.feature("Forms page")]


@allure.story("Form submission")
class TestForms:
    @pytest.mark.smoke
    @allure.severity(allure.severity_level.CRITICAL)
    def test_submit_valid_form(self, forms_page):
        """A valid form submission shows a success message and echo table."""
        forms_page.open()
        with allure.step("Fill and submit the form"):
            forms_page.submit_form(
                name="Playwright User",
                email="pwuser@example.com",
                role="admin",
                bio="Loves automation.",
                newsletter=True,
            )
        with allure.step("Verify the success message"):
            message = forms_page.success_message()
            assert "Playwright User" in message
            forms_page.assert_visible(forms_page.RESULT_TABLE)

    @pytest.mark.regression
    def test_form_requires_name(self, forms_page):
        forms_page.open()
        forms_page.submit_form(name="", email="noname@example.com")
        assert "Name is required" in forms_page.error_message()

    @pytest.mark.regression
    def test_form_rejects_bad_email(self, forms_page):
        forms_page.open()
        forms_page.submit_form(name="Bad Email", email="not-an-email")
        assert "valid email" in forms_page.error_message()

    @pytest.mark.regression
    def test_role_dropdown_options(self, forms_page):
        """The role dropdown exposes exactly the supported roles."""
        forms_page.open()
        options = forms_page.locate(f"{forms_page.ROLE_SELECT} option").all_inner_texts()
        assert [o.strip() for o in options] == ["user", "admin", "editor"]

    @pytest.mark.regression
    def test_file_input_accepts_upload(self, forms_page, tmp_path):
        """The avatar file input accepts a file (upload widget works)."""
        avatar = tmp_path / "avatar.txt"
        avatar.write_text("fake-avatar-bytes", encoding="utf-8")
        forms_page.open()
        forms_page.upload_file("[data-testid='input-avatar']", avatar)
        value = forms_page.input_value("[data-testid='input-avatar']")
        assert "avatar" in value
