import logging

import structlog

from assistant.shared.config import settings


def configure_logging() -> None:
    """Configure structlog for the application.

    Uses ConsoleRenderer in DEBUG mode for readability during development,
    JSONRenderer otherwise for structured log ingestion in production.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            (
                structlog.dev.ConsoleRenderer()
                if settings.log_level == "DEBUG"
                else structlog.processors.JSONRenderer()
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
