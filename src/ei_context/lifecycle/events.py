"""Observable host events, never private reasoning, transcripts or runtime checkpoints."""

from collections.abc import Sequence
from typing import Literal, Protocol

from pydantic import AwareDatetime

from ei_context.models import (
    AccessScope,
    Identifier,
    MemoryCandidate,
    MemoryKind,
    Model,
    SourceRef,
    Text,
    WorkstreamRef,
)


class ContextEvent(Model):
    schema_version: Literal["1"] = "1"
    id: Identifier
    kind: Literal[
        "user_confirmed_decision",
        "user_confirmed_finding",
        "tool_result",
        "run_completed",
        "context_refresh",
    ]
    tenant_id: Identifier
    actor_id: Identifier
    namespace: Identifier = "work"
    occurred_at: AwareDatetime
    workstream: WorkstreamRef | None = None
    summary: Text | None = None
    source_refs: tuple[SourceRef, ...] = ()
    proposal: MemoryCandidate | None = None


class MemoryExtractor(Protocol):
    """Optional extractor processes only pre-authorised events; outputs remain proposals."""

    async def extract(
        self, event: ContextEvent, *, scope: AccessScope
    ) -> Sequence[MemoryCandidate]: ...


class ExplicitOnlyExtractor:
    """No LLM or raw-tool extraction. Confirmed statements still need commit approval."""

    async def extract(
        self, event: ContextEvent, *, scope: AccessScope
    ) -> tuple[MemoryCandidate, ...]:
        if event.proposal is not None:
            return (event.proposal,)
        explicit_kind = {
            "user_confirmed_decision": MemoryKind.DECISION,
            "user_confirmed_finding": MemoryKind.FINDING,
        }.get(event.kind)
        if explicit_kind is None or event.summary is None or not event.source_refs:
            return ()
        return (
            MemoryCandidate(
                kind=explicit_kind,
                content=event.summary,
                source_refs=event.source_refs,
                namespace=event.namespace,
                workstream=event.workstream,
                source_event=event.id,
            ),
        )
