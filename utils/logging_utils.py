"""Structured logging for the framework.

Log records include timestamp, level, test id (when bound), category and
message. Secrets are masked automatically by the attached filter.
"""

from __future__ import annotations

import contextvars
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from utils.masking import mask_sensitive_data

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"

_current_test: contextvars.ContextVar[str] = contextvars.ContextVar("fw_test", default="")
_current_category: contextvars.ContextVar[str] = contextvars.ContextVar("fw_category", default="")


def bind_test_context(test_id: str = "", category: str = "") -> None:
    """Bind the current test id/category to subsequent log records."""
    _current_test.set(test_id or "")
    _current_category.set(category or "")


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.test_id = _current_test.get()
        record.category = _current_category.get()
        return True


class _MaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_sensitive_data(record.msg)
        if record.args:
            try:
                if isinstance(record.args, dict):
                    record.args = mask_sensitive_data(record.args)  # type: ignore[assignment]
                else:
                    record.args = tuple(
                        mask_sensitive_data(a) if isinstance(a, str) else a
                        for a in record.args
                    )
            except Exception:
                pass
        return True


_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    numeric = getattr(logging, str(level).upper(), logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(category)-6s | %(test_id)-60s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger("fw")
    root.setLevel(numeric)
    root.propagate = False
    # NOTE: filters live on the HANDLERS (not only the loggers) on purpose:
    # records from child loggers (e.g. logging.getLogger("fw.x")) reach these
    # handlers via propagation without passing the parent logger's filters.
    # Handler-level filters guarantee every formatted record has the
    # test/category attributes, so formatting can never crash.
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric)
    console.setFormatter(fmt)
    console.addFilter(_ContextFilter())
    console.addFilter(_MaskingFilter())
    root.addHandler(console)
    file_handler = RotatingFileHandler(
        LOG_DIR / "framework.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(numeric)
    file_handler.setFormatter(fmt)
    file_handler.addFilter(_ContextFilter())
    file_handler.addFilter(_MaskingFilter())
    root.addHandler(file_handler)


def get_logger(name: str = "fw") -> logging.Logger:
    configure_logging()
    logger = logging.getLogger("fw" if name in {"fw", "__main__"} else f"fw.{name}")
    logger.addFilter(_ContextFilter())
    logger.addFilter(_MaskingFilter())
    return logger
