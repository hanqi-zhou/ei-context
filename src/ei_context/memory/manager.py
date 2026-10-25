"""Explicit memory approval and lifecycle facade; no model calls or automatic publication."""

from collections.abc import Sequence

from ei_context.errors import AccessDenied, InvalidMemory
from ei_context.lifecycle.events import ContextEvent, ExplicitOnlyExtractor, MemoryExtractor
from ei_context.models import (
    AccessScope,
    ApprovalEvidence,
    MemoryCandidate,
    MemoryRecord,
    MemoryUpdate,
    Visibility,
    WorkstreamRef,
)
from ei_context.policy import AccessPolicy
from ei_context.protocols import MemoryStore


class MemoryManager:
    """Caller attests provenance through ApprovalEvidence. No implicit technical verification."""

    def __init__(
        self,
        store: MemoryStore,
        *,
        policy: AccessPolicy | None = None,
        extractor: MemoryExtractor | None = None,
    ) -> None:
        self.store = store
        self.policy = policy or AccessPolicy()
        self.extractor = extractor or ExplicitOnlyExtractor()

    async def commit(
        self, candidate: MemoryCandidate, *, scope: AccessScope, approval: ApprovalEvidence
    ) -> MemoryRecord:
        self.policy.require_write(candidate, scope)
        return await self.store.create(candidate, scope=scope, approval=approval)

    async def search(
        self,
        query: str,
        *,
        scope: AccessScope,
        workstream: WorkstreamRef | None = None,
        limit: int = 20,
    ) -> list[MemoryRecord]:
        self.policy.validate_scope(scope)
        return list(await self.store.search(query, scope=scope, workstream=workstream, limit=limit))

    async def update(
        self,
        memory_id: str,
        update: MemoryUpdate,
        *,
        expected_revision: int,
        scope: AccessScope,
        approval: ApprovalEvidence,
    ) -> MemoryRecord:
        return await self.store.update(
            memory_id, update, expected_revision=expected_revision, scope=scope, approval=approval
        )

    async def supersede(
        self, memory_id: str, replacement_id: str, *, expected_revision: int, scope: AccessScope
    ) -> MemoryRecord:
        return await self.store.supersede(
            memory_id, replacement_id, expected_revision=expected_revision, scope=scope
        )

    async def invalidate(
        self, memory_id: str, *, scope: AccessScope, expected_revision: int, reason: str
    ) -> MemoryRecord:
        return await self.store.invalidate(
            memory_id, scope=scope, expected_revision=expected_revision, reason=reason
        )

    async def delete(self, memory_id: str, *, scope: AccessScope) -> None:
        await self.store.delete(memory_id, scope=scope)

    async def propose_from_event(
        self, event: ContextEvent, *, scope: AccessScope
    ) -> list[MemoryCandidate]:
        """Stage candidates in caller memory only; filter before optional external extraction."""
        scope = self.policy.validate_scope(scope)
        event = ContextEvent.model_validate(event)
        if (
            event.tenant_id != scope.tenant_id
            or event.actor_id != scope.actor_id
            or event.namespace not in scope.allowed_namespaces
            or not self.policy.sources_allowed(event.source_refs, scope)
        ):
            raise AccessDenied("event is outside authenticated scope")
        event_snapshots = {ref.model_dump_json() for ref in event.source_refs}

        def validate_lineage(candidate: MemoryCandidate) -> None:
            self.policy.require_write(candidate, scope)
            if any(ref.model_dump_json() not in event_snapshots for ref in candidate.source_refs):
                raise InvalidMemory("proposal provenance must be observed in its source event")

        if event.proposal is not None:
            validate_lineage(event.proposal)
        proposed = await self.extractor.extract(event, scope=scope)
        if len(proposed) > 100:
            raise InvalidMemory("extractor candidate limit exceeded")
        candidates = []
        for raw in proposed:
            candidate = MemoryCandidate.model_validate(raw)
            validate_lineage(candidate)
            if (
                candidate.visibility != Visibility.PRIVATE
                or candidate.namespace != event.namespace
                or candidate.workstream != event.workstream
            ):
                raise InvalidMemory("extracted proposals must preserve private event scope")
            expected_kind = {
                "user_confirmed_decision": "decision",
                "user_confirmed_finding": "finding",
            }.get(event.kind)
            if expected_kind is not None and candidate.kind.value != expected_kind:
                raise InvalidMemory("confirmed event and proposed memory kind must match")
            candidates.append(candidate.model_copy(update={"source_event": event.id}))
        return candidates

    async def distill(
        self, events: Sequence[ContextEvent], *, scope: AccessScope
    ) -> list[MemoryCandidate]:
        """Stage explicit observable outcomes, without saving events or scheduling runs."""
        self.policy.validate_scope(scope)
        if len(events) > 1000:
            raise InvalidMemory("event batch limit exceeded")
        candidates: list[MemoryCandidate] = []
        for event in events:
            candidates.extend(await self.propose_from_event(event, scope=scope))
        return candidates
