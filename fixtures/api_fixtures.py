"""API fixtures: settings-driven reusable API clients."""

from __future__ import annotations

import pytest

from api.auth_client import AuthClient
from api.posts_api import PostsApi
from api.users_api import UsersApi


@pytest.fixture(scope="session")
def users_api(effective_api_base_url: str, fw_settings) -> UsersApi:
    client = UsersApi(effective_api_base_url, timeout=fw_settings.api_timeout)
    yield client
    client.close()


@pytest.fixture(scope="session")
def posts_api(effective_api_base_url: str, fw_settings) -> PostsApi:
    client = PostsApi(effective_api_base_url, timeout=fw_settings.api_timeout)
    yield client
    client.close()


@pytest.fixture(scope="session")
def auth_api(effective_api_base_url: str, fw_settings) -> AuthClient:
    client = AuthClient(effective_api_base_url, timeout=fw_settings.api_timeout)
    yield client
    client.close()


@pytest.fixture(scope="function")
def authenticated_api(auth_api: AuthClient, fw_settings) -> AuthClient:
    """Auth client with a fresh bearer token for the configured user."""
    auth_api.login_and_get_token(fw_settings.username, fw_settings.password)
    return auth_api
