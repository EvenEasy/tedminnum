import json

from ted.application.ports import (
    AuditRepository,
    IntegrationsRepository,
)
from ted.domain.models import (
    Audit,
    Delivery,
    User,
    now,
)


class Activity:
    def __init__(self, audit: AuditRepository, integrations: IntegrationsRepository):
        self.audit_repository, self.integrations = audit, integrations

    async def audit(self, actor: User, action: str, id: object, detail: str = "") -> None:
        await self.audit_repository.save(
            Audit(actor_id=actor.id, action=action, object_id=str(id), detail=detail)
        )

    async def event(self, name: str, id: object) -> None:
        for hook in await self.integrations.webhooks():
            if hook.enabled:
                delivery = Delivery(webhook_id=hook.id, event=name, payload="")
                delivery.payload = json.dumps(
                    {
                        "id": str(delivery.id),
                        "event": name,
                        "object_id": str(id),
                        "occurred_at": now().isoformat(),
                    },
                    separators=(",", ":"),
                )
                await self.integrations.save(delivery)
