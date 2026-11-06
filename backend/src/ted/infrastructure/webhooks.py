"""Bounded transactional outbox. Run one lightweight worker beside the API."""

import asyncio
import hmac
import ipaddress
import logging
import socket
import time
from datetime import timedelta
from hashlib import sha256
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select

from ted.domain.models import Delivery, Webhook, now
from ted.domain.rules import Problem, require
from ted.infrastructure.database import engine, sessions
from ted.infrastructure.persistence.mapping import to_domain
from ted.infrastructure.persistence.records import DeliveryRow, WebhookRow
from ted.infrastructure.persistence.schema import tables
from ted.infrastructure.runtime import settings


def validate_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise Problem("Invalid webhook URL") from error
    hosts = {h.strip().lower() for h in settings.webhook_hosts.split(",") if h.strip()}
    require(
        parsed.scheme == "https"
        and parsed.hostname in hosts
        and port in (None, 443)
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment,
        "Use HTTPS on port 443 with a host in the operator's WEBHOOK_HOSTS allowlist",
    )


def signature(secret: str, timestamp: str, payload: bytes) -> str:
    return (
        "v1=" + hmac.new(secret.encode(), timestamp.encode() + b"." + payload, sha256).hexdigest()
    )


async def deliver(hook: Webhook, delivery: Delivery) -> int:
    validate_url(hook.url)
    parsed = urlsplit(hook.url)
    assert parsed.hostname is not None
    addresses = await asyncio.wait_for(
        asyncio.to_thread(socket.getaddrinfo, parsed.hostname, 443, type=socket.SOCK_STREAM),
        timeout=5,
    )
    ips = sorted({str(item[4][0]) for item in addresses})
    require(
        bool(ips) and all(ipaddress.ip_address(ip).is_global for ip in ips),
        "Non-public webhook destination rejected",
    )
    # Pin the validated IP to prevent a second DNS resolution / rebinding at connect time.
    ip = ips[0]
    host = f"[{ip}]" if ":" in ip else ip
    target = f"https://{host}{parsed.path or '/'}" + (f"?{parsed.query}" if parsed.query else "")
    stamp = str(int(time.time()))
    payload = delivery.payload.encode()
    async with httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False) as client:
        async with client.stream(
            "POST",
            target,
            content=payload,
            headers={
                "Host": parsed.hostname,
                "Content-Type": "application/json",
                "X-Ted-Timestamp": stamp,
                "X-Ted-Signature": signature(hook.secret, stamp, payload),
            },
            extensions={"sni_hostname": parsed.hostname},
        ) as response:
            return response.status_code


async def tick() -> bool:
    async with sessions() as session, session.begin():
        c = tables[DeliveryRow].c
        delivery = await session.scalar(
            select(DeliveryRow)
            .where(c.delivered_at.is_(None), c.attempts < 6, c.next_attempt <= now())
            .order_by(c.next_attempt)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if delivery is None:
            return False
        hook = await session.get(WebhookRow, delivery.webhook_id)
        if hook is None or not hook.enabled:
            delivery.attempts, delivery.status_code = 6, -2
            return True
        try:
            delivery.status_code = await deliver(
                to_domain(hook, Webhook), to_domain(delivery, Delivery)
            )
        except Exception:
            # Never log URLs, payloads, secrets, or raw network exceptions.
            delivery.status_code = -1
        delivery.attempts += 1
        if 200 <= delivery.status_code < 300:
            delivery.delivered_at = now()
        else:
            delivery.next_attempt = now() + timedelta(
                seconds=min(300, 5 * 2 ** (delivery.attempts - 1))
            )
        return True


async def main() -> None:
    try:
        while True:
            try:
                available = await tick()
            except Exception as error:
                logging.getLogger(__name__).warning(
                    "Webhook poll failed (%s)", type(error).__name__
                )
                available = False
            if not available:
                await asyncio.sleep(2)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
