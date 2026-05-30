"""Configuration structlog (sortie console lisible)."""

from __future__ import annotations

import logging

import structlog

_CONFIGURED = False


def configure(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True
