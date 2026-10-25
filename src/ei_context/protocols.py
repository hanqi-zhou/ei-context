"""Adapter-neutral async interfaces; no EI Core/Server imports or runtime ownership."""

from collections.abc import Sequence
from typing import Protocol

from ei_context.lifecycle.events import MemoryExtractor as MemoryExtractor
from ei_context.models import (
    AccessScope,
    ApprovalEvidence,
    Evidence,
    MemoryCandidate,
    MemoryRecord,
    MemoryUpdate,
    WorkstreamRef,
)


class ContextProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    async def search(
        self, query: str, *, scope: AccessScope, workstream: WorkstreamRef | None, limit: int
    ) -> Sequence[Evidence]:
        """Authorise natively BEFORE lexical/vector/model processing and return bounded hits."""
        ...


class TokenCounter(Protocol):
    def count(self, text: str) -> int:
        """Count the entire rendered context including framing and citations."""
        ...


class Ranker(Protocol):
    def rank(
        self, query: str, evidence: Sequence[Evidence], *, workstream: WorkstreamRef | None
    ) -> Sequence[tuple[Evidence, float, str]]: ...


class MemoryStore(Protocol):
    async def create(
        self, candidate: MemoryCandidate, *, scope: AccessScope, approval: ApprovalEvidence
    ) -> MemoryRecord: ...

    async def get(self, memory_id: str, *, scope: AccessScope) -> MemoryRecord | None: ...

    async def search(
        self, query: str, *, scope: AccessScope, workstream: WorkstreamRef | None, limit: int
    ) -> Sequence[MemoryRecord]: ...

    async def list(
        self, *, scope: AccessScope, include_inactive: bool = False
    ) -> Sequence[MemoryRecord]: ...

    async def export(self, *, scope: AccessScope) -> str: ...

    async def history(self, memory_id: str, *, scope: AccessScope) -> Sequence[MemoryRecord]: ...

    async def update(
        self,
        memory_id: str,
        update: MemoryUpdate,
        *,
        expected_revision: int,
        scope: AccessScope,
        approval: ApprovalEvidence,
    ) -> MemoryRecord: ...

    async def supersede(
        self, memory_id: str, replacement_id: str, *, expected_revision: int, scope: AccessScope
    ) -> MemoryRecord: ...

    async def invalidate(
        self, memory_id: str, *, scope: AccessScope, expected_revision: int, reason: str
    ) -> MemoryRecord: ...

    async def delete(self, memory_id: str, *, scope: AccessScope) -> None: ...

    async def close(self) -> None: ...
