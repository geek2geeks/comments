import pytest
import logging
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from io import StringIO

from core.logging_config import (
    setup_logging,
    get_logger,
    log_function_call,
    CorrelationFilter,
    JSONFormatter,
    ColoredConsoleFormatter
)


class TestLoggingSetup:
    """Test logging configuration setup."""

    def test_setup_logging_development(self):
        """Test logging setup for development environment."""
        with patch.dict('os.environ', {'ENVIRONMENT': 'development'}):
            setup_logging()
            
            logger = logging.getLogger('profile_api')
            assert logger.level == logging.DEBUG
            
            # Should have console handler
            handlers = logger.handlers
            assert len(handlers) > 0
            
            # Check for colored formatter in development
            console_handler = next((h for h in handlers if isinstance(h, logging.StreamHandler)), None)
            assert console_handler is not None
            assert isinstance(console_handler.formatter, ColoredConsoleFormatter)

    def test_setup_logging_production(self):
        """Test logging setup for production environment."""
        with patch.dict('os.environ', {'ENVIRONMENT': 'production'}):
            setup_logging()
            
            logger = logging.getLogger('profile_api')
            assert logger.level == logging.INFO
            
            # Should have JSON formatter in production
            handlers = logger.handlers
            console_handler = next((h for h in handlers if isinstance(h, logging.StreamHandler)), None)
            assert console_handler is not None
            assert isinstance(console_handler.formatter, JSONFormatter)

    def test_get_logger(self):
        """Test getting a logger instance."""
        logger = get_logger('test_module')
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'profile_api.test_module'

    def test_get_logger_with_correlation_filter(self):
        """Test that logger has correlation filter."""
        logger = get_logger('test_module')
        
        # Check if correlation filter is present
        filters = logger.filters
        correlation_filter = next((f for f in filters if isinstance(f, CorrelationFilter)), None)
        assert correlation_filter is not None


class TestCorrelationFilter:
    """Test CorrelationFilter functionality."""

    def test_correlation_filter_adds_correlation_id(self):
        """Test that correlation filter adds correlation ID to log records."""
        correlation_filter = CorrelationFilter()
        
        # Mock contextvars to return a correlation ID
        with patch('core.logging_config.correlation_id_var') as mock_var:
            mock_var.get.return_value = 'test-correlation-123'
            
            record = logging.LogRecord(
                name='test',
                level=logging.INFO,
                pathname='',
                lineno=0,
                msg='Test message',
                args=(),
                exc_info=None
            )
            
            result = correlation_filter.filter(record)
            
            assert result is True
            assert hasattr(record, 'correlation_id')
            assert record.correlation_id == 'test-correlation-123'

    def test_correlation_filter_no_correlation_id(self):
        """Test correlation filter when no correlation ID is set."""
        correlation_filter = CorrelationFilter()
        
        # Mock contextvars to raise LookupError (no correlation ID set)
        with patch('core.logging_config.correlation_id_var') as mock_var:
            mock_var.get.side_effect = LookupError()
            
            record = logging.LogRecord(
                name='test',
                level=logging.INFO,
                pathname='',
                lineno=0,
                msg='Test message',
                args=(),
                exc_info=None
            )
            
            result = correlation_filter.filter(record)
            
            assert result is True
            assert hasattr(record, 'correlation_id')
            assert record.correlation_id is None


class TestJSONFormatter:
    """Test JSONFormatter functionality."""

    def test_json_formatter_basic_formatting(self):
        """Test basic JSON formatting of log records."""
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='/path/to/file.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.correlation_id = 'test-correlation-123'
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data['timestamp']
        assert log_data['level'] == 'INFO'
        assert log_data['logger'] == 'test_logger'
        assert log_data['message'] == 'Test message'
        assert log_data['correlation_id'] == 'test-correlation-123'
        assert log_data['module'] == 'file'
        assert log_data['line'] == 42

    def test_json_formatter_with_extra_fields(self):
        """Test JSON formatter with extra fields."""
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.ERROR,
            pathname='/path/to/file.py',
            lineno=42,
            msg='Error occurred',
            args=(),
            exc_info=None
        )
        record.correlation_id = None
        record.user_id = 'user123'
        record.request_id = 'req456'
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data['level'] == 'ERROR'
        assert log_data['message'] == 'Error occurred'
        assert log_data['correlation_id'] is None
        assert log_data['user_id'] == 'user123'
        assert log_data['request_id'] == 'req456'

    def test_json_formatter_with_exception(self):
        """Test JSON formatter with exception information."""
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = True
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.ERROR,
            pathname='/path/to/file.py',
            lineno=42,
            msg='Exception occurred',
            args=(),
            exc_info=exc_info
        )
        record.correlation_id = 'test-correlation-123'
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data['level'] == 'ERROR'
        assert log_data['message'] == 'Exception occurred'
        assert 'exception' in log_data
        assert 'ValueError: Test exception' in log_data['exception']


class TestColoredConsoleFormatter:
    """Test ColoredConsoleFormatter functionality."""

    def test_colored_formatter_basic_formatting(self):
        """Test basic colored formatting of log records."""
        formatter = ColoredConsoleFormatter()
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='/path/to/file.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.correlation_id = 'test-correlation-123'
        
        formatted = formatter.format(record)
        
        # Should contain the basic information
        assert 'INFO' in formatted
        assert 'test_logger' in formatted
        assert 'Test message' in formatted
        assert 'test-correlation-123' in formatted

    def test_colored_formatter_different_levels(self):
        """Test colored formatter with different log levels."""
        formatter = ColoredConsoleFormatter()
        
        levels = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]
        
        for level in levels:
            record = logging.LogRecord(
                name='test_logger',
                level=level,
                pathname='/path/to/file.py',
                lineno=42,
                msg=f'Test {logging.getLevelName(level)} message',
                args=(),
                exc_info=None
            )
            record.correlation_id = 'test-correlation-123'
            
            formatted = formatter.format(record)
            
            # Should contain the level name
            assert logging.getLevelName(level) in formatted
            assert f'Test {logging.getLevelName(level)} message' in formatted


class TestLogFunctionCallDecorator:
    """Test log_function_call decorator functionality."""

    def test_sync_function_logging(self):
        """Test logging of synchronous function calls."""
        # Capture log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(JSONFormatter())
        
        logger = get_logger('test_decorator')
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        @log_function_call
        def test_function(x, y, z=None):
            return x + y
        
        result = test_function(1, 2, z='test')
        
        assert result == 3
        
        # Check log output
        log_output = log_capture.getvalue()
        assert 'test_function' in log_output
        assert 'Function call started' in log_output or 'Function call completed' in log_output

    @pytest.mark.asyncio
    async def test_async_function_logging(self):
        """Test logging of asynchronous function calls."""
        # Capture log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(JSONFormatter())
        
        logger = get_logger('test_decorator')
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        @log_function_call
        async def async_test_function(x, y):
            await asyncio.sleep(0.01)  # Small delay
            return x * y
        
        result = await async_test_function(3, 4)
        
        assert result == 12
        
        # Check log output
        log_output = log_capture.getvalue()
        assert 'async_test_function' in log_output

    def test_function_with_exception_logging(self):
        """Test logging when decorated function raises an exception."""
        # Capture log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(JSONFormatter())
        
        logger = get_logger('test_decorator')
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        @log_function_call
        def failing_function():
            raise ValueError("Test exception")
        
        with pytest.raises(ValueError):
            failing_function()
        
        # Check log output
        log_output = log_capture.getvalue()
        assert 'failing_function' in log_output
        assert 'ERROR' in log_output or 'Exception' in log_output

    @pytest.mark.asyncio
    async def test_async_function_with_exception_logging(self):
        """Test logging when decorated async function raises an exception."""
        # Capture log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(JSONFormatter())
        
        logger = get_logger('test_decorator')
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        @log_function_call
        async def async_failing_function():
            await asyncio.sleep(0.01)
            raise RuntimeError("Async test exception")
        
        with pytest.raises(RuntimeError):
            await async_failing_function()
        
        # Check log output
        log_output = log_capture.getvalue()
        assert 'async_failing_function' in log_output
        assert 'ERROR' in log_output or 'Exception' in log_output

    def test_function_execution_time_logging(self):
        """Test that execution time is logged."""
        # Capture log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(JSONFormatter())
        
        logger = get_logger('test_decorator')
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        @log_function_call
        def timed_function():
            import time
            time.sleep(0.1)  # Sleep for 100ms
            return "done"
        
        result = timed_function()
        
        assert result == "done"
        
        # Check log output for execution time
        log_output = log_capture.getvalue()
        assert 'execution_time' in log_output or 'duration' in log_output


class TestLoggingIntegration:
    """Test logging integration with other components."""

    def test_logger_with_correlation_context(self):
        """Test logger behavior with correlation context."""
        logger = get_logger('integration_test')
        
        # Mock correlation context
        with patch('core.logging_config.correlation_id_var') as mock_var:
            mock_var.get.return_value = 'integration-test-123'
            
            # Capture log output
            log_capture = StringIO()
            handler = logging.StreamHandler(log_capture)
            handler.setFormatter(JSONFormatter())
            
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
            logger.info("Integration test message", extra={"user_id": "user123"})
            
            log_output = log_capture.getvalue()
            log_data = json.loads(log_output.strip())
            
            assert log_data['message'] == 'Integration test message'
            assert log_data['correlation_id'] == 'integration-test-123'
            assert log_data['user_id'] == 'user123'

    def test_multiple_loggers_independence(self):
        """Test that multiple loggers work independently."""
        logger1 = get_logger('module1')
        logger2 = get_logger('module2')
        
        assert logger1.name == 'profile_api.module1'
        assert logger2.name == 'profile_api.module2'
        assert logger1 != logger2

    def test_logging_performance(self):
        """Test logging performance with high volume."""
        logger = get_logger('performance_test')
        
        # Capture to null handler to avoid I/O overhead
        null_handler = logging.NullHandler()
        logger.addHandler(null_handler)
        logger.setLevel(logging.INFO)
        
        import time
        start_time = time.time()
        
        # Log 1000 messages
        for i in range(1000):
            logger.info(f"Performance test message {i}", extra={"iteration": i})
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete within reasonable time (adjust threshold as needed)
        assert duration < 1.0  # Less than 1 second for 1000 log messages