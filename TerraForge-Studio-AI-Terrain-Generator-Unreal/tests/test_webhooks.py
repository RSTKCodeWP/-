"""
Tests for webhook subscriptions and delivery.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from realworldmapgen.api import webhook_routes
from realworldmapgen.api.webhook_routes import (
    SIGNATURE_HEADER,
    WebhookEvent,
    dispatch_event,
    sign_payload,
)


@pytest.fixture(autouse=True)
def _clear_subscriptions():
    webhook_routes._webhooks.clear()
    yield
    webhook_routes._webhooks.clear()


SECRET = "a-sufficiently-long-secret"


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def test_create_and_list_webhook(client):
    response = client.post(
        "/api/webhooks",
        json={"url": "https://example.com/hook", "events": ["generation.completed"]},
    )
    assert response.status_code == 201

    created = response.json()
    assert created["id"].startswith("wh_")
    assert created["events"] == ["generation.completed"]

    listed = client.get("/api/webhooks").json()
    assert [item["id"] for item in listed] == [created["id"]]


def test_secret_is_never_returned(client):
    """The signing secret is write-only; echoing it would leak it."""
    created = client.post(
        "/api/webhooks",
        json={
            "url": "https://example.com/hook",
            "events": ["generation.completed"],
            "secret": SECRET,
        },
    ).json()

    assert "secret" not in created
    assert created["has_secret"] is True

    fetched = client.get(f"/api/webhooks/{created['id']}").json()
    assert "secret" not in fetched
    assert SECRET not in json.dumps(client.get("/api/webhooks").json())


def test_unknown_events_are_rejected(client):
    response = client.post(
        "/api/webhooks",
        json={"url": "https://example.com/hook", "events": ["not.a.real.event"]},
    )
    assert response.status_code == 422


def test_empty_event_list_is_rejected(client):
    response = client.post(
        "/api/webhooks", json={"url": "https://example.com/hook", "events": []}
    )
    assert response.status_code == 422


def test_short_secret_is_rejected(client):
    response = client.post(
        "/api/webhooks",
        json={
            "url": "https://example.com/hook",
            "events": ["generation.completed"],
            "secret": "short",
        },
    )
    assert response.status_code == 422


def test_ids_are_unique(client):
    """Timestamp-derived ids used to collide when created in the same tick."""
    ids = {
        client.post(
            "/api/webhooks",
            json={"url": "https://example.com/hook", "events": ["generation.completed"]},
        ).json()["id"]
        for _ in range(20)
    }
    assert len(ids) == 20


def test_update_and_delete(client):
    created = client.post(
        "/api/webhooks",
        json={"url": "https://example.com/hook", "events": ["generation.completed"]},
    ).json()

    updated = client.patch(
        f"/api/webhooks/{created['id']}",
        json={"url": "https://example.com/other", "events": ["generation.failed"]},
    ).json()
    assert updated["url"] == "https://example.com/other"
    assert updated["events"] == ["generation.failed"]

    assert client.delete(f"/api/webhooks/{created['id']}").status_code == 200
    assert client.get(f"/api/webhooks/{created['id']}").status_code == 404


def test_missing_webhook_returns_404(client):
    assert client.get("/api/webhooks/wh_missing").status_code == 404
    assert client.delete("/api/webhooks/wh_missing").status_code == 404


def test_supported_events_endpoint(client):
    events = client.get("/api/webhooks/events").json()["events"]
    assert "generation.completed" in events


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------
def test_signature_is_computed_over_the_transmitted_bytes():
    """
    The digest must cover exactly what is sent.

    The previous implementation hashed ``str(payload)`` - a Python dict repr -
    while POSTing JSON, so no receiver could reproduce it.
    """
    body = b'{"event":"generation.completed"}'

    signature = sign_payload(body, SECRET)

    expected = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert signature == f"sha256={expected}"


def test_signature_changes_with_the_payload():
    assert sign_payload(b'{"a":1}', SECRET) != sign_payload(b'{"a":2}', SECRET)


@pytest.mark.asyncio
async def test_receiver_can_verify_a_real_delivery(monkeypatch):
    """A subscriber can validate the signature against the body it receives."""
    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            return None

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def post(self, url, content, headers):
            captured["body"] = content
            captured["signature"] = headers[SIGNATURE_HEADER]
            return _FakeResponse()

    monkeypatch.setattr(webhook_routes.httpx, "AsyncClient", lambda **kw: _FakeClient())

    webhook_routes._webhooks["wh_1"] = webhook_routes.Webhook(
        id="wh_1",
        url="https://example.com/hook",
        events=["generation.completed"],
        secret=SECRET,
        created_at=webhook_routes._utcnow(),
    )

    await dispatch_event(
        WebhookEvent(event="generation.completed", data={"task_id": "t1"})
    )

    # This is exactly what a subscriber would do to authenticate the request.
    algo, _, digest = captured["signature"].partition("=")
    assert algo == "sha256"
    assert hmac.compare_digest(
        digest, hmac.new(SECRET.encode(), captured["body"], hashlib.sha256).hexdigest()
    )
    assert json.loads(captured["body"])["data"]["task_id"] == "t1"


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dispatch_delivers_to_subscribers(monkeypatch):
    sent = []

    async def fake_send(url, body, secret=None):
        sent.append((url, body, secret))
        return True

    monkeypatch.setattr(webhook_routes, "send_webhook", fake_send)

    webhook_routes._webhooks["wh_1"] = webhook_routes.Webhook(
        id="wh_1",
        url="https://example.com/hook",
        events=["generation.completed"],
        secret=SECRET,
        created_at=webhook_routes._utcnow(),
    )

    delivered = await dispatch_event(
        WebhookEvent(event="generation.completed", data={"task_id": "t1"})
    )

    assert delivered == 1
    url, body, secret = sent[0]
    assert url == "https://example.com/hook"
    assert secret == SECRET
    # Body must be valid JSON matching the event.
    assert json.loads(body)["data"]["task_id"] == "t1"


@pytest.mark.asyncio
async def test_dispatch_skips_unsubscribed_events(monkeypatch):
    sent = []

    async def fake_send(url, body, secret=None):
        sent.append(url)
        return True

    monkeypatch.setattr(webhook_routes, "send_webhook", fake_send)

    webhook_routes._webhooks["wh_1"] = webhook_routes.Webhook(
        id="wh_1",
        url="https://example.com/hook",
        events=["generation.failed"],
        created_at=webhook_routes._utcnow(),
    )

    delivered = await dispatch_event(
        WebhookEvent(event="generation.completed", data={})
    )

    assert delivered == 0
    assert sent == []


@pytest.mark.asyncio
async def test_dispatch_skips_inactive_subscriptions(monkeypatch):
    async def fake_send(url, body, secret=None):
        pytest.fail("inactive webhook should not be delivered to")

    monkeypatch.setattr(webhook_routes, "send_webhook", fake_send)

    webhook_routes._webhooks["wh_1"] = webhook_routes.Webhook(
        id="wh_1",
        url="https://example.com/hook",
        events=["generation.completed"],
        created_at=webhook_routes._utcnow(),
        is_active=False,
    )

    assert await dispatch_event(WebhookEvent(event="generation.completed", data={})) == 0


@pytest.mark.asyncio
async def test_all_subscribers_share_identical_bytes(monkeypatch):
    """Every receiver must sign the same bytes, or signatures would differ."""
    bodies = []

    async def fake_send(url, body, secret=None):
        bodies.append(body)
        return True

    monkeypatch.setattr(webhook_routes, "send_webhook", fake_send)

    for index in range(3):
        webhook_routes._webhooks[f"wh_{index}"] = webhook_routes.Webhook(
            id=f"wh_{index}",
            url=f"https://example.com/{index}",
            events=["generation.completed"],
            created_at=webhook_routes._utcnow(),
        )

    await dispatch_event(WebhookEvent(event="generation.completed", data={"a": 1}))

    assert len(bodies) == 3
    assert len(set(bodies)) == 1


@pytest.mark.asyncio
async def test_delivery_failure_does_not_propagate(monkeypatch):
    """A broken subscriber must never break the generation that triggered it."""

    async def exploding_send(url, body, secret=None):
        raise RuntimeError("subscriber is down")

    monkeypatch.setattr(webhook_routes, "send_webhook", exploding_send)

    webhook_routes._webhooks["wh_1"] = webhook_routes.Webhook(
        id="wh_1",
        url="https://example.com/hook",
        events=["generation.completed"],
        created_at=webhook_routes._utcnow(),
    )

    # gather(return_exceptions=True) swallows it; no raise expected here.
    assert await dispatch_event(WebhookEvent(event="generation.completed", data={})) == 1


def test_emit_without_a_running_loop_is_a_noop():
    """Called from sync code with no loop, emit drops the event rather than raising."""
    webhook_routes._webhooks["wh_1"] = webhook_routes.Webhook(
        id="wh_1",
        url="https://example.com/hook",
        events=["generation.completed"],
        created_at=webhook_routes._utcnow(),
    )

    webhook_routes.emit("generation.completed", {"task_id": "t1"})
