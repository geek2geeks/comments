import pytest
import asyncio
import time
from unittest.mock import Mock, patch
from core.performance import (
    MetricsCollector,
    async_timer,
    sync_timer,
    timed,
    async_timed,
    counted,
    async_counted,
    optimize_json_serialization,
    batch_operation
)


class TestMetricsCollector:
    """Test MetricsCollector functionality."""

    @pytest.fixture
    def metrics_collector(self):
        """Create a metrics collector for testing."""
        return MetricsCollector()

    def test_increment_counter(self, metrics_collector):
        """Test incrementing counters."""
        metrics_collector.increment_counter("test_counter")
        metrics_collector.increment_counter("test_counter", 5)
        
        metrics = metrics_collector.get_metrics()
        assert metrics["counters"]["test_counter"] == 6

    def test_record_timing(self, metrics_collector):
        """Test recording timing metrics."""
        metrics_collector.record_timing("test_operation", 1.5)
        metrics_collector.record_timing("test_operation", 2.5)
        
        metrics = metrics_collector.get_metrics()
        timings = metrics["timings"]["test_operation"]
        
        assert len(timings) == 2
        assert 1.5 in timings
        assert 2.5 in timings

    def test_record_gauge(self, metrics_collector):
        """Test recording gauge metrics."""
        metrics_collector.record_gauge("cpu_usage", 75.5)
        metrics_collector.record_gauge("memory_usage", 60.2)
        
        metrics = metrics_collector.get_metrics()
        assert metrics["gauges"]["cpu_usage"] == 75.5
        assert metrics["gauges"]["memory_usage"] == 60.2

    def test_get_timing_stats(self, metrics_collector):
        """Test getting timing statistics."""
        # Record multiple timings
        timings = [1.0, 2.0, 3.0, 4.0, 5.0]
        for timing in timings:
            metrics_collector.record_timing("test_op", timing)
        
        stats = metrics_collector.get_timing_stats("test_op")
        
        assert stats["count"] == 5
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["avg"] == 3.0
        assert stats["total"] == 15.0

    def test_get_timing_stats_nonexistent(self, metrics_collector):
        """Test getting stats for non-existent timing."""
        stats = metrics_collector.get_timing_stats("nonexistent")
        
        assert stats["count"] == 0
        assert stats["min"] == 0
        assert stats["max"] == 0
        assert stats["avg"] == 0
        assert stats["total"] == 0

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_collect_system_metrics(self, mock_disk, mock_memory, mock_cpu, metrics_collector):
        """Test collecting system metrics."""
        # Mock system metrics
        mock_cpu.return_value = 75.5
        mock_memory.return_value = Mock(percent=60.2, available=1024*1024*1024)
        mock_disk.return_value = Mock(percent=45.8, free=2048*1024*1024)
        
        metrics_collector.collect_system_metrics()
        metrics = metrics_collector.get_metrics()
        
        assert metrics["gauges"]["cpu_percent"] == 75.5
        assert metrics["gauges"]["memory_percent"] == 60.2
        assert metrics["gauges"]["disk_percent"] == 45.8
        assert metrics["gauges"]["memory_available_gb"] == 1.0
        assert metrics["gauges"]["disk_free_gb"] == 2.0

    def test_reset_metrics(self, metrics_collector):
        """Test resetting all metrics."""
        metrics_collector.increment_counter("test_counter")
        metrics_collector.record_timing("test_timing", 1.5)
        metrics_collector.record_gauge("test_gauge", 100)
        
        metrics_collector.reset_metrics()
        metrics = metrics_collector.get_metrics()
        
        assert len(metrics["counters"]) == 0
        assert len(metrics["timings"]) == 0
        assert len(metrics["gauges"]) == 0


class TestTimingContextManagers:
    """Test timing context managers."""

    @pytest.fixture
    def metrics_collector(self):
        """Create a metrics collector for testing."""
        return MetricsCollector()

    @pytest.mark.asyncio
    async def test_async_timer(self, metrics_collector):
        """Test async_timer context manager."""
        async with async_timer(metrics_collector, "test_operation"):
            await asyncio.sleep(0.1)
        
        metrics = metrics_collector.get_metrics()
        timings = metrics["timings"]["test_operation"]
        
        assert len(timings) == 1
        assert timings[0] >= 0.1  # Should be at least 0.1 seconds

    def test_sync_timer(self, metrics_collector):
        """Test sync_timer context manager."""
        with sync_timer(metrics_collector, "test_operation"):
            time.sleep(0.1)
        
        metrics = metrics_collector.get_metrics()
        timings = metrics["timings"]["test_operation"]
        
        assert len(timings) == 1
        assert timings[0] >= 0.1  # Should be at least 0.1 seconds


class TestDecorators:
    """Test performance decorators."""

    @pytest.fixture
    def metrics_collector(self):
        """Create a metrics collector for testing."""
        return MetricsCollector()

    def test_timed_decorator(self, metrics_collector):
        """Test timed decorator for sync functions."""
        @timed(metrics_collector, "test_function")
        def test_function():
            time.sleep(0.05)
            return "result"
        
        result = test_function()
        
        assert result == "result"
        metrics = metrics_collector.get_metrics()
        timings = metrics["timings"]["test_function"]
        assert len(timings) == 1
        assert timings[0] >= 0.05

    @pytest.mark.asyncio
    async def test_async_timed_decorator(self, metrics_collector):
        """Test async_timed decorator for async functions."""
        @async_timed(metrics_collector, "test_async_function")
        async def test_async_function():
            await asyncio.sleep(0.05)
            return "async_result"
        
        result = await test_async_function()
        
        assert result == "async_result"
        metrics = metrics_collector.get_metrics()
        timings = metrics["timings"]["test_async_function"]
        assert len(timings) == 1
        assert timings[0] >= 0.05

    def test_counted_decorator(self, metrics_collector):
        """Test counted decorator for sync functions."""
        @counted(metrics_collector, "test_function_calls")
        def test_function():
            return "result"
        
        test_function()
        test_function()
        test_function()
        
        metrics = metrics_collector.get_metrics()
        assert metrics["counters"]["test_function_calls"] == 3

    @pytest.mark.asyncio
    async def test_async_counted_decorator(self, metrics_collector):
        """Test async_counted decorator for async functions."""
        @async_counted(metrics_collector, "test_async_function_calls")
        async def test_async_function():
            return "async_result"
        
        await test_async_function()
        await test_async_function()
        
        metrics = metrics_collector.get_metrics()
        assert metrics["counters"]["test_async_function_calls"] == 2

    def test_combined_decorators(self, metrics_collector):
        """Test combining multiple decorators."""
        @counted(metrics_collector, "combined_function_calls")
        @timed(metrics_collector, "combined_function_timing")
        def combined_function(x, y):
            time.sleep(0.01)
            return x + y
        
        result1 = combined_function(1, 2)
        result2 = combined_function(3, 4)
        
        assert result1 == 3
        assert result2 == 7
        
        metrics = metrics_collector.get_metrics()
        assert metrics["counters"]["combined_function_calls"] == 2
        assert len(metrics["timings"]["combined_function_timing"]) == 2


class TestOptimizationUtilities:
    """Test optimization utility functions."""

    def test_optimize_json_serialization(self):
        """Test JSON serialization optimization."""
        data = {
            "string": "test",
            "number": 123,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "object": {"nested": "value"}
        }
        
        # Test that it returns a JSON string
        result = optimize_json_serialization(data)
        assert isinstance(result, str)
        
        # Test that it can be parsed back
        import json
        parsed = json.loads(result)
        assert parsed == data

    def test_optimize_json_serialization_with_custom_encoder(self):
        """Test JSON serialization with custom encoder."""
        from datetime import datetime
        
        class CustomEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return super().default(obj)
        
        data = {
            "timestamp": datetime(2024, 1, 1, 12, 0, 0),
            "value": 123
        }
        
        result = optimize_json_serialization(data, cls=CustomEncoder)
        assert "2024-01-01T12:00:00" in result

    @pytest.mark.asyncio
    async def test_batch_operation(self):
        """Test batch operation utility."""
        async def process_item(item):
            await asyncio.sleep(0.01)  # Simulate async work
            return item * 2
        
        items = [1, 2, 3, 4, 5]
        results = await batch_operation(items, process_item, batch_size=2)
        
        assert results == [2, 4, 6, 8, 10]

    @pytest.mark.asyncio
    async def test_batch_operation_with_exception(self):
        """Test batch operation handling exceptions."""
        async def process_item(item):
            if item == 3:
                raise ValueError(f"Error processing {item}")
            return item * 2
        
        items = [1, 2, 3, 4, 5]
        
        with pytest.raises(ValueError, match="Error processing 3"):
            await batch_operation(items, process_item, batch_size=2)

    @pytest.mark.asyncio
    async def test_batch_operation_empty_list(self):
        """Test batch operation with empty list."""
        async def process_item(item):
            return item * 2
        
        results = await batch_operation([], process_item)
        assert results == []

    @pytest.mark.asyncio
    async def test_batch_operation_single_item(self):
        """Test batch operation with single item."""
        async def process_item(item):
            return item * 2
        
        results = await batch_operation([5], process_item)
        assert results == [10]