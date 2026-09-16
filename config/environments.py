"""Environment profiles for the framework.

Each profile defines the default URLs for a named environment. Explicit
settings (CLI flags, ``.env`` values, OS environment variables) always win
over these profile defaults -- see :mod:`config.settings`.

To add a new environment, add one entry to :data:`ENVIRONMENTS` -- nothing
else needs to change. The dashboard discovers the list dynamically.
"""

from __future__ import annotations

ENVIRONMENTS: dict[str, dict[str, str]] = {
    "local": {
        "base_url": "http://127.0.0.1:8765",
        "api_base_url": "http://127.0.0.1:8765/api",
        "description": "Local bundled demo application (default, works offline).",
    },
    "dev": {
        "base_url": "http://127.0.0.1:8765",
        "api_base_url": "http://127.0.0.1:8765/api",
        "description": "Development environment (override with real URLs via .env).",
    },
    "qa": {
        "base_url": "http://127.0.0.1:8765",
        "api_base_url": "http://127.0.0.1:8765/api",
        "description": "QA environment (override with real URLs via .env).",
    },
    "staging": {
        "base_url": "http://127.0.0.1:8765",
        "api_base_url": "http://127.0.0.1:8765/api",
        "description": "Staging environment (override with real URLs via .env).",
    },
    "prodlike": {
        "base_url": "http://127.0.0.1:8765",
        "api_base_url": "http://127.0.0.1:8765/api",
        "description": "Production-like environment (override with real URLs via .env).",
    },
}

DEFAULT_ENVIRONMENT = "local"


def get_environment_config(name: str) -> dict[str, str]:
    """Return the config dict for an environment name (case-insensitive).

    Raises:
        ValueError: If the environment name is unknown.
    """
    key = (name or "").strip().lower()
    if key not in ENVIRONMENTS:
        valid = ", ".join(sorted(ENVIRONMENTS))
        raise ValueError(f"Unknown environment '{name}'. Valid environments: {valid}")
    return dict(ENVIRONMENTS[key])


def list_environments() -> list[str]:
    """Return the sorted list of known environment names."""
    return sorted(ENVIRONMENTS)
