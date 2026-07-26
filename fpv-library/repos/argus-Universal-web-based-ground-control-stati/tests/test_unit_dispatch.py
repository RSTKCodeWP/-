"""Tests for backend/mavlink_dispatch.py — handler registration and dispatch."""

from unittest.mock import MagicMock

from backend.mavlink_dispatch import _handlers, dispatch, register


class TestRegister:
    def test_register_handler(self):
        handler = MagicMock()
        register(9999, handler)
        assert 9999 in _handlers
        assert _handlers[9999] is handler
        del _handlers[9999]

    def test_register_overwrites(self):
        h1 = MagicMock()
        h2 = MagicMock()
        register(9998, h1)
        register(9998, h2)
        assert _handlers[9998] is h2
        del _handlers[9998]


class TestDispatch:
    def test_calls_registered_handler(self):
        handler = MagicMock()
        register(9997, handler)
        link = MagicMock()
        dispatch(9997, b"\x01\x02", 2, link)
        handler.assert_called_once_with(b"\x01\x02", 2, link)
        del _handlers[9997]

    def test_unknown_mid_no_error(self):
        link = MagicMock()
        dispatch(9996, b"", 0, link)  # Should not raise

    def test_handler_receives_correct_args(self):
        calls = []

        def handler(payload, pl, link):
            calls.append((payload, pl, link))

        register(9995, handler)
        link = MagicMock()
        dispatch(9995, b"\xaa\xbb", 5, link)
        assert len(calls) == 1
        assert calls[0] == (b"\xaa\xbb", 5, link)
        del _handlers[9995]
