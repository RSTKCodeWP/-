"""Tests for utility functions."""

import pytest
from datetime import datetime, timezone
from app.utils import utc_now


def test_utc_now_returns_datetime():
    """Test that utc_now returns a datetime object."""
    result = utc_now()
    assert isinstance(result, datetime)


def test_utc_now_has_timezone():
    """Test that utc_now returns timezone-aware datetime."""
    result = utc_now()
    assert result.tzinfo is not None
    assert result.tzinfo == timezone.utc


def test_utc_now_is_current():
    """Test that utc_now returns current time."""
    before = datetime.now(timezone.utc)
    result = utc_now()
    after = datetime.now(timezone.utc)
    
    # Result should be between before and after
    assert before <= result <= after
