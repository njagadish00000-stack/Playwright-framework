"""Page Object Model layer for UI automation."""

from pages.base_page import BasePage
from pages.home_page import HomePage
from pages.forms_page import FormsPage
from pages.login_page import LoginPage
from pages.users_page import UsersPage

__all__ = ["BasePage", "HomePage", "FormsPage", "LoginPage", "UsersPage"]
