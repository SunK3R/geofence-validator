# -*- coding: utf-8 -*-
"""
logger.py - Internal Logging Configuration for the Library.

This module is designed with a "graceful upgrade" philosophy.

By default, it uses the standard library's `logging` module and a `NullHandler`
to ensure the library is silent unless configured by the end-user. This adheres
to best practices for library development.

However, it also includes an `enable_debugging` helper function that checks for
the presence of the optional `rich` library. If `rich` is installed, it uses
`rich.logging.RichHandler` to provide beautiful, colorized, and highly readable
log output. If `rich` is not found, it gracefully falls back to the standard
`logging.StreamHandler`, ensuring full functionality in all environments.

This provides an enhanced developer experience for those who opt-in, without
imposing any dependencies on those who don't.
"""
from __future__ import annotations

import logging
import sys

# Define the single, top-level logger name for the entire library.
LIBRARY_LOGGER_NAME: str = "geofence_validator"


def setup_library_logging() -> None:
    """
    Configure the library's top-level logger with a NullHandler.

    This ensures that if the user of the library has not configured logging,
    no messages from our library will be propagated or printed.
    """
    library_logger = logging.getLogger(LIBRARY_LOGGER_NAME)

    # Check if there's already a NullHandler in the library_logger's handlers
    has_null_handler = any(
        isinstance(handler, logging.NullHandler)
        for handler in library_logger.handlers
    )
    if not has_null_handler:
        library_logger.addHandler(logging.NullHandler())
    library_logger.propagate = False
    library_logger.debug(
        "Attached NullHandler to logger '%s' to prevent log output.",
        LIBRARY_LOGGER_NAME,
    )


def enable_debugging(level: int = logging.DEBUG) -> None:
    """
    Enable verbose console logging for debugging the library's behavior.

    This developer-facing utility automatically detects if `rich` is installed
    and uses it for superior log formatting if available. Otherwise, it falls
    back to a standard `StreamHandler`.

    To get rich logging, install the library with the `rich` extra:
    `pip install "geofence-validator[rich]"`

    Args:
        level: The logging level to set (e.g., logging.INFO, logging.DEBUG).
    """
    library_logger = logging.getLogger(LIBRARY_LOGGER_NAME)
    
    # Clear any existing handlers (like the default NullHandler).
    if library_logger.hasHandlers():
        for handler in library_logger.handlers[:]:
            library_logger.removeHandler(handler)
            
    library_logger.setLevel(level)
    library_logger.propagate = False
    
    handler: logging.Handler

    try:
        # Attempt to import rich and use its handler for beautiful output.
        from rich.logging import RichHandler

        handler = RichHandler(
            rich_tracebacks=True,
            show_time=False,
            show_level=True,
            show_path=True,
            markup=True,
        )
        library_logger.addHandler(handler)
        library_logger.info(
            "Rich logging enabled for '[bold cyan]%s[/bold cyan]' at level [bold yellow]%s[/bold yellow].",
            LIBRARY_LOGGER_NAME,
            logging.getLevelName(level),
            extra={"markup": True},
        )
        return

    except ImportError:
        # Gracefully fall back to the standard StreamHandler if rich is not installed.
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - L%(lineno)d - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        library_logger.addHandler(handler)
        library_logger.info(
            "Standard logging enabled for '%s' at level %s. "
            "For rich output, run 'pip install rich'.",
            LIBRARY_LOGGER_NAME,
            logging.getLevelName(level),
        )