from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .drone_link import DroneLink

_handlers: dict[int, Callable] = {}


def register(mid: int, handler: Callable) -> None:
    _handlers[mid] = handler


def dispatch(mid: int, payload: bytes, pl: int, link: DroneLink) -> None:
    handler = _handlers.get(mid)
    if handler:
        handler(payload, pl, link)
