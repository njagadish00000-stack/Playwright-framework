"""ZIP packaging: complete framework + framework-without-example-tests.

Both archives are real, validated, and preserve the project structure. They
never include virtualenvs, caches, generated reports, credentials or browser
binaries.
"""

from __future__ import annotations

import fnmatch
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"

EXCLUDE_DIRS = {
    ".venv", "venv", ".git", "__pycache__", ".pytest_cache", ".cache",
    "node_modules", ".idea", ".vscode", "dist",
    "reports", "logs", ".hypothesis",
}
EXCLUDE_FILES = {
    ".env", ".env.local", "*.pem", "*.key", "*.pyc", "*.pyo",
    ".DS_Store", "Thumbs.db",
}
# Example tests excluded from the "without example tests" package.
EXAMPLE_TEST_DIRS = {"api_tests", "ui_tests", "api_ui_tests", "e2e_tests"}
# Files that MUST exist inside a valid package.
REQUIRED_FILES = [
    "README.md", "requirements.txt", "pytest.ini", "conftest.py",
    "VERSION", ".env.example", ".gitignore",
    "dashboard/index.html", "server/app.py",
]


def _excluded(relative: Path, *, without_examples: bool) -> bool:
    parts = set(relative.parts)
    if parts & EXCLUDE_DIRS:
        return True
    name = relative.name
    for pattern in EXCLUDE_FILES:
        if fnmatch.fnmatch(name, pattern):
            return True
    if without_examples and relative.parts and relative.parts[0] in EXAMPLE_TEST_DIRS:
        # Keep the directory + __init__.py so users know where tests go.
        if len(relative.parts) == 1 or name != "__init__.py":
            return len(relative.parts) != 1
        return False
    return False


def _iter_files(without_examples: bool) -> list[Path]:
    files: list[Path] = []
    for path in sorted(PROJECT_ROOT.rglob("*")):
        if path.is_dir() or path.is_symlink():
            continue
        relative = path.relative_to(PROJECT_ROOT)
        if _excluded(relative, without_examples=without_examples):
            continue
        files.append(path)
    return files


def validate_package(path: Path, *, without_examples: bool) -> dict:
    """Validate a built ZIP. Raises ValueError on any problem."""
    issues: list[str] = []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        for required in REQUIRED_FILES:
            if required not in names:
                issues.append(f"missing required file: {required}")
        for name in names:
            lowered = name.lower()
            if "/.venv/" in f"/{lowered}" or lowered.startswith(".venv/"):
                issues.append(f"contains virtualenv file: {name}")
            if "__pycache__" in lowered or ".pytest_cache" in lowered:
                issues.append(f"contains cache file: {name}")
            if lowered.endswith("/.env") or lowered == ".env":
                issues.append("contains .env secrets file")
            if "allure-results" in lowered or "execution-history" in lowered:
                issues.append(f"contains generated report: {name}")
            if "ms-playwright" in lowered or "browser binaries" in lowered:
                issues.append(f"contains browser binary: {name}")
        test_files = [n for n in names
                      if n.split("/")[0] in EXAMPLE_TEST_DIRS and n.endswith(".py")
                      and not n.endswith("__init__.py")]
        if without_examples and test_files:
            issues.append(f"should exclude example tests, found: {test_files[:3]}")
        if not without_examples and not test_files:
            issues.append("complete package contains no example tests")
    if issues:
        raise ValueError("; ".join(issues))
    return {"file": str(path), "entries": len(names),
            "size_bytes": path.stat().st_size, "valid": True}


def build_package(*, without_examples: bool = False) -> dict:
    """Build one ZIP package and validate it. Returns info dict."""
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    from config.settings import framework_version

    version = framework_version()
    filename = (f"playwright-framework-{version}-no-examples.zip"
                if without_examples else
                f"playwright-framework-{version}-complete.zip")
    target = DIST_DIR / filename
    if target.exists():
        target.unlink()
    files = _iter_files(without_examples=without_examples)
    # For the no-examples package, ensure empty test dirs exist in the ZIP.
    extra_dirs: list[str] = []
    if without_examples:
        for dirname in sorted(EXAMPLE_TEST_DIRS):
            init = PROJECT_ROOT / dirname / "__init__.py"
            if init.exists() and init not in files:
                files.append(init)
            extra_dirs.append(f"{dirname}/")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for extra in extra_dirs:
            archive.writestr(extra, "")
        for path in files:
            archive.write(path, path.relative_to(PROJECT_ROOT))
    info = validate_package(target, without_examples=without_examples)
    info["filename"] = filename
    return info
