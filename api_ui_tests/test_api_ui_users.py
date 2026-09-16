"""API + UI example tests: API setup -> UI verification."""

import allure
import pytest

from utils.data_utils import random_user_payload

pytestmark = [pytest.mark.api_ui, allure.epic("API + UI"),
              allure.feature("API setup, UI verification")]


@allure.story("API creates data, UI verifies it")
class TestApiSetupUiVerify:
    @pytest.mark.smoke
    @allure.severity(allure.severity_level.CRITICAL)
    def test_user_created_via_api_appears_in_ui(self, users_api, users_page):
        """A user created through the REST API is visible in the Users table."""
        payload = random_user_payload()
        with allure.step(f"Create user via API: {payload['username']}"):
            created = users_api.create_user(payload).assert_status(201).json
        with allure.step("Verify the user in the web UI"):
            users_page.open()
            users_page.wait_for_users()
            assert users_page.has_user(created["name"]), (
                f"User {created['name']} not visible in UI table")
            users_page.search(created["username"])
            assert users_page.has_user(created["name"])

    @pytest.mark.regression
    def test_user_updated_via_api_reflected_in_ui(self, users_api, users_page):
        """A user renamed through the REST API shows the new name in the UI."""
        payload = random_user_payload()
        created = users_api.create_user(payload).assert_status(201).json
        with allure.step("Rename the user via API"):
            users_api.patch_user(created["id"], {"name": "Renamed Via API"}).assert_status(200)
        with allure.step("Verify the new name in the web UI"):
            users_page.open()
            users_page.wait_for_users()
            assert users_page.has_user("Renamed Via API")

    @pytest.mark.regression
    def test_user_count_matches_between_api_and_ui(self, users_api, users_page):
        """The UI table row count matches the API list length."""
        api_count = len(users_api.list_users().assert_status(200).json)
        users_page.open()
        users_page.wait_for_users()
        assert users_page.user_count() == api_count
