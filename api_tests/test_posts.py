"""API example tests for the /posts resource."""

import allure
import pytest

from api.posts_api import POST_SCHEMA
from utils.data_utils import random_post_payload

pytestmark = [pytest.mark.api, allure.epic("API"), allure.feature("Posts API")]


@allure.story("List and retrieve posts")
class TestGetPosts:
    @pytest.mark.smoke
    def test_list_posts(self, posts_api):
        posts = posts_api.list_posts().assert_status(200).assert_response_time_under(5).json
        assert len(posts) >= 10
        assert posts[0]["title"] == "Demo post 1"

    @pytest.mark.smoke
    def test_get_single_post(self, posts_api):
        post = posts_api.get_post(1).assert_status(200).assert_schema(POST_SCHEMA).json
        assert post["id"] == 1
        assert post["userId"] == 1

    @pytest.mark.regression
    def test_filter_posts_by_user(self, posts_api):
        posts = posts_api.list_posts(userId=2).assert_status(200).json
        assert posts
        assert all(p["userId"] == 2 for p in posts)

    @pytest.mark.regression
    def test_get_missing_post_returns_404(self, posts_api):
        posts_api.get_post(999999).assert_status(404)


@allure.story("Create, update and delete posts")
class TestModifyPosts:
    @pytest.mark.smoke
    def test_create_post(self, posts_api):
        payload = random_post_payload(user_id=3)
        created = posts_api.create_post(payload).assert_status(201).json
        assert created["title"] == payload["title"]
        fetched = posts_api.get_post(created["id"]).assert_status(200).json
        assert fetched["body"] == payload["body"]

    @pytest.mark.regression
    def test_update_post_put(self, posts_api):
        created = posts_api.create_post(random_post_payload()).assert_status(201).json
        updated = posts_api.update_post(
            created["id"], {"userId": 5, "title": "Replaced", "body": "Replaced body"}
        ).assert_status(200).json
        assert updated["title"] == "Replaced"
        assert updated["userId"] == 5

    @pytest.mark.regression
    def test_patch_post(self, posts_api):
        created = posts_api.create_post(random_post_payload()).assert_status(201).json
        patched = posts_api.patch_post(created["id"], {"title": "Patched"}).assert_status(200).json
        assert patched["title"] == "Patched"

    @pytest.mark.regression
    def test_delete_post(self, posts_api):
        created = posts_api.create_post(random_post_payload()).assert_status(201).json
        posts_api.delete_post(created["id"]).assert_status(204)
        posts_api.get_post(created["id"]).assert_status(404)

    @pytest.mark.regression
    def test_create_post_missing_fields_returns_400(self, posts_api):
        posts_api.create_post({"title": "no body/user"}).assert_status(400)
