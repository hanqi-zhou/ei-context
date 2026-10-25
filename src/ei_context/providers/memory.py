"""Adapt durable work memory to the same evidence interface as external sources."""

from ei_context.models import AccessScope, Evidence, SourceRef, Visibility, WorkstreamRef
from ei_context.protocols import MemoryStore


class MemoryProvider:
    provider_id = "memory"

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    async def search(
        self, query: str, *, scope: AccessScope, workstream: WorkstreamRef | None, limit: int
    ) -> tuple[Evidence, ...]:
        records = await self.store.search(query, scope=scope, workstream=workstream, limit=limit)
        return tuple(
            Evidence(
                id=f"memory:{r.id}",
                text=r.content,
                source=SourceRef(
                    provider="memory",
                    source_id=r.id,
                    version=str(r.revision),
                    uri=f"memory:{r.id}",
                    retrieved_at=r.updated_at,
                    modified_at=r.updated_at,
                    valid_until=r.valid_until,
                ),
                tenant_id=r.tenant_id,
                namespace=r.namespace,
                access_principals=frozenset(
                    {
                        f"actor:{r.actor_id}"
                        if r.visibility == Visibility.PRIVATE
                        else r.team_principal or ""
                    }
                ),
                trust_label=r.approval.method,
                workstream=r.workstream,
                source_refs=r.source_refs,
                memory_kind=r.kind,
                memory_status=r.status,
                valid_until=r.valid_until,
                metadata={"confirmation": r.approval.reference, "sensitivity": r.sensitivity},
            )
            for r in records
        )
