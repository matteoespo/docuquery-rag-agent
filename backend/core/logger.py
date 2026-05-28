"""
Structured logging setup for the backend.

Replaces bare ``print()`` calls with leveled, timestamped log output
visible in Docker container logs.
"""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Return a named logger with a human-readable stream handler."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger