"""
Performance Monitoring and Metrics Collection.

This module provides a comprehensive system for monitoring the performance of the
Profile API. It includes tools for collecting, aggregating, and exposing various
performance metrics, including request timings, system resource usage, and custom
application-specific metrics.

Key Components:
- `MetricsCollector`: The central class for collecting and managing metrics. It
  stores metrics in-memory and can provide aggregated statistics over a specified
  time window. It handles different types of metrics, including counters, gauges,
  and histograms.
- `PerformanceMetric` & `RequestMetrics`: Dataclasses that define the structure
  for individual performance metrics and request-level metrics, ensuring
  consistency in data collection.
- `PerformanceTimer` & `async_timer`: Context managers (both synchronous and
  asynchronous) for easily timing specific blocks of code.
- `@timed` & `@counted`: Decorators that provide a convenient way to apply timing
  and counting metrics to functions without cluttering the business logic.
- System Metrics Collection: The `MetricsCollector` automatically collects system-
  level metrics (CPU, memory, disk usage) in a background task.

Architectural Design:
- In-Memory Aggregation: For simplicity, this implementation aggregates metrics
  in memory. In a production environment, this could be extended to export
  metrics to a dedicated monitoring system like Prometheus or Datadog.
- Singleton Pattern (via `get_metrics_collector`): A single, global instance of
  the `MetricsCollector` is used throughout the application to ensure that all
  metrics are collected in a central repository.
- Asynchronous and Thread-Safe: The collector is designed to be used in an
  asynchronous FastAPI application and uses locks to ensure that metric collection
  is thread-safe.
- Extensibility: The system is designed to be easily extensible. New types of
  metrics can be added, and the `MetricsCollector` can be adapted to use
  different storage backends.
"""

import time
import asyncio
import psutil
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import asynccontextmanager, contextmanager
import functools
import threading

from core.logging_config import get_logger

logger = get_logger("core.performance")


@dataclass
class PerformanceMetric:
    """Individual performance metric"""

    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = "ms"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags,
            "unit": self.unit,
        }


@dataclass
class RequestMetrics:
    """Request-level performance metrics"""

    endpoint: str
    method: str
    status_code: int
    duration_ms: float
    timestamp: datetime
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    request_size: Optional[int] = None
    response_size: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "method": self.method,
            "status_code": self.status_code,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
            "user_agent": self.user_agent,
            "ip_address": self.ip_address,
            "request_size": self.request_size,
            "response_size": self.response_size,
        }


class MetricsCollector:
    """Collects and aggregates performance metrics"""

    def __init__(self, max_metrics: int = 10000):
        self.max_metrics = max_metrics
        self.metrics: deque = deque(maxlen=max_metrics)
        self.request_metrics: deque = deque(maxlen=max_metrics)
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

        # Start system metrics collection
        self._system_metrics_task = None
        self._start_system_metrics_collection()

    def record_metric(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        unit: str = "ms",
    ):
        """Record a performance metric"""
        metric = PerformanceMetric(
            name=name,
            value=value,
            timestamp=datetime.utcnow(),
            tags=tags or {},
            unit=unit,
        )

        with self._lock:
            self.metrics.append(metric)

            # Update histogram
            self.histograms[name].append(value)
            # Keep histogram size manageable
            if len(self.histograms[name]) > 1000:
                self.histograms[name] = self.histograms[name][-1000:]

        logger.debug(
            f"Recorded metric: {name}={value}{unit}",
            extra={"metric_name": name, "value": value, "unit": unit, "tags": tags},
        )

    def record_request(self, metrics: RequestMetrics):
        """Record request-level metrics"""
        with self._lock:
            self.request_metrics.append(metrics)

            # Update counters
            self.counters["requests_total"] += 1
            self.counters[f"requests_{metrics.method.lower()}"] += 1
            self.counters[f"responses_{metrics.status_code}"] += 1

            # Update histograms
            self.histograms["request_duration"].append(metrics.duration_ms)
            if len(self.histograms["request_duration"]) > 1000:
                self.histograms["request_duration"] = self.histograms[
                    "request_duration"
                ][-1000:]

        logger.debug(
            f"Recorded request: {metrics.method} {metrics.endpoint} - {metrics.duration_ms}ms",
            extra={
                "endpoint": metrics.endpoint,
                "method": metrics.method,
                "duration_ms": metrics.duration_ms,
                "status_code": metrics.status_code,
            },
        )

    def increment_counter(
        self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ):
        """Increment a counter metric"""
        with self._lock:
            counter_key = name
            if tags:
                tag_str = ":".join(f"{k}={v}" for k, v in sorted(tags.items()))
                counter_key = f"{name}:{tag_str}"

            self.counters[counter_key] += value

        logger.debug(f"Incremented counter: {counter_key} += {value}")

    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Set a gauge metric"""
        with self._lock:
            gauge_key = name
            if tags:
                tag_str = ":".join(f"{k}={v}" for k, v in sorted(tags.items()))
                gauge_key = f"{name}:{tag_str}"

            self.gauges[gauge_key] = value

        logger.debug(f"Set gauge: {gauge_key} = {value}")

    def get_stats(self, time_window_minutes: int = 5) -> Dict[str, Any]:
        """Get aggregated statistics"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)

        with self._lock:
            # Filter recent metrics
            recent_requests = [
                req for req in self.request_metrics if req.timestamp >= cutoff_time
            ]

            recent_metrics = [
                metric for metric in self.metrics if metric.timestamp >= cutoff_time
            ]

            # Calculate request statistics
            request_stats = self._calculate_request_stats(recent_requests)

            # Calculate metric statistics
            metric_stats = self._calculate_metric_stats(recent_metrics)

            # System metrics
            system_stats = self._get_system_stats()

            return {
                "time_window_minutes": time_window_minutes,
                "timestamp": datetime.utcnow().isoformat(),
                "requests": request_stats,
                "metrics": metric_stats,
                "system": system_stats,
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
            }

    def _calculate_request_stats(
        self, requests: List[RequestMetrics]
    ) -> Dict[str, Any]:
        """Calculate request statistics"""
        if not requests:
            return {
                "total": 0,
                "avg_duration_ms": 0,
                "min_duration_ms": 0,
                "max_duration_ms": 0,
                "p95_duration_ms": 0,
                "p99_duration_ms": 0,
                "requests_per_second": 0,
                "status_codes": {},
                "endpoints": {},
            }

        durations = [req.duration_ms for req in requests]
        durations.sort()

        # Calculate percentiles
        p95_idx = int(len(durations) * 0.95)
        p99_idx = int(len(durations) * 0.99)

        # Count by status code
        status_codes = defaultdict(int)
        for req in requests:
            status_codes[str(req.status_code)] += 1

        # Count by endpoint
        endpoints = defaultdict(int)
        for req in requests:
            endpoints[f"{req.method} {req.endpoint}"] += 1

        # Calculate RPS
        if requests:
            time_span = (requests[-1].timestamp - requests[0].timestamp).total_seconds()
            rps = len(requests) / max(time_span, 1)
        else:
            rps = 0

        return {
            "total": len(requests),
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "p95_duration_ms": durations[p95_idx] if p95_idx < len(durations) else 0,
            "p99_duration_ms": durations[p99_idx] if p99_idx < len(durations) else 0,
            "requests_per_second": round(rps, 2),
            "status_codes": dict(status_codes),
            "endpoints": dict(endpoints),
        }

    def _calculate_metric_stats(
        self, metrics: List[PerformanceMetric]
    ) -> Dict[str, Any]:
        """Calculate metric statistics"""
        if not metrics:
            return {}

        # Group by metric name
        by_name = defaultdict(list)
        for metric in metrics:
            by_name[metric.name].append(metric.value)

        stats = {}
        for name, values in by_name.items():
            values.sort()
            p95_idx = int(len(values) * 0.95)
            p99_idx = int(len(values) * 0.99)

            stats[name] = {
                "count": len(values),
                "avg": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "p95": values[p95_idx] if p95_idx < len(values) else 0,
                "p99": values[p99_idx] if p99_idx < len(values) else 0,
            }

        return stats

    def _get_system_stats(self) -> Dict[str, Any]:
        """Get current system statistics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            cpu_count = psutil.cpu_count()

            # Memory usage
            memory = psutil.virtual_memory()

            # Disk usage
            disk = psutil.disk_usage("/")

            # Network I/O
            network = psutil.net_io_counters()

            return {
                "cpu": {"percent": cpu_percent, "count": cpu_count},
                "memory": {
                    "total_bytes": memory.total,
                    "available_bytes": memory.available,
                    "used_bytes": memory.used,
                    "percent": memory.percent,
                },
                "disk": {
                    "total_bytes": disk.total,
                    "free_bytes": disk.free,
                    "used_bytes": disk.used,
                    "percent": (disk.used / disk.total) * 100,
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv,
                },
            }
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}

    def _start_system_metrics_collection(self):
        """Start background system metrics collection"""

        async def collect_system_metrics():
            while True:
                try:
                    stats = self._get_system_stats()

                    # Record as gauges
                    if "cpu" in stats:
                        self.set_gauge("system_cpu_percent", stats["cpu"]["percent"])

                    if "memory" in stats:
                        self.set_gauge(
                            "system_memory_percent", stats["memory"]["percent"]
                        )
                        self.set_gauge(
                            "system_memory_used_bytes", stats["memory"]["used_bytes"]
                        )

                    if "disk" in stats:
                        self.set_gauge("system_disk_percent", stats["disk"]["percent"])

                    await asyncio.sleep(30)  # Collect every 30 seconds

                except Exception as e:
                    logger.error(f"Error in system metrics collection: {e}")
                    await asyncio.sleep(60)  # Wait longer on error

        # Start the background task
        try:
            loop = asyncio.get_event_loop()
            self._system_metrics_task = loop.create_task(collect_system_metrics())
        except RuntimeError:
            # No event loop running, will start later
            pass

    def cleanup(self):
        """Cleanup resources"""
        if self._system_metrics_task:
            self._system_metrics_task.cancel()


class PerformanceTimer:
    """Context manager for timing operations"""

    def __init__(
        self,
        name: str,
        collector: MetricsCollector,
        tags: Optional[Dict[str, str]] = None,
    ):
        self.name = name
        self.collector = collector
        self.tags = tags or {}
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        duration_ms = (self.end_time - self.start_time) * 1000

        # Add exception info to tags if there was an error
        tags = self.tags.copy()
        if exc_type:
            tags["error"] = exc_type.__name__

        self.collector.record_metric(self.name, duration_ms, tags)

    @property
    def duration_ms(self) -> Optional[float]:
        """Get duration in milliseconds"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None


@asynccontextmanager
async def async_timer(
    name: str, collector: MetricsCollector, tags: Optional[Dict[str, str]] = None
):
    """Async context manager for timing operations"""
    start_time = time.perf_counter()
    tags = tags or {}

    try:
        yield
    except Exception as e:
        tags["error"] = type(e).__name__
        raise
    finally:
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000
        collector.record_metric(name, duration_ms, tags)


@contextmanager
def sync_timer(
    name: str, collector: MetricsCollector, tags: Optional[Dict[str, str]] = None
):
    """Sync context manager for timing operations"""
    start_time = time.perf_counter()
    tags = tags or {}

    try:
        yield
    except Exception as e:
        tags["error"] = type(e).__name__
        raise
    finally:
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000
        collector.record_metric(name, duration_ms, tags)


# Global metrics collector
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
        logger.info("Metrics collector initialized")
    return _metrics_collector


def init_metrics_collector(max_metrics: int = 10000) -> MetricsCollector:
    """Initialize metrics collector with custom settings"""
    global _metrics_collector
    if _metrics_collector:
        _metrics_collector.cleanup()

    _metrics_collector = MetricsCollector(max_metrics=max_metrics)
    logger.info(f"Metrics collector initialized with max_metrics={max_metrics}")
    return _metrics_collector


# Performance decorators
def timed(name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
    """Decorator to time function execution"""

    def decorator(func):
        metric_name = name or f"{func.__module__}.{func.__name__}"

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                collector = get_metrics_collector()
                async with async_timer(metric_name, collector, tags):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                collector = get_metrics_collector()
                with PerformanceTimer(metric_name, collector, tags):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator


def counted(name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
    """Decorator to count function calls"""

    def decorator(func):
        counter_name = name or f"{func.__module__}.{func.__name__}_calls"

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            collector.increment_counter(counter_name, tags=tags)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def async_timed(name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
    """Decorator to time async function execution"""

    def decorator(func):
        metric_name = name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            async with async_timer(metric_name, collector, tags):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


def async_counted(name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
    """Decorator to count async function calls"""

    def decorator(func):
        counter_name = name or f"{func.__module__}.{func.__name__}_calls"

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            collector.increment_counter(counter_name, tags=tags)
            return await func(*args, **kwargs)

        return wrapper

    return decorator


class PerformanceOptimizer:
    """Performance optimization utilities"""

    @staticmethod
    def optimize_json_response(data: Any) -> str:
        """Optimize JSON serialization"""
        import orjson

        try:
            # Use orjson for faster serialization if available
            return orjson.dumps(data).decode()
        except ImportError:
            import json

            return json.dumps(data, separators=(",", ":"))

    @staticmethod
    async def batch_operations(
        operations: List[Callable], batch_size: int = 10
    ) -> List[Any]:
        """Execute operations in batches to avoid overwhelming the system"""
        results = []

        for i in range(0, len(operations), batch_size):
            batch = operations[i : i + batch_size]

            # Execute batch concurrently
            batch_results = await asyncio.gather(
                *[
                    op()
                    if asyncio.iscoroutinefunction(op)
                    else asyncio.create_task(asyncio.to_thread(op))
                    for op in batch
                ],
                return_exceptions=True,
            )

            results.extend(batch_results)

            # Small delay between batches to prevent overwhelming
            if i + batch_size < len(operations):
                await asyncio.sleep(0.01)

        return results

    @staticmethod
    def memory_efficient_generator(data_source, chunk_size: int = 1000):
        """Create memory-efficient generator for large datasets"""
        for i in range(0, len(data_source), chunk_size):
            yield data_source[i : i + chunk_size]

    @staticmethod
    async def with_timeout(coro, timeout_seconds: float = 30.0):
        """Execute coroutine with timeout"""
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(f"Operation timed out after {timeout_seconds} seconds")
            raise

    @staticmethod
    def compress_response(data: bytes, min_size: int = 1024) -> bytes:
        """Compress response data if it's large enough"""
        if len(data) < min_size:
            return data

        import gzip

        return gzip.compress(data)


# Note: Metrics collector functions are already defined earlier in the file


def optimize_json_serialization(data: Any, **kwargs) -> str:
    """Optimize JSON serialization for better performance"""
    import json

    # Use separators for more compact JSON
    return json.dumps(data, separators=(",", ":"), **kwargs)


async def batch_operation(
    items: List[Any], operation: Callable, batch_size: int = 10
) -> List[Any]:
    """Execute operations in batches to avoid overwhelming the system"""
    if not items:
        return []

    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        batch_results = []

        for item in batch:
            if asyncio.iscoroutinefunction(operation):
                result = await operation(item)
            else:
                result = operation(item)
            batch_results.append(result)

        results.extend(batch_results)

        # Small delay between batches to prevent overwhelming
        if i + batch_size < len(items):
            await asyncio.sleep(0.01)

    return results
