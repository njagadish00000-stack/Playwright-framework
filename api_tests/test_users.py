"""API example tests for the /users resource (GET/POST/PUT/PATCH/DELETE)."""

import allure
import pytest

from api.users_api import USER_LIST_SCHEMA, USER_SCHEMA
from utils.data_utils import load_csv, load_json, random_user_payload, unique_suffix

pytestmark = [pytest.mark.api, allure.epic("API"), allure.feature("Users API")]


@allure.story("List and retrieve users")
class TestGetUsers:
    @pytest.mark.smoke
    @allure.severity(allure.severity_level.CRITICAL)
    def test_list_users(self, users_api):
        """GET /users returns the seeded list and matches the schema."""
        with allure.step("List all users"):
            response = users_api.list_users().assert_status(200)
            response.assert_response_time_under(5)
        with allure.step("Validate payload schema and content"):
            response.assert_schema(USER_LIST_SCHEMA)
            assert len(response.json) >= 10
            assert response.json[0]["username"] == "alice"

    @pytest.mark.smoke
    def test_get_single_user(self, users_api):
        """GET /users/{id} returns one user."""
        user = users_api.get_user(1).assert_status(200).assert_schema(USER_SCHEMA).json
        assert user["id"] == 1
        assert user["email"] == "alice@example.com"

    @pytest.mark.regression
    def test_filter_users_by_role(self, users_api):
        """Query-parameter filtering: only admins are returned."""
        users = users_api.list_users(role="admin").assert_status(200).json
        assert users, "expected at least one admin user"
        assert all(u["role"] == "admin" for u in users)

    @pytest.mark.regression
    def test_list_users_with_limit(self, users_api):
        users = users_api.list_users(_limit=3).assert_status(200).json
        assert len(users) == 3


@allure.story("Create, update and delete users")
class TestModifyUsers:
    @pytest.mark.smoke
    @allure.severity(allure.severity_level.CRITICAL)
    def test_create_user(self, users_api):
        """POST /users creates a user that can be fetched afterwards."""
        payload = random_user_payload()
        with allure.step(f"Create user {payload['username']}"):
            created = users_api.create_user(payload).assert_status(201).json
        assert created["id"] > 0
        assert created["username"] == payload["username"]
        with allure.step("Verify the user exists via GET"):
            fetched = users_api.get_user(created["id"]).assert_status(200).json
            assert fetched["email"] == payload["email"]

    @pytest.mark.regression
    def test_update_user_put(self, users_api):
        created = users_api.create_user(random_user_payload()).assert_status(201).json
        updated = users_api.update_user(
            created["id"],
            {"name": "Replaced Name", "username": created["username"],
             "email": created["email"], "role": "admin"},
        ).assert_status(200).json
        assert updated["name"] == "Replaced Name"
        assert updated["role"] == "admin"

    @pytest.mark.regression
    def test_patch_user(self, users_api):
        created = users_api.create_user(random_user_payload()).assert_status(201).json
        patched = users_api.patch_user(created["id"], {"role": "editor"}).assert_status(200).json
        assert patched["role"] == "editor"
        assert patched["name"] == created["name"]

    @pytest.mark.regression
    def test_delete_user(self, users_api):
        created = users_api.create_user(random_user_payload()).assert_status(201).json
        users_api.delete_user(created["id"]).assert_status(204)
        users_api.get_user(created["id"]).assert_status(404)


@allure.story("Negative and edge-case validation")
class TestUsersNegative:
    @pytest.mark.regression
    def test_get_missing_user_returns_404(self, users_api):
        users_api.get_user(999999).assert_status(404)

    @pytest.mark.regression
    def test_create_user_missing_fields_returns_400(self, users_api):
        users_api.create_user({"name": "No Username"}).assert_status(400)

    @pytest.mark.regression
    def test_create_duplicate_username_returns_409(self, users_api):
        payload = random_user_payload(username=f"dup_{unique_suffix()}")
        users_api.create_user(payload).assert_status(201)
        users_api.create_user(payload).assert_status(409)

    @pytest.mark.regression
    def test_delete_missing_user_returns_404(self, users_api):
        users_api.delete_user(999999).assert_status(404)

    @pytest.mark.regression
    @pytest.mark.parametrize("method,expected", [("head", 200), ("options", 200)])
    def test_head_and_options(self, users_api, method, expected):
        response = users_api.head_users() if method == "head" else users_api.options_users()
        response.assert_status(expected)


@allure.story("Data-driven user creation")
class TestUsersDataDriven:
    @pytest.mark.regression
    def test_create_users_from_json_data(self, users_api):
        """Create users defined in test_data/json/users.json (uniquified)."""
        for row in load_json("users.json"):
            payload = dict(row)
            payload["username"] = f"{row['username']}_{unique_suffix()}"
            payload["email"] = f"{unique_suffix()}_{row['email']}"
            created = users_api.create_user(payload).assert_status(201).json
            assert created["username"] == payload["username"]

    @pytest.mark.regression
    def test_create_users_from_csv_data(self, users_api):
        """Create users defined in test_data/csv/users.csv (uniquified)."""
        for row in load_csv("users.csv"):
            payload = dict(row)
            payload["username"] = f"{row['username']}_{unique_suffix()}"
            payload["email"] = f"{unique_suffix()}_{row['email']}"
            users_api.create_user(payload).assert_status(201)
