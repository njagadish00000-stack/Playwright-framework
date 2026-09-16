"""Posts resource API client."""

from __future__ import annotations

from typing import Any

from api.base_api_client import ApiResponse, BaseApiClient

POST_SCHEMA = {
    "type": "object",
    "required": ["id", "userId", "title", "body"],
    "properties": {
        "id": {"type": "integer"},
        "userId": {"type": "integer"},
        "title": {"type": "string"},
        "body": {"type": "string"},
    },
}


class PostsApi(BaseApiClient):
    """CRUD client for the ``/posts`` resource."""

    def list_posts(self, **params) -> ApiResponse:
        return self.get("/posts", params=params or None)

    def get_post(self, post_id: int) -> ApiResponse:
        return self.get("/posts/{id}", path_params={"id": post_id})

    def create_post(self, payload: dict[str, Any]) -> ApiResponse:
        return self.post("/posts", json=payload)

    def update_post(self, post_id: int, payload: dict[str, Any]) -> ApiResponse:
        return self.put("/posts/{id}", path_params={"id": post_id}, json=payload)

    def patch_post(self, post_id: int, payload: dict[str, Any]) -> ApiResponse:
        return self.patch("/posts/{id}", path_params={"id": post_id}, json=payload)

    def delete_post(self, post_id: int) -> ApiResponse:
        return self.delete("/posts/{id}", path_params={"id": post_id})
