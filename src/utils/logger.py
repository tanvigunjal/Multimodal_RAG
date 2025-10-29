# src/utils/logger.py

import logging
import sys
from src.config import get_settings

def configure_logging() -> None:
    """
    Configures the root logger for the application.

    This function sets the logging level, format, and handler based on the
    application's configuration settings. It should be called once at the
    start of the application.
    """
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Use a more detailed format for development
    if settings.environment == "development":
        log_format = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "[%(pathname)s:%(lineno)d] - %(message)s"
        )
    else:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True  # Overwrite existing configuration
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured for '{settings.environment}' environment at level '{settings.log_level}'.")

def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger instance for the given name.

    Args:
        name: The name for the logger.

    Returns:
        A logging.Logger instance.
    """
    return logging.getLogger(name)
