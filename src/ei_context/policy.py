"""Access enforcement shared by local providers, memory stores, and the engine."""

from collections.abc import Callable
from typing import Protocol

from pydantic import ValidationError

from ei_context.errors import AccessDenied, InvalidScope
from ei_context.models import (
    AccessScope,
    Evidence,
    MemoryCandidate,
    MemoryRecord,
    SourceRef,
    Visibility,
)


class GrantResolver(Protocol):
    """A trusted host resolves current grants from authenticated identity, never request hints."""

    def __call__(self, tenant_id: str, actor_id: str) -> frozenset[str]: ...


class AccessPolicy:
    """Default deny team/org. Private ownership cannot be delegated using principal hints."""

    def __init__(self, grant_resolver: GrantResolver | None = None) -> None:
        self._resolve = grant_resolver

    def validate_scope(self, scope: AccessScope) -> AccessScope:
        try:
            return AccessScope.model_validate(scope)
        except (ValidationError, TypeError):
            raise InvalidScope("a valid authenticated scope is required") from None

    def grants(self, scope: AccessScope) -> frozenset[str]:
        scope = self.validate_scope(scope)
        verified = self._resolve(scope.tenant_id, scope.actor_id) if self._resolve else frozenset()
        return frozenset({f"actor:{scope.actor_id}"}) | frozenset(
            grant for grant in verified if grant.startswith("team:")
        )

    def sources_allowed(self, refs: tuple[SourceRef, ...], scope: AccessScope) -> bool:
        scope = self.validate_scope(scope)
        return scope.allowed_sources is None or all(
            ref.identity in scope.allowed_sources for ref in refs
        )

    def evidence_allowed(self, evidence: Evidence, scope: AccessScope) -> bool:
        scope = self.validate_scope(scope)
        refs = (
            evidence.source_refs
            if evidence.source.provider == "memory" and evidence.memory_kind is not None
            else (evidence.source, *evidence.source_refs)
        )
        return (
            evidence.tenant_id == scope.tenant_id
            and evidence.namespace in scope.allowed_namespaces
            and bool(evidence.access_principals & self.grants(scope))
            and self.sources_allowed(refs, scope)
        )

    def memory_allowed(self, record: MemoryRecord, scope: AccessScope) -> bool:
        scope = self.validate_scope(scope)
        return (
            record.tenant_id == scope.tenant_id
            and record.namespace in scope.allowed_namespaces
            and self.sources_allowed(record.source_refs, scope)
            and (
                (record.visibility == Visibility.PRIVATE and record.actor_id == scope.actor_id)
                or (
                    record.visibility == Visibility.TEAM
                    and record.team_principal in self.grants(scope)
                )
            )
        )

    def require_write(self, candidate: MemoryCandidate, scope: AccessScope) -> None:
        scope = self.validate_scope(scope)
        if (
            candidate.namespace not in scope.allowed_namespaces
            or not self.sources_allowed(candidate.source_refs, scope)
            or candidate.visibility == Visibility.ORG
            or (
                candidate.visibility == Visibility.TEAM
                and (
                    candidate.team_principal not in self.grants(scope)
                    or not (candidate.team_principal or "").startswith("team:")
                )
            )
        ):
            raise AccessDenied("memory write is not authorised")

    def require_owner(self, record: MemoryRecord, scope: AccessScope) -> None:
        if not self.memory_allowed(record, scope) or record.actor_id != scope.actor_id:
            raise AccessDenied("memory is unavailable for mutation")


# A resolver may be an ordinary function; this alias is useful in host annotations.
GrantFunction = Callable[[str, str], frozenset[str]]
