"""API + UI example tests: UI action -> API verification."""

import allure
import pytest

pytestmark = [pytest.mark.api_ui, allure.epic("API + UI"),
              allure.feature("UI action, API verification")]


@allure.story("UI performs login, API verifies backend state")
class TestUiActionApiVerify:
    @pytest.mark.smoke
    def test_ui_login_token_accepted_by_api(self, login_page, auth_api, fw_settings):
        """The token issued during a UI login is valid for direct API calls."""
        with allure.step("Log in through the web UI"):
            login_page.open()
            login_page.login(fw_settings.username, fw_settings.password)
            assert fw_settings.username in login_page.greeting()
        with allure.step("Read the session token from the browser"):
            token = login_page.evaluate("() => localStorage.getItem('demo_token')")
            assert token, "UI login did not store a token in localStorage"
        with allure.step("Verify the token against the API"):
            auth_api.set_bearer_token(token)
            profile = auth_api.profile().assert_status(200).json
            assert profile["username"] == fw_settings.username

    @pytest.mark.regression
    def test_users_page_renders_live_api_data(self, users_page, users_api):
        """The Users page renders exactly the users returned by the API."""
        with allure.step("Fetch users from the API"):
            api_names = sorted(u["name"] for u in users_api.list_users().assert_status(200).json)
        with allure.step("Render the Users page"):
            users_page.open()
            users_page.wait_for_users()
            ui_names = sorted(users_page.user_names())
        assert ui_names == api_names
