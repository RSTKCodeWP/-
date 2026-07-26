"""Tests for metrics service."""

import pytest
from app.services.metrics import MetricsCollector, metrics


@pytest.fixture
def collector():
    """Create fresh metrics collector."""
    return MetricsCollector()


@pytest.mark.asyncio
async def test_increment_counter(collector):
    """Test counter increment."""
    await collector.increment_counter("test_counter")
    await collector.increment_counter("test_counter")
    await collector.increment_counter("test_counter", value=5)

    metrics_text = await collector.get_metrics()
    assert "test_counter 7" in metrics_text


@pytest.mark.asyncio
async def test_counter_with_labels(collector):
    """Test counter with labels."""
    await collector.increment_counter("requests", labels={"method": "GET"})
    await collector.increment_counter("requests", labels={"method": "POST"})
    await collector.increment_counter("requests", labels={"method": "GET"})

    metrics_text = await collector.get_metrics()
    assert 'requests{method="GET"} 2' in metrics_text
    assert 'requests{method="POST"} 1' in metrics_text


@pytest.mark.asyncio
async def test_set_gauge(collector):
    """Test gauge setting."""
    await collector.set_gauge("active_users", 42)
    await collector.set_gauge("active_users", 50)

    metrics_text = await collector.get_metrics()
    assert "active_users 50" in metrics_text


@pytest.mark.asyncio
async def test_observe_histogram(collector):
    """Test histogram observation."""
    await collector.observe_histogram("request_duration", 0.1)
    await collector.observe_histogram("request_duration", 0.2)
    await collector.observe_histogram("request_duration", 0.3)

    metrics_text = await collector.get_metrics()
    assert "request_duration_count 3" in metrics_text
    assert "request_duration_sum 0.6" in metrics_text


@pytest.mark.asyncio
async def test_reset_metrics(collector):
    """Test metrics reset."""
    await collector.increment_counter("test")
    await collector.set_gauge("gauge", 100)

    await collector.reset()

    metrics_text = await collector.get_metrics()
    assert "test" not in metrics_text
    assert "gauge" not in metrics_text


@pytest.mark.asyncio
async def test_global_metrics_instance():
    """Test global metrics instance."""
    await metrics.reset()
    await metrics.increment_counter("global_test")

    metrics_text = await metrics.get_metrics()
    assert "global_test 1" in metrics_text

    # Cleanup
    await metrics.reset()
