"""Structured logging configuration with credential sanitization."""

import logging
import logging.handlers
import re
from pathlib import Path

# Patterns to sanitize from log messages
SENSITIVE_PATTERNS = [
    (re.compile(r"(apikey[:=]\s*)([a-zA-Z0-9_\-\.]+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(api[-_]?key[:=]\s*['\"]?)([\w\-]+)(['\"]?)", re.IGNORECASE), r"\1[REDACTED]\3"),
    (re.compile(r"(Bearer\s+)([\w\-\.]+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(key=)([a-zA-Z0-9_\-\.%]+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(expires=)(\d+)", re.IGNORECASE), r"\1[TIMESTAMP]"),
]


class SanitizingFormatter(logging.Formatter):
    """Logging formatter that automatically masks secrets and API keys."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        return sanitize_sensitive_data(msg)


def sanitize_sensitive_data(text: str) -> str:
    """Mask any API keys, tokens, or credentials in a string."""
    sanitized = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def setup_logging(
    log_dir: str | Path = "data/logs",
    log_level: int = logging.INFO,
    console_output: bool = True,
) -> None:
    """Configure logging to multiple destination files and console."""
    dir_path = Path(log_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    formatter = SanitizingFormatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    # 1. Main app log
    app_handler = logging.handlers.RotatingFileHandler(
        dir_path / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    app_handler.setFormatter(formatter)
    app_handler.setLevel(log_level)
    root_logger.addHandler(app_handler)

    # 2. Error log (WARNING and ERROR only)
    error_handler = logging.handlers.RotatingFileHandler(
        dir_path / "error.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.WARNING)
    root_logger.addHandler(error_handler)

    # 3. Dedicated download log
    dl_logger = logging.getLogger("nexus.downloads")
    dl_handler = logging.handlers.RotatingFileHandler(
        dir_path / "download.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    dl_handler.setFormatter(formatter)
    dl_logger.addHandler(dl_handler)

    # 4. Dedicated install log
    inst_logger = logging.getLogger("nexus.installer")
    inst_handler = logging.handlers.RotatingFileHandler(
        dir_path / "install.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    inst_handler.setFormatter(formatter)
    inst_logger.addHandler(inst_handler)

    # 5. Optional console output
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.WARNING)  # keep console quiet by default for rich UI
        root_logger.addHandler(console_handler)


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a named logger with proper hierarchy."""
    return logging.getLogger(name or "nexus_autoinstaller")
