"""Deterministic offline providers. ACL filtering precedes text matching."""

import re
from collections.abc import Sequence
from datetime import UTC, datetime

from ei_context.models import AccessScope, Evidence, SourceRef, WorkstreamRef
from ei_context.policy import AccessPolicy


def terms(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"\w+", text.casefold()))


class InMemoryProvider:
    """Snapshot provider with scoped search, direct-ID and listing paths."""

    def __init__(
        self, provider_id: str, evidence: Sequence[Evidence], *, policy: AccessPolicy | None = None
    ) -> None:
        self.provider_id = provider_id
        self._policy = policy or AccessPolicy()
        self._records = tuple(Evidence.model_validate(e.model_dump()) for e in evidence)

    async def list(self, *, scope: AccessScope) -> tuple[Evidence, ...]:
        scope = self._policy.validate_scope(scope)
        return tuple(e for e in self._records if self._policy.evidence_allowed(e, scope))

    async def get(self, evidence_id: str, *, scope: AccessScope) -> Evidence | None:
        return next((e for e in await self.list(scope=scope) if e.id == evidence_id), None)

    async def search(
        self, query: str, *, scope: AccessScope, workstream: WorkstreamRef | None, limit: int
    ) -> tuple[Evidence, ...]:
        if not 0 < limit <= 1000:
            raise ValueError("limit must be in 1..1000")
        authorised = await self.list(scope=scope)
        query_terms = terms(query)
        ranked = sorted(
            (
                (e, len(query_terms & terms(e.text)))
                for e in authorised
                if query_terms & terms(e.text)
                or (workstream is not None and e.workstream == workstream)
            ),
            key=lambda item: (-item[1], item[0].id),
        )
        return tuple(e for e, _ in ranked[:limit])


class FixtureProvider(InMemoryProvider):
    """Synthetic ledger documentation fixture, entirely independent of EI Stack."""

    def __init__(self, *, policy: AccessPolicy | None = None) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        super().__init__(
            "fixture-docs",
            [
                Evidence(
                    id="ledger-doc-v2",
                    text="NewRoute supports ledger calculation with stable IDs.",
                    source=SourceRef(
                        provider="fixture-docs",
                        source_id="ledger-doc",
                        version="2",
                        uri="https://example.invalid/ledger/v2",
                        retrieved_at=now,
                        modified_at=now,
                    ),
                    tenant_id="demo",
                    access_principals=frozenset({"actor:alice"}),
                    trust_label="system_verified",
                    workstream=WorkstreamRef(external_id="DEMO-42"),
                )
            ],
            policy=policy,
        )
