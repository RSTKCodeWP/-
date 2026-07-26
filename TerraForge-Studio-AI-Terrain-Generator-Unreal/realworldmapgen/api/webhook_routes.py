"""
Webhook subscriptions.

Clients register a URL and a set of events; TerraForge posts a JSON payload to
that URL when a matching event occurs. Payloads are signed with HMAC-SHA256
over the exact bytes sent, so receivers can verify authenticity.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

#: Events a subscription may listen for.
SUPPORTED_EVENTS = (
    "generation.started",
    "generation.completed",
    "generation.failed",
)

#: Header carrying the payload signature.
SIGNATURE_HEADER = "X-TerraForge-Signature"

DELIVERY_TIMEOUT = 10.0
DELIVERY_ATTEMPTS = 3

# In-memory storage. Subscriptions do not survive a restart; persisting them
# needs a datastore, which this service does not currently have.
_webhooks: Dict[str, "Webhook"] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WebhookCreate(BaseModel):
    url: HttpUrl
    events: List[str] = Field(..., min_length=1)
    secret: Optional[str] = Field(
        None,
        min_length=16,
        description="Shared secret used to sign deliveries (HMAC-SHA256)",
    )


class Webhook(BaseModel):
    """Internal representation, including the signing secret."""

    id: str
    url: str
    events: List[str]
    secret: Optional[str] = None
    created_at: datetime
    is_active: bool = True


class WebhookPublic(BaseModel):
    """
    What the API returns.

    The signing secret is deliberately absent: it is write-only, and echoing it
    back would hand it to anyone who can read the webhook list.
    """

    id: str
    url: str
    events: List[str]
    created_at: datetime
    is_active: bool
    has_secret: bool


class WebhookEvent(BaseModel):
    event: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=_utcnow)


def _to_public(webhook: Webhook) -> WebhookPublic:
    return WebhookPublic(
        id=webhook.id,
        url=webhook.url,
        events=webhook.events,
        created_at=webhook.created_at,
        is_active=webhook.is_active,
        has_secret=webhook.secret is not None,
    )


def _validate_events(events: List[str]) -> List[str]:
    unknown = sorted(set(events) - set(SUPPORTED_EVENTS))
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported events: {unknown}. Supported: {list(SUPPORTED_EVENTS)}",
        )
    return list(dict.fromkeys(events))


def sign_payload(body: bytes, secret: str) -> str:
    """
    Signature for a delivery.

    Computed over the exact bytes transmitted. A previous implementation
    hashed ``str(payload)`` - the Python repr of a dict - while sending JSON,
    so no receiver could ever reproduce the digest.
    """
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
@router.get("/events")
async def list_supported_events() -> Dict[str, Any]:
    """Events that can be subscribed to."""
    return {"events": list(SUPPORTED_EVENTS)}


@router.post("", response_model=WebhookPublic, status_code=201)
async def create_webhook(payload: WebhookCreate) -> WebhookPublic:
    """Create a webhook subscription."""
    events = _validate_events(payload.events)

    webhook = Webhook(
        id=f"wh_{uuid.uuid4().hex}",
        url=str(payload.url),
        events=events,
        secret=payload.secret,
        created_at=_utcnow(),
    )
    _webhooks[webhook.id] = webhook

    logger.info("Registered webhook %s for %s", webhook.id, webhook.events)
    return _to_public(webhook)


@router.get("", response_model=List[WebhookPublic])
async def list_webhooks() -> List[WebhookPublic]:
    """List all webhook subscriptions."""
    return [_to_public(webhook) for webhook in _webhooks.values()]


@router.get("/{webhook_id}", response_model=WebhookPublic)
async def get_webhook(webhook_id: str) -> WebhookPublic:
    """Get a single webhook subscription."""
    webhook = _webhooks.get(webhook_id)
    if webhook is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return _to_public(webhook)


@router.patch("/{webhook_id}", response_model=WebhookPublic)
async def update_webhook(webhook_id: str, payload: WebhookCreate) -> WebhookPublic:
    """Update a webhook subscription."""
    webhook = _webhooks.get(webhook_id)
    if webhook is None:
        raise HTTPException(status_code=404, detail="Webhook not found")

    webhook.url = str(payload.url)
    webhook.events = _validate_events(payload.events)
    if payload.secret is not None:
        webhook.secret = payload.secret

    return _to_public(webhook)


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str) -> Dict[str, Any]:
    """Delete a webhook subscription."""
    if _webhooks.pop(webhook_id, None) is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"success": True, "id": webhook_id}


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------
async def send_webhook(url: str, body: bytes, secret: Optional[str] = None) -> bool:
    """
    POST a signed payload, retrying transient failures.

    Returns True when the endpoint accepted the delivery. Failures are logged
    rather than raised: a broken subscriber must never fail the generation
    that triggered the event.
    """
    headers = {"Content-Type": "application/json"}
    if secret:
        headers[SIGNATURE_HEADER] = sign_payload(body, secret)

    for attempt in range(DELIVERY_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=DELIVERY_TIMEOUT) as client:
                response = await client.post(url, content=body, headers=headers)
                response.raise_for_status()
                return True
        except httpx.HTTPStatusError as exc:
            # 4xx means the subscriber rejected it; retrying will not help.
            if 400 <= exc.response.status_code < 500:
                logger.warning(
                    "Webhook delivery to %s rejected with %d", url, exc.response.status_code
                )
                return False
            logger.warning("Webhook delivery to %s failed: %s", url, exc)
        except Exception as exc:  # noqa: BLE001 - delivery must never propagate
            logger.warning("Webhook delivery to %s failed: %s", url, exc)

        if attempt + 1 < DELIVERY_ATTEMPTS:
            await asyncio.sleep(2**attempt)

    logger.error("Webhook delivery to %s gave up after %d attempts", url, DELIVERY_ATTEMPTS)
    return False


async def dispatch_event(event: WebhookEvent) -> int:
    """
    Deliver an event to every subscription listening for it.

    Returns the number of subscriptions the event was dispatched to.
    """
    targets = [
        webhook
        for webhook in _webhooks.values()
        if webhook.is_active and event.event in webhook.events
    ]
    if not targets:
        return 0

    # Serialize once so every receiver signs and verifies identical bytes.
    body = json.dumps(event.model_dump(mode="json"), separators=(",", ":")).encode()

    logger.info("Dispatching %s to %d webhook(s)", event.event, len(targets))
    await asyncio.gather(
        *(send_webhook(webhook.url, body, webhook.secret) for webhook in targets),
        return_exceptions=True,
    )
    return len(targets)


def emit(event_name: str, data: Dict[str, Any]) -> None:
    """
    Fire an event without blocking the caller.

    Safe to call from synchronous code paths; when no event loop is running the
    event is dropped rather than raising.
    """
    if not _webhooks:
        return

    event = WebhookEvent(event=event_name, data=data)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("No running loop; dropping webhook event %s", event_name)
        return

    task = loop.create_task(dispatch_event(event))
    # Keep a reference so the task is not garbage collected mid-flight.
    _pending.add(task)
    task.add_done_callback(_pending.discard)


_pending: set = set()
