"""End-to-end example: complete user workflow across API + UI.

Workflow:
    1. API setup  -- create a user + a post via the REST API.
    2. UI workflow -- log in, browse the Users page, submit the practice form.
    3. API verify -- the created entities exist in the backend.
    4. UI verify  -- the created user is visible in the Users table.
    5. Cleanup    -- delete created entities, verify removal via API + UI.
"""

import allure
import pytest

from utils.data_utils import random_post_payload, random_user_payload

pytestmark = [pytest.mark.e2e, allure.epic("End-to-End"),
              allure.feature("User workflow")]


@allure.story("Complete user lifecycle")
class TestUserWorkflow:
    @pytest.mark.smoke
    @allure.severity(allure.severity_level.CRITICAL)
    def test_full_user_lifecycle(self, users_api, posts_api, login_page,
                                 users_page, forms_page, fw_settings):
        user_payload = random_user_payload()
        created_user_id = None
        created_post_id = None
        try:
            with allure.step("1. API setup: create user"):
                created = users_api.create_user(user_payload).assert_status(201).json
                created_user_id = created["id"]
            with allure.step("2. API setup: create post for the user"):
                post = posts_api.create_post(
                    random_post_payload(user_id=created_user_id)).assert_status(201).json
                created_post_id = post["id"]
            with allure.step("3. UI workflow: log in"):
                login_page.open()
                login_page.login(fw_settings.username, fw_settings.password)
                assert fw_settings.username in login_page.greeting()
            with allure.step("4. UI verify: user visible in Users table"):
                users_page.open()
                users_page.wait_for_users()
                assert users_page.has_user(created["name"])
            with allure.step("5. UI workflow: submit the practice form"):
                forms_page.open()
                forms_page.submit_form(
                    name=created["name"], email=created["email"], role="user")
                assert created["name"] in forms_page.success_message()
            with allure.step("6. API verify: entities exist in backend"):
                assert users_api.get_user(created_user_id).assert_status(200).json["email"] == \
                    user_payload["email"]
                assert posts_api.get_post(created_post_id).assert_status(200).json["userId"] == \
                    created_user_id
        finally:
            with allure.step("7. Cleanup: delete created entities"):
                if created_post_id:
                    posts_api.delete_post(created_post_id)
                if created_user_id:
                    users_api.delete_user(created_user_id)
            with allure.step("8. Verify cleanup via API"):
                if created_user_id:
                    users_api.get_user(created_user_id).assert_status(404)

    @pytest.mark.regression
    def test_user_search_workflow(self, users_api, users_page):
        """E2E search flow: API creates uniquely-named user, UI search finds it."""
        payload = random_user_payload(name="Zed Searchable")
        created = users_api.create_user(payload).assert_status(201).json
        try:
            users_page.open()
            users_page.wait_for_users()
            users_page.search("Zed Searchable")
            assert users_page.has_user("Zed Searchable")
            users_page.search("no-such-user-xyz")
            assert users_page.user_count() == 0
        finally:
            users_api.delete_user(created["id"])
