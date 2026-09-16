"""Users resource API client."""

from __future__ import annotations

from typing import Any

from api.base_api_client import ApiResponse, BaseApiClient

USER_SCHEMA = {
    "type": "object",
    "required": ["id", "name", "username", "email"],
    "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string"},
        "username": {"type": "string"},
        "email": {"type": "string"},
        "role": {"type": "string"},
    },
}

USER_LIST_SCHEMA = {"type": "array", "items": USER_SCHEMA}


class UsersApi(BaseApiClient):
    """CRUD client for the ``/users`` resource."""

    def list_users(self, **params) -> ApiResponse:
        return self.get("/users", params=params or None)

    def get_user(self, user_id: int) -> ApiResponse:
        return self.get("/users/{id}", path_params={"id": user_id})

    def create_user(self, payload: dict[str, Any]) -> ApiResponse:
        return self.post("/users", json=payload)

    def update_user(self, user_id: int, payload: dict[str, Any]) -> ApiResponse:
        return self.put("/users/{id}", path_params={"id": user_id}, json=payload)

    def patch_user(self, user_id: int, payload: dict[str, Any]) -> ApiResponse:
        return self.patch("/users/{id}", path_params={"id": user_id}, json=payload)

    def delete_user(self, user_id: int) -> ApiResponse:
        return self.delete("/users/{id}", path_params={"id": user_id})

    def head_users(self) -> ApiResponse:
        return self.head("/users")

    def options_users(self) -> ApiResponse:
        return self.options("/users")
