"""Server-configured principals. HTTP bodies never supply their own identity."""

from contextvars import ContextVar
from dataclasses import dataclass

from evosprig.core.journal import Scope


@dataclass(frozen=True)
class Principal:
    user: str = "local"
    tenant: str = "local"

    def __post_init__(self):
        Scope("identity", self.user, self.tenant)

    @property
    def key(self):
        return (self.user, self.tenant)

    def scope(self, project):
        return Scope(project, self.user, self.tenant)


current_principal = ContextVar("evosprig_principal", default=Principal())
