# src/utils/logger.py

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
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

    # Create logs directory if it doesn't exist
    if settings.environment != "development":
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        log_file = logs_dir / "app.log"
        
        # Create file handler with rotation
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers = [logging.StreamHandler(sys.stdout), file_handler]
    else:
        handlers = [logging.StreamHandler(sys.stdout)]

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True  # Overwrite existing configuration
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured for '{settings.environment}' environment at level '{settings.log_level}'.")
    if settings.environment != "development":
        logger.info(f"Log file location: {log_file.absolute()}")

def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger instance for the given name.

    Args:
        name: The name for the logger.

    Returns:
        A logging.Logger instance.
    """
    return logging.getLogger(name)
