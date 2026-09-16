"""API example tests: auth flows, headers, uploads, error handling."""

import allure
import pytest

pytestmark = [pytest.mark.api, allure.epic("API"), allure.feature("Auth & errors")]


@allure.story("Authentication")
class TestAuth:
    @pytest.mark.smoke
    @allure.severity(allure.severity_level.CRITICAL)
    def test_login_and_profile_with_bearer_token(self, auth_api, fw_settings):
        """Login returns a bearer token that grants access to /profile."""
        with allure.step("Log in with demo credentials"):
            token = auth_api.login_and_get_token(fw_settings.username, fw_settings.password)
            assert token
        with allure.step("Call the protected profile endpoint"):
            profile = auth_api.profile().assert_status(200).json
            assert profile["username"] == fw_settings.username

    @pytest.mark.regression
    def test_login_with_bad_password_returns_401(self, auth_api):
        auth_api.login("demo", "wrong-password").assert_status(401)

    @pytest.mark.regression
    def test_profile_without_token_returns_401(self, auth_api):
        # Fresh client without the Authorization header.
        from api.auth_client import AuthClient

        anonymous = AuthClient(auth_api.base_url, timeout=auth_api.timeout)
        try:
            anonymous.profile().assert_status(401)
        finally:
            anonymous.close()

    @pytest.mark.regression
    def test_basic_auth(self, auth_api):
        response = auth_api.basic_auth_check("demo", "demo123").assert_status(200)
        assert response.json["authenticated"] is True


@allure.story("Headers, echo and uploads")
class TestHeadersAndUploads:
    @pytest.mark.regression
    def test_custom_header_roundtrip(self, auth_api):
        auth_api.set_header("X-Custom-Header", "framework-check")
        try:
            echoed = auth_api.echo_headers().assert_status(200).json
            assert echoed.get("X-Custom-Header") == "framework-check"
        finally:
            auth_api.session.headers.pop("X-Custom-Header", None)

    @pytest.mark.regression
    def test_form_data_and_query_params(self, auth_api):
        response = auth_api.session.post(
            f"{auth_api.base_url}/echo?a=1", data={"field": "value"}, timeout=auth_api.timeout
        )
        assert response.status_code == 200
        body = response.json()
        assert body["form"] == {"field": "value"}
        assert body["args"] == {"a": "1"}

    @pytest.mark.regression
    def test_multipart_file_upload(self, auth_api, tmp_path):
        sample = tmp_path / "upload.txt"
        sample.write_text("hello upload", encoding="utf-8")
        with open(sample, "rb") as fh:
            response = auth_api.request("POST", "/upload", files={"file": ("upload.txt", fh)})
        response.assert_status(201)
        assert response.json["filename"] == "upload.txt"
        assert response.json["size"] == len("hello upload")

    @pytest.mark.regression
    def test_cookie_handling(self, users_api):
        # Cookies must not break requests; server simply ignores them.
        users_api.get("/users", params={"_limit": 1},
                      cookies={"sessionid": "abc123"}).assert_status(200)


@allure.story("Response time and errors")
class TestTimingAndErrors:
    @pytest.mark.regression
    def test_response_time_validation(self, users_api):
        users_api.list_users().assert_status(200).assert_response_time_under(5)

    @pytest.mark.regression
    def test_unknown_route_returns_404(self, users_api):
        users_api.get("/does-not-exist").assert_status(404)
