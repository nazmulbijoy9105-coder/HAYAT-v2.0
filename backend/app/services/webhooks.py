"""
HAYAT v2.0 — Webhook System
Event-driven notifications for institutional clients.
"""

import hmac
import hashlib
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("hayat.webhooks")


class WebhookEvent:
    """Standardized webhook event types."""
    CASE_CREATED = "case.created"
    CASE_UPDATED = "case.updated"
    STATUTE_CREATED = "statute.created"
    STATUTE_AMENDED = "statute.amended"
    DOCUMENT_PROCESSED = "document.processed"
    DOCUMENT_FAILED = "document.failed"
    SEARCH_PERFORMED = "search.performed"
    AI_QUERY = "ai.query"
    DEADLINE_APPROACHING = "deadline.approaching"
    DEADLINE_OVERDUE = "deadline.overdue"


class WebhookDelivery:
    """Webhook delivery service with retry and signature verification."""

    MAX_RETRIES = 5
    RETRY_DELAYS = [1, 5, 15, 60, 300]

    def __init__(self):
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )

    def _sign_payload(self, payload: str, secret: str) -> str:
        return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

    async def _deliver_single(self, url: str, event: str, payload: Dict[str, Any], secret: str) -> bool:
        event_id = str(uuid4())
        timestamp = datetime.utcnow().isoformat()

        body = json.dumps({"event_id": event_id, "event": event, "timestamp": timestamp, "data": payload}, default=str)
        signature = self._sign_payload(body, secret)

        try:
            response = await self.http_client.post(
                url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-HAYAT-Event": event,
                    "X-HAYAT-Signature": f"sha256={signature}",
                    "X-HAYAT-Event-ID": event_id,
                    "X-HAYAT-Timestamp": timestamp,
                },
            )
            success = response.status_code < 400
            logger.info("webhook_delivered" if success else "webhook_failed", event=event, url=url, status=response.status_code)
            return success
        except Exception as e:
            logger.error("webhook_delivery_error", event=event, url=url, error=str(e))
            return False

    async def deliver(self, event: str, payload: Dict[str, Any], subscribers: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        results = []
        for sub in subscribers:
            url = sub["url"]
            secret = sub["secret"]
            delivered = False
            attempts = 0
            for delay in self.RETRY_DELAYS:
                attempts += 1
                delivered = await self._deliver_single(url, event, payload, secret)
                if delivered:
                    break
                if attempts < len(self.RETRY_DELAYS):
                    import asyncio
                    await asyncio.sleep(delay)
            results.append({"url": url, "delivered": delivered, "attempts": attempts})
        return results

    async def verify_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        expected = self._sign_payload(payload.decode(), secret)
        return hmac.compare_digest(f"sha256={expected}", signature)


class WebhookManager:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.delivery = WebhookDelivery()

    async def subscribe(self, user_id: str, url: str, events: List[str], secret: str) -> Dict[str, Any]:
        subscription = {
            "id": str(uuid4()),
            "user_id": user_id,
            "url": url,
            "events": events,
            "secret": secret,
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
        }
        logger.info("webhook_subscribed", user_id=user_id, url=url, events=events)
        return subscription

    async def unsubscribe(self, subscription_id: str) -> bool:
        logger.info("webhook_unsubscribed", subscription_id=subscription_id)
        return True

    async def broadcast(self, event: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        subscribers = []
        if subscribers:
            return await self.delivery.deliver(event, payload, subscribers)
        return []
