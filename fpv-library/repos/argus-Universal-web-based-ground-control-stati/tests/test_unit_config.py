"""Tests for backend/config.py — configuration defaults and env overrides."""

import os
from unittest.mock import patch

from backend.config import Config, _env


class TestEnvHelper:
    def test_returns_default_when_unset(self):
        assert _env("ARGUS_NONEXISTENT_KEY_12345", 42) == 42

    def test_returns_env_value_with_type_cast(self):
        with patch.dict(os.environ, {"ARGUS_TEST_INT": "9999"}):
            assert _env("ARGUS_TEST_INT", 0) == 9999

    def test_string_default(self):
        with patch.dict(os.environ, {"ARGUS_TEST_STR": "hello"}):
            assert _env("ARGUS_TEST_STR", "") == "hello"

    def test_float_cast(self):
        with patch.dict(os.environ, {"ARGUS_TEST_F": "3.14"}):
            assert _env("ARGUS_TEST_F", 0.0) == 3.14

    def test_explicit_cast_function(self):
        with patch.dict(os.environ, {"ARGUS_TEST_CAST": "1"}):
            assert _env("ARGUS_TEST_CAST", False, cast=bool) is True


class TestConfigDefaults:
    def test_host_type(self):
        assert isinstance(Config.HOST, str)

    def test_port_type(self):
        assert isinstance(Config.PORT, int)

    def test_push_intervals(self):
        assert Config.WS_PUSH_INTERVAL_CONNECTED < Config.WS_PUSH_INTERVAL_IDLE

    def test_timeouts_positive(self):
        assert Config.TCP_CONNECT_TIMEOUT > 0
        assert Config.TCP_READ_TIMEOUT > 0
        assert Config.SERIAL_READ_TIMEOUT > 0

    def test_tile_cache_max(self):
        assert Config.TILE_CACHE_MAX > 0
