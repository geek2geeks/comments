"""
Logging Configuration for the Profile API.

This module provides a centralized and configurable logging system for the
application. It supports structured JSON logging for production environments and
color-coded, human-readable logs for development. It also includes support for
request correlation IDs to facilitate tracing and debugging.

Key Components:
- `CorrelationMiddleware`: A filter that injects a unique correlation ID into
  each log record, allowing all logs related to a single request to be easily
  grouped and traced.
- `JSONFormatter`: A custom log formatter that outputs log records as structured
  JSON. This is ideal for production environments where logs are ingested by
  log management systems (e.g., ELK stack, Splunk, Datadog).
- `ColoredConsoleFormatter`: A formatter that adds color to log levels, making
  logs easier to read in a development console.
- `get_logging_config`: A function that generates the logging configuration
  dictionary based on the environment (development vs. production).
- `setup_logging`: The main function that initializes the logging system for the
  entire application.
- `log_function_call`: A decorator to automatically log the entry, exit, and
  execution time of functions, reducing boilerplate logging code.

Architectural Design:
- Environment-Aware Configuration: The logging format and level are determined by
  environment variables, allowing for easy configuration without code changes.
- Structured vs. Unstructured Logging: The system can switch between structured
  (JSON) and unstructured (colored text) logging, providing the best format for
  both machine and human consumption.
- Context-Aware Logging: The use of `contextvars` for the correlation ID ensures
  that the ID is correctly associated with the asynchronous context of each
  request, even in a highly concurrent environment.
- Centralized Setup: All logging configuration is centralized in this module,
  making it easy to manage and modify the application's logging behavior.
"""

import os
import json
import logging
import logging.config
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar

# Context variable for request correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


class CorrelationFilter(logging.Filter):
    """Filter that adds correlation ID to log records"""

    def filter(self, record: logging.LogRecord) -> bool:
        corr_id = correlation_id.get()
        if corr_id:
            record.correlation_id = corr_id
        return True


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation ID if available
        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id

        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "exc_info",
                "exc_text",
                "stack_info",
                "correlation_id",
            }:
                log_entry[key] = value

        return json.dumps(log_entry)


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console formatter for development"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # Add correlation ID if available
        corr_id = getattr(record, "correlation_id", None)
        corr_part = f" [{corr_id}]" if corr_id else ""

        formatted = f"{color}[{timestamp}] {record.levelname:8} {record.name}{corr_part}: {record.getMessage()}{reset}"

        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        return formatted


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs"""

    def format(self, record: logging.LogRecord) -> str:
        # Base log structure
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation ID if available
        corr_id = correlation_id.get()
        if corr_id:
            log_entry["correlation_id"] = corr_id

        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields from the log record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "exc_info",
                "exc_text",
                "stack_info",
            }:
                extra_fields[key] = value

        if extra_fields:
            log_entry["extra"] = extra_fields

        return json.dumps(log_entry, default=str)


def get_logging_config() -> Dict[str, Any]:
    """Get logging configuration based on environment"""

    environment = os.getenv("ENVIRONMENT", "development").lower()
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Base configuration
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "()": StructuredFormatter,
            },
            "colored_console": {
                "()": ColoredConsoleFormatter,
            },
            "simple": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "colored_console"
                if environment == "development"
                else "structured",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            # Application loggers
            "api": {"level": log_level, "handlers": ["console"], "propagate": False},
            "services": {
                "level": log_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "core": {"level": log_level, "handlers": ["console"], "propagate": False},
            # Third-party loggers
            "uvicorn": {"level": "INFO", "handlers": ["console"], "propagate": False},
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "fastapi": {"level": "INFO", "handlers": ["console"], "propagate": False},
        },
        "root": {"level": log_level, "handlers": ["console"]},
    }

    # Add file logging for production
    if environment == "production":
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": log_level,
            "formatter": "structured",
            "filename": "/var/log/profile_api/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
        }

        # Add file handler to all loggers
        for logger_config in config["loggers"].values():
            logger_config["handlers"].append("file")
        config["root"]["handlers"].append("file")

    return config


def setup_logging():
    """Initialize logging configuration"""
    config = get_logging_config()
    logging.config.dictConfig(config)

    # Log startup message
    logger = logging.getLogger("core.logging")
    environment = os.getenv("ENVIRONMENT", "development")
    logger.info(f"Logging initialized for {environment} environment")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name"""
    return logging.getLogger(name)


def set_correlation_id(corr_id: str):
    """Set correlation ID for the current context"""
    correlation_id.set(corr_id)


def get_correlation_id() -> Optional[str]:
    """Get correlation ID from the current context"""
    return correlation_id.get()


def log_function_call(logger: logging.Logger):
    """Decorator to log function calls with parameters and execution time"""

    def decorator(func):
        import functools
        import time

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            logger.debug(
                f"Calling {func.__name__}",
                extra={
                    "function": func.__name__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()),
                },
            )

            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.debug(
                    f"Completed {func.__name__}",
                    extra={
                        "function": func.__name__,
                        "execution_time_ms": round(execution_time * 1000, 2),
                        "success": True,
                    },
                )
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(
                    f"Failed {func.__name__}: {str(e)}",
                    extra={
                        "function": func.__name__,
                        "execution_time_ms": round(execution_time * 1000, 2),
                        "success": False,
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            logger.debug(
                f"Calling {func.__name__}",
                extra={
                    "function": func.__name__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()),
                },
            )

            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.debug(
                    f"Completed {func.__name__}",
                    extra={
                        "function": func.__name__,
                        "execution_time_ms": round(execution_time * 1000, 2),
                        "success": True,
                    },
                )
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(
                    f"Failed {func.__name__}: {str(e)}",
                    extra={
                        "function": func.__name__,
                        "execution_time_ms": round(execution_time * 1000, 2),
                        "success": False,
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
                raise

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
