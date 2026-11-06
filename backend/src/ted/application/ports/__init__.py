from typing import Protocol

from .audit import AuditQueries as AuditQueries
from .audit import AuditRepository as AuditRepository
from .billing import BillingQueries as BillingQueries
from .billing import BillingRepository as BillingRepository
from .identity import IdentityQueries as IdentityQueries
from .identity import IdentityRepository as IdentityRepository
from .integrations import IntegrationsQueries as IntegrationsQueries
from .integrations import IntegrationsRepository as IntegrationsRepository
from .tracking import TrackingQueries as TrackingQueries
from .tracking import TrackingRepository as TrackingRepository
from .work import WorkQueries as WorkQueries
from .work import WorkRepository as WorkRepository
from .workspace import WorkspaceQueries as WorkspaceQueries
from .workspace import WorkspaceRepository as WorkspaceRepository


class Passwords(Protocol):
    dummy_hash: str

    def hash(self, password: str) -> str: ...
    def verify(self, password: str, hashed: str) -> bool: ...
