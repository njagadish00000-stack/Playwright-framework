"""Base HTTP client used by every API client in the framework.

Features:
    * GET / POST / PUT / PATCH / DELETE / HEAD / OPTIONS
    * query params, path params, headers, cookies, JSON / form / multipart bodies
    * bearer, basic and custom-header authentication
    * request/response logging with sensitive-data masking
    * Allure request/response attachments
    * timeouts, retries with backoff, response-time measurement
    * status / header / JSON / schema validation helpers
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import requests

from utils.logging_utils import get_logger
from utils.masking import mask_sensitive_data

logger = get_logger(__name__)


@dataclass
class ApiResponse:
    """Thin wrapper around ``requests.Response`` with validation helpers."""

    status_code: int
    headers: dict
    body: Any
    raw_text: str
    elapsed: float
    url: str
    method: str
    request_body: Any = None
    request_headers: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def json(self) -> Any:
        return self.body

    def assert_status(self, *expected: int) -> "ApiResponse":
        if self.status_code not in expected:
            raise AssertionError(
                f"Expected status {expected}, got {self.status_code} "
                f"for {self.method} {self.url}. Body: {self.raw_text[:500]}"
            )
        return self

    def assert_response_time_under(self, seconds: float) -> "ApiResponse":
        if self.elapsed > seconds:
            raise AssertionError(
                f"Response took {self.elapsed:.3f}s, expected under {seconds}s "
                f"for {self.method} {self.url}"
            )
        return self

    def assert_header(self, name: str, expected: str) -> "ApiResponse":
        actual = self.headers.get(name, self.headers.get(name.lower(), ""))
        if actual != expected:
            raise AssertionError(
                f"Expected header {name}={expected!r}, got {actual!r}"
            )
        return self

    def assert_json_path(self, path: str, expected: Any) -> "ApiResponse":
        """Assert a dotted JSON path (supports ``a.b.0.c``) equals *expected*."""
        actual = self.json_path(path)
        if actual != expected:
            raise AssertionError(
                f"Expected JSON path '{path}'={expected!r}, got {actual!r}"
            )
        return self

    def json_path(self, path: str, default: Any = None) -> Any:
        current: Any = self.body
        for part in path.split("."):
            if isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return default
            elif isinstance(current, dict):
                if part not in current:
                    return default
                current = current[part]
            else:
                return default
        return current

    def assert_schema(self, schema: dict) -> "ApiResponse":
        try:
            import jsonschema
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("jsonschema is required for schema validation") from exc
        jsonschema.validate(instance=self.body, schema=schema)
        return self


class BaseApiClient:
    """Reusable base client. Subclasses declare resources (see users_api.py)."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: int = 15,
        default_headers: dict | None = None,
        auth: tuple[str, str] | None = None,
        bearer_token: str | None = None,
        verify_tls: bool = True,
        max_retries: int = 0,
        retry_backoff: float = 0.5,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.session = requests.Session()
        self.session.headers.update(
            {"Accept": "application/json", **(default_headers or {})}
        )
        if auth:
            self.session.auth = auth
        if bearer_token:
            self.session.headers["Authorization"] = f"Bearer {bearer_token}"

    # -- auth helpers ------------------------------------------------------
    def set_bearer_token(self, token: str) -> None:
        self.session.headers["Authorization"] = f"Bearer {token}"

    def set_basic_auth(self, username: str, password: str) -> None:
        self.session.auth = (username, password)

    def set_header(self, name: str, value: str) -> None:
        self.session.headers[name] = value

    # -- core request ------------------------------------------------------
    def request(
        self,
        method: str,
        path: str,
        *,
        path_params: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        cookies: dict | None = None,
        json: Any = None,
        data: Any = None,
        files: dict | None = None,
        timeout: int | None = None,
    ) -> ApiResponse:
        if path_params:
            path = path.format(**path_params)
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        merged_headers = dict(self.session.headers)
        if headers:
            merged_headers.update(headers)
        attempt = 0
        last_error: Exception | None = None
        while attempt <= self.max_retries:
            start = time.perf_counter()
            try:
                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    headers=headers,
                    cookies=cookies,
                    json=json,
                    data=data,
                    files=files,
                    timeout=timeout or self.timeout,
                    verify=self.verify_tls,
                )
                elapsed = time.perf_counter() - start
                api_response = self._wrap(
                    response, elapsed, method.upper(), url, json if json is not None else data,
                    merged_headers,
                )
                self._log_and_attach(api_response, params)
                return api_response
            except requests.RequestException as exc:
                last_error = exc
                attempt += 1
                if attempt > self.max_retries:
                    break
                time.sleep(self.retry_backoff * attempt)
        raise RuntimeError(f"Request {method} {url} failed after retries: {last_error}")

    def _wrap(
        self, response: requests.Response, elapsed: float, method: str,
        url: str, request_body: Any, request_headers: dict,
    ) -> ApiResponse:
        try:
            body = response.json()
        except ValueError:
            body = None
        return ApiResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=body,
            raw_text=response.text or "",
            elapsed=round(elapsed, 4),
            url=url,
            method=method,
            request_body=request_body,
            request_headers=request_headers,
        )

    def _log_and_attach(self, resp: ApiResponse, params: dict | None) -> None:
        safe_headers = mask_sensitive_data(resp.request_headers)
        safe_body = mask_sensitive_data(resp.request_body)
        logger.info("%s %s -> %s (%.3fs)", resp.method, resp.url, resp.status_code, resp.elapsed)
        logger.debug("Request headers=%s params=%s body=%s", safe_headers, params, safe_body)
        logger.debug("Response body: %s", (resp.raw_text or "")[:2000])
        try:
            import allure

            request_text = (
                f"{resp.method} {resp.url}\nparams={params}\n"
                f"headers={safe_headers}\nbody={safe_body}"
            )
            allure.attach(
                request_text, name=f"Request: {resp.method} {resp.url}",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                f"Status: {resp.status_code}\nTime: {resp.elapsed}s\n\n{resp.raw_text[:8000]}",
                name=f"Response: {resp.status_code} ({resp.elapsed}s)",
                attachment_type=allure.attachment_type.TEXT,
            )
            if resp.body is not None:
                import json as _json

                allure.attach(
                    _json.dumps(mask_sensitive_data(resp.body), indent=2, default=str)[:8000],
                    name="Response JSON",
                    attachment_type=allure.attachment_type.JSON,
                )
        except Exception as exc:  # Allure must never break API execution
            logger.debug("Allure attach skipped: %s", exc)

    # -- convenience verbs ---------------------------------------------------
    def get(self, path: str, **kwargs) -> ApiResponse:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> ApiResponse:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> ApiResponse:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs) -> ApiResponse:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs) -> ApiResponse:
        return self.request("DELETE", path, **kwargs)

    def head(self, path: str, **kwargs) -> ApiResponse:
        return self.request("HEAD", path, **kwargs)

    def options(self, path: str, **kwargs) -> ApiResponse:
        return self.request("OPTIONS", path, **kwargs)

    def close(self) -> None:
        self.session.close()
