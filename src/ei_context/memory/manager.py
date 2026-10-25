"""Explicit memory approval and lifecycle facade; no model calls or automatic publication."""

from ei_context.models import (
    AccessScope,
    ApprovalEvidence,
    MemoryCandidate,
    MemoryRecord,
    MemoryUpdate,
    WorkstreamRef,
)
from ei_context.policy import AccessPolicy
from ei_context.protocols import MemoryStore


class MemoryManager:
    """Caller attests provenance through ApprovalEvidence. No implicit technical verification."""

    def __init__(self, store: MemoryStore, *, policy: AccessPolicy | None = None) -> None:
        self.store = store
        self.policy = policy or AccessPolicy()

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
