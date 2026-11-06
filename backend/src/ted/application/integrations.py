from secrets import token_urlsafe
from typing import Protocol
from uuid import UUID

from ted.application.access import admin
from ted.application.activity import Activity
from ted.application.ports import IntegrationsRepository
from ted.domain.models import User, Webhook


class WebhookDestinations(Protocol):
    def validate(self, url: str) -> None: ...


class IntegrationManagement:
    def __init__(
        self,
        integrations: IntegrationsRepository,
        destinations: WebhookDestinations,
        activity: Activity,
    ):
        self.integrations, self.destinations, self.activity = integrations, destinations, activity

    async def create(self, actor: User, url: str) -> Webhook:
        admin(actor)
        self.destinations.validate(url)
        hook = Webhook(url=url, secret=token_urlsafe(32))
        await self.integrations.save(hook)
        await self.activity.audit(actor, "webhook.created", hook.id)
        return hook

    async def update(self, actor: User, id: UUID, enabled: bool, rotate_secret: bool) -> Webhook:
        admin(actor)
        hook = await self.integrations.webhook(id, lock=True)
        hook.enabled = enabled
        if rotate_secret:
            hook.secret = token_urlsafe(32)
        await self.integrations.save(hook)
        await self.activity.audit(actor, "webhook.updated", id)
        return hook
