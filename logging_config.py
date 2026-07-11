"""Minimal, dependency-free logging setup for observability.

Self-hosters get visibility into paid API calls (model, token usage, failures)
without any new dependency — just the stdlib ``logging`` module. Entry points
(the Streamlit app, the CLI) call :func:`configure_logging` once at startup;
library modules log through ``logging.getLogger("app_ly.<area>")``.

Never log resume content, job listings, or contact PII — only counts, the
model id, and control-flow context.
"""

from __future__ import annotations

import logging
import os

# All application loggers live under this namespace so configuration can target
# them without fighting Streamlit's own root-logger setup.
LOGGER_NAME = "app_ly"

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging() -> logging.Logger:
    """Configure the ``app_ly`` logger from the ``LOG_LEVEL`` env var (default
    ``INFO``) and return it. Idempotent — safe to call on every Streamlit rerun.
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
    # Own our output rather than duplicating through the root logger's handlers.
    logger.propagate = False
    return logger
