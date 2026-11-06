"""Composition root for request-scoped ports and application operations.

The existing outer transaction owns commit/rollback before a response is sent.
Repositories only flush. Every request/job receives a separate AsyncSession.
"""

import hmac
from collections.abc import AsyncIterator
from hashlib import sha256
from typing import Annotated

from fastapi import Depends, Header, Query, Request, Security
from fastapi.security import APIKeyCookie
from sqlalchemy.ext.asyncio import AsyncSession

from ted.application.access import AccessPolicy
from ted.application.activity import Activity
from ted.application.billing import CreateInvoice, FinanceReport, InvoiceLifecycle, RecordPayment
from ted.application.identity import (
    Authenticate,
    ChangePassword,
    Identity,
    Logout,
    UpdatePreferences,
)
from ted.application.integrations import IntegrationManagement
from ted.application.ports import (
    AuditRepository,
    BillingRepository,
    IdentityRepository,
    IntegrationsRepository,
    TrackingRepository,
    WorkRepository,
    WorkspaceRepository,
)
from ted.application.settings import WorkspaceSettings
from ted.application.tracking import Tracking
from ted.application.work import WorkManagement
from ted.domain.models import LoginSession, User, now
from ted.domain.rules import require
from ted.infrastructure.database import sessions
from ted.infrastructure.passwords import ArgonPasswords
from ted.infrastructure.persistence.audit import SqlAuditRepository
from ted.infrastructure.persistence.billing import SqlBillingRepository
from ted.infrastructure.persistence.identity import SqlIdentityRepository
from ted.infrastructure.persistence.integrations import SqlIntegrationsRepository
from ted.infrastructure.persistence.tracking import SqlTrackingRepository
from ted.infrastructure.persistence.work import SqlWorkRepository
from ted.infrastructure.persistence.workspace import SqlWorkspaceRepository
from ted.infrastructure.webhooks import validate_url

passwords = ArgonPasswords()
cookie = APIKeyCookie(name="ted_session", auto_error=False)


async def request_transaction() -> AsyncIterator[AsyncSession]:
    async with sessions() as db:
        async with db.begin():
            yield db


DbSession = Annotated[AsyncSession, Depends(request_transaction, scope="function")]


def identity_repository(db: DbSession) -> IdentityRepository:
    return SqlIdentityRepository(db)


def work_repository(db: DbSession) -> WorkRepository:
    return SqlWorkRepository(db)


def tracking_repository(db: DbSession) -> TrackingRepository:
    return SqlTrackingRepository(db)


def billing_repository(db: DbSession) -> BillingRepository:
    return SqlBillingRepository(db)


def workspace_repository(db: DbSession) -> WorkspaceRepository:
    return SqlWorkspaceRepository(db)


def audit_repository(db: DbSession) -> AuditRepository:
    return SqlAuditRepository(db)


def integrations_repository(db: DbSession) -> IntegrationsRepository:
    return SqlIntegrationsRepository(db)


IdentityRepo = Annotated[IdentityRepository, Depends(identity_repository)]
WorkRepo = Annotated[WorkRepository, Depends(work_repository)]
TrackingRepo = Annotated[TrackingRepository, Depends(tracking_repository)]
BillingRepo = Annotated[BillingRepository, Depends(billing_repository)]
WorkspaceRepo = Annotated[WorkspaceRepository, Depends(workspace_repository)]
AuditRepo = Annotated[AuditRepository, Depends(audit_repository)]
IntegrationsRepo = Annotated[IntegrationsRepository, Depends(integrations_repository)]


async def session_dependency(
    identity: IdentityRepo, token: Annotated[str | None, Security(cookie)]
) -> LoginSession:
    session = await identity.session(sha256((token or "").encode()).hexdigest())
    require(session is not None and session.expires_at > now(), "Sign in required", 401)
    assert session is not None
    return session


SessionDep = Annotated[LoginSession, Depends(session_dependency)]


async def actor_dependency(
    request: Request,
    identity: IdentityRepo,
    session: SessionDep,
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> User:
    user = await identity.user(session.user_id)
    require(user.active, "Sign in required", 401)
    request.state.actor_id = str(user.id)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require(hmac.compare_digest(csrf or "", session.csrf), "CSRF token required", 403)
    return user


Actor = Annotated[User, Depends(actor_dependency)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


def activity(audit: AuditRepo, integrations: IntegrationsRepo) -> Activity:
    return Activity(audit, integrations)


ActivityDep = Annotated[Activity, Depends(activity)]


def access(work: WorkRepo, actor: Actor) -> AccessPolicy:
    return AccessPolicy(work, actor)


Access = Annotated[AccessPolicy, Depends(access)]


def identity_service(
    identity: IdentityRepo, workspace: WorkspaceRepo, events: ActivityDep
) -> Identity:
    return Identity(identity, passwords, workspace, events)


IdentityService = Annotated[Identity, Depends(identity_service)]


def work_service(
    work: WorkRepo,
    identity: IdentityRepo,
    tracking: TrackingRepo,
    billing: BillingRepo,
    workspace: WorkspaceRepo,
    events: ActivityDep,
    policy: Access,
    actor: Actor,
) -> WorkManagement:
    return WorkManagement(work, identity, tracking, billing, workspace, events, policy, actor)


WorkService = Annotated[WorkManagement, Depends(work_service)]


def tracking_service(
    tracking: TrackingRepo,
    identity: IdentityRepo,
    work: WorkRepo,
    billing: BillingRepo,
    workspace: WorkspaceRepo,
    events: ActivityDep,
    policy: Access,
    actor: Actor,
) -> Tracking:
    return Tracking(tracking, identity, work, billing, workspace, events, policy, actor)


TrackingService = Annotated[Tracking, Depends(tracking_service)]


def create_invoice(
    billing: BillingRepo,
    work: WorkRepo,
    tracking: TrackingRepo,
    workspace: WorkspaceRepo,
    events: ActivityDep,
    actor: Actor,
) -> CreateInvoice:
    return CreateInvoice(billing, work, tracking, workspace, events, actor)


CreateInvoiceOperation = Annotated[CreateInvoice, Depends(create_invoice)]


def invoice_lifecycle(
    billing: BillingRepo, workspace: WorkspaceRepo, events: ActivityDep, actor: Actor
) -> InvoiceLifecycle:
    return InvoiceLifecycle(billing, workspace, events, actor)


InvoiceLifecycleOperation = Annotated[InvoiceLifecycle, Depends(invoice_lifecycle)]


def record_payment(
    billing: BillingRepo, workspace: WorkspaceRepo, events: ActivityDep, actor: Actor
) -> RecordPayment:
    return RecordPayment(billing, workspace, events, actor)


RecordPaymentOperation = Annotated[RecordPayment, Depends(record_payment)]


def finance_report(
    billing: BillingRepo,
    work: WorkRepo,
    tracking: TrackingRepo,
    workspace: WorkspaceRepo,
    actor: Actor,
) -> FinanceReport:
    return FinanceReport(billing, work, tracking, workspace, actor)


FinanceReportOperation = Annotated[FinanceReport, Depends(finance_report)]


def workspace_service(
    workspace: WorkspaceRepo, work: WorkRepo, billing: BillingRepo, events: ActivityDep
) -> WorkspaceSettings:
    return WorkspaceSettings(workspace, work, billing, events)


WorkspaceService = Annotated[WorkspaceSettings, Depends(workspace_service)]


class Destinations:
    def validate(self, url: str) -> None:
        validate_url(url)


def integration_service(
    integrations: IntegrationsRepo, events: ActivityDep
) -> IntegrationManagement:
    return IntegrationManagement(integrations, Destinations(), events)


IntegrationService = Annotated[IntegrationManagement, Depends(integration_service)]


def authenticate(identity: IdentityRepo) -> Authenticate:
    return Authenticate(identity, passwords)


Authentication = Annotated[Authenticate, Depends(authenticate)]


def logout_operation(identity: IdentityRepo) -> Logout:
    return Logout(identity)


LogoutOperation = Annotated[Logout, Depends(logout_operation)]


def update_preferences(identity: IdentityRepo) -> UpdatePreferences:
    return UpdatePreferences(identity)


PreferencesOperation = Annotated[UpdatePreferences, Depends(update_preferences)]


def change_password(identity: IdentityRepo, events: ActivityDep) -> ChangePassword:
    return ChangePassword(identity, passwords, events)


PasswordOperation = Annotated[ChangePassword, Depends(change_password)]
