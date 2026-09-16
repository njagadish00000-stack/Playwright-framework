"""Test-data helpers: JSON/CSV loading, .env access and data generation."""

from __future__ import annotations

import csv
import json
import os
import random
import string
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_DATA_DIR = PROJECT_ROOT / "test_data"


def load_json(name: str) -> object:
    """Load ``test_data/json/<name>`` (adds ``.json`` if missing)."""
    filename = name if name.endswith(".json") else f"{name}.json"
    path = TEST_DATA_DIR / "json" / filename
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_csv(name: str) -> list[dict[str, str]]:
    """Load ``test_data/csv/<name>`` as a list of row dicts."""
    filename = name if name.endswith(".csv") else f"{name}.csv"
    path = TEST_DATA_DIR / "csv" / filename
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def unique_suffix() -> str:
    """A short unique suffix for generated entity names."""
    return f"{int(time.time() * 1000) % 1_000_000:06d}{random.randint(10, 99)}"


def random_string(length: int = 8, alphabet: str = string.ascii_lowercase) -> str:
    return "".join(random.choice(alphabet) for _ in range(length))


def random_email(prefix: str = "user") -> str:
    return f"{prefix}_{unique_suffix()}@example.com"


def random_user_payload(**overrides) -> dict:
    payload = {
        "name": f"Test User {unique_suffix()}",
        "username": f"tuser_{unique_suffix()}",
        "email": random_email(),
        "role": "user",
    }
    payload.update(overrides)
    return payload


def random_post_payload(user_id: int = 1, **overrides) -> dict:
    payload = {
        "userId": user_id,
        "title": f"Post {unique_suffix()}",
        "body": f"Body {random_string(24)}",
    }
    payload.update(overrides)
    return payload


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)
