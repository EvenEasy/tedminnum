from ted.application.access import admin
from ted.application.activity import Activity
from ted.application.ports import BillingQueries, WorkQueries, WorkspaceRepository
from ted.domain.models import User, Workspace
from ted.domain.rules import require


class WorkspaceSettings:
    def __init__(
        self,
        workspace: WorkspaceRepository,
        work: WorkQueries,
        billing: BillingQueries,
        activity: Activity,
    ):
        self.workspace, self.work, self.billing, self.activity = workspace, work, billing, activity

    async def update(self, actor: User, name: str, currency: str) -> Workspace:
        admin(actor)
        workspace = await self.workspace.workspace(lock=True)
        if currency != workspace.currency:
            require(
                not await self.billing.invoices() and not await self.work.clients(actor),
                "Set currency before adding clients or invoices",
                409,
            )
        workspace.name, workspace.currency = name, currency
        await self.workspace.save(workspace)
        await self.activity.audit(actor, "workspace.updated", workspace.id)
        return workspace
