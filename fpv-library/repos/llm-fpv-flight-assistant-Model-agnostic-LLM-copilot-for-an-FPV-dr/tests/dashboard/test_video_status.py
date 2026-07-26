import pytest
from dashboard.__main__ import poll_once


class FakeResp:
    def __init__(self, ok): self._ok = ok
    def json(self): return {"ok": self._ok, "age_s": 0.1}
    def raise_for_status(self): ...


class FakeHttp:
    def __init__(self, ok=True, fail=False): self._ok = ok; self._fail = fail
    async def get(self, url):
        if self._fail:
            raise RuntimeError("connection refused")
        return FakeResp(self._ok)


@pytest.mark.asyncio
async def test_poll_once_healthy():
    msg = await poll_once(FakeHttp(ok=True), "http://x/health", "http://x/stream.mjpg")
    assert msg == {"type": "video_status", "ok": True, "url": "http://x/stream.mjpg"}


@pytest.mark.asyncio
async def test_poll_once_unreachable_is_not_ok():
    msg = await poll_once(FakeHttp(fail=True), "http://x/health", "http://x/stream.mjpg")
    assert msg["type"] == "video_status" and msg["ok"] is False
