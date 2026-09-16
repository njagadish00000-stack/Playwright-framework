"""Users page object: renders the user list fetched from the REST API."""

from __future__ import annotations

from pages.base_page import BasePage


class UsersPage(BasePage):
    url_path = "/users"

    TABLE_ROWS = "[data-testid='user-row']"
    TABLE = "[data-testid='users-table']"
    REFRESH_BUTTON = "[data-testid='btn-refresh-users']"
    SEARCH_INPUT = "[data-testid='input-user-search']"
    EMPTY_STATE = "[data-testid='users-empty']"

    def wait_for_users(self, timeout: int | None = None) -> None:
        self.page.wait_for_selector(self.TABLE_ROWS, timeout=timeout)

    def user_names(self) -> list[str]:
        return [t.strip() for t in self.locate(f"{self.TABLE_ROWS} td:nth-child(2)").all_inner_texts()]

    def user_count(self) -> int:
        return self.count(self.TABLE_ROWS)

    def search(self, query: str) -> None:
        self.fill(self.SEARCH_INPUT, query)

    def refresh(self) -> None:
        self.click(self.REFRESH_BUTTON)
        self.wait_for_users()

    def has_user(self, name: str, timeout: int | None = 10000) -> bool:
        try:
            self.page.wait_for_selector(
                f"{self.TABLE_ROWS}:has-text('{name}')", timeout=timeout
            )
            return True
        except Exception:
            return False
