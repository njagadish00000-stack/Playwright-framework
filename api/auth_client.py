"""Authentication API client (login, tokens, protected resources)."""

from __future__ import annotations

from typing import Any

from api.base_api_client import ApiResponse, BaseApiClient


class AuthClient(BaseApiClient):
    """Client for auth endpoints: login, refresh, profile, basic-auth."""

    def login(self, username: str, password: str) -> ApiResponse:
        return self.post("/login", json={"username": username, "password": password})

    def login_and_get_token(self, username: str, password: str) -> str:
        response = self.login(username, password).assert_status(200)
        token = response.json_path("token")
        if not token:
            raise AssertionError(f"Login response has no token: {response.raw_text[:300]}")
        self.set_bearer_token(token)
        return token

    def profile(self) -> ApiResponse:
        return self.get("/profile")

    def basic_auth_check(self, username: str, password: str) -> ApiResponse:
        """Call the basic-auth protected endpoint with one-off credentials."""
        import requests

        response = requests.get(
            f"{self.base_url}/basic-auth",
            auth=(username, password),
            timeout=self.timeout,
        )
        return self._wrap(
            response, response.elapsed.total_seconds(), "GET",
            f"{self.base_url}/basic-auth", None, {},
        )

    def echo_headers(self) -> ApiResponse:
        return self.get("/echo-headers")

    def echo(self, payload: dict[str, Any]) -> ApiResponse:
        return self.post("/echo", json=payload)
