"""Runnable synthetic adapter contract, not an assumption about unavailable EI APIs."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ei_context import AccessScope, Evidence, SourceRef, WorkstreamRef
from ei_context.providers import FixtureProvider


@dataclass(frozen=True)
class NativeHit:
    """Illustrative host shim result; replace translation when actual EI APIs arrive."""

    id: str
    excerpt: str
    source_id: str
    uri: str | None
    version: str | None
    retrieved_at: datetime
    tenant_id: str
    access_principals: frozenset[str]


class NativeSearchShim(Protocol):
    async def search_authorised(
        self, query: str, *, scope: AccessScope, limit: int
    ) -> Sequence[NativeHit]:
        """Use native source permissions BEFORE reading/indexing/reranking source text."""
        ...


class EngineeringSearchAdapter:
    """Future EI Core connection is a host shim, with no package dependency here."""

    provider_id = "engineering-adapter"

    def __init__(self, client: NativeSearchShim) -> None:
        self.client = client

    async def search(
        self, query: str, *, scope: AccessScope, workstream: WorkstreamRef | None, limit: int
    ) -> Sequence[Evidence]:
        hits = await self.client.search_authorised(query, scope=scope, limit=limit)
        return tuple(
            Evidence(
                id=hit.id,
                text=hit.excerpt,
                source=SourceRef(
                    provider=self.provider_id,
                    source_id=hit.source_id,
                    uri=hit.uri,
                    version=hit.version,
                    retrieved_at=hit.retrieved_at,
                ),
                tenant_id=hit.tenant_id,
                access_principals=hit.access_principals,
                # No native verification attestation in this shim: remain unverified.
                trust_label="unverified",
            )
            for hit in hits[:limit]
        )


class SyntheticNativeShim:
    async def search_authorised(
        self, query: str, *, scope: AccessScope, limit: int
    ) -> Sequence[NativeHit]:
        evidence = await FixtureProvider().search(query, scope=scope, workstream=None, limit=limit)
        return tuple(
            NativeHit(
                id=e.id,
                excerpt=e.text,
                source_id=e.source.source_id,
                uri=e.source.uri,
                version=e.source.version,
                retrieved_at=e.source.retrieved_at,
                tenant_id=e.tenant_id,
                access_principals=e.access_principals,
            )
            for e in evidence
        )


async def main() -> None:
    provider = EngineeringSearchAdapter(SyntheticNativeShim())
    owner = AccessScope(tenant_id="demo", actor_id="alice")
    assert len(await provider.search("ledger", scope=owner, workstream=None, limit=5)) == 1
    outsider = AccessScope(tenant_id="demo", actor_id="bob")
    assert await provider.search("ledger", scope=outsider, workstream=None, limit=5) == ()
    print("SYNTHETIC ADAPTER PASS")


if __name__ == "__main__":
    asyncio.run(main())
