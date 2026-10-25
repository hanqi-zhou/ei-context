from datetime import UTC, datetime

import pytest

from ei_context import AccessScope, ApprovalEvidence, MemoryCandidate, MemoryKind, SourceRef


@pytest.fixture
def scope():
    return AccessScope(tenant_id="demo", actor_id="alice")


@pytest.fixture
def now():
    return datetime(2026, 1, 2, tzinfo=UTC)


@pytest.fixture
def ref(now):
    return SourceRef(provider="fixture-docs", source_id="ledger-doc", version="1", retrieved_at=now)


@pytest.fixture
def approval(now):
    return ApprovalEvidence(
        actor_id="alice", method="user_confirmed", reference="approval:1", approved_at=now
    )


@pytest.fixture
def candidate(ref):
    return MemoryCandidate(
        kind=MemoryKind.DECISION, content="Choose NewRoute for ledger.", source_refs=(ref,)
    )
