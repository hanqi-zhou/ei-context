"""Synthetic persistence, memory provenance and small/medium local-search measurements."""

import asyncio
import json
import statistics
import tempfile
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

from ei_context import (
    AccessScope,
    ApprovalEvidence,
    ContextEngine,
    ContextRequest,
    Evidence,
    MemoryCandidate,
    MemoryKind,
    SourceRef,
    SQLiteMemoryStore,
    WorkstreamRef,
)
from ei_context.providers import FixtureProvider, InMemoryProvider
from ei_context.providers.memory import MemoryProvider

NOW = datetime(2026, 1, 2, tzinfo=UTC)
SCOPE = AccessScope(tenant_id="demo", actor_id="alice")
APPROVAL = ApprovalEvidence(
    actor_id="alice", method="user_confirmed", reference="eval:approval", approved_at=NOW
)
REF = SourceRef(provider="fixture-docs", source_id="ledger-doc", version="2", retrieved_at=NOW)


async def measure_store(path: Path, size: int) -> dict[str, object]:
    store = SQLiteMemoryStore(path, clock=lambda: NOW)
    for i in range(size):
        await store.create(
            MemoryCandidate(
                kind=MemoryKind.FINDING,
                content=f"Synthetic ledger finding specimen {i}",
                source_refs=(REF,),
            ),
            scope=SCOPE,
            approval=APPROVAL,
        )
    await store.close()
    store = SQLiteMemoryStore(path, clock=lambda: NOW)
    latency = []
    tracemalloc.start()
    for _ in range(30):
        start = time.perf_counter()
        rows = await store.search("ledger finding", scope=SCOPE, workstream=None, limit=10)
        latency.append((time.perf_counter() - start) * 1000)
        assert len(rows) == 10
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    output = {
        "records": size,
        "searches": 30,
        "fts5": store.fts_available,
        "latency_ms_p50": statistics.median(latency),
        "latency_ms_p95": sorted(latency)[28],
        "python_peak_bytes_during_search": peak,
    }
    await store.close()
    return output


async def quality(path: Path) -> dict[str, object]:
    store = SQLiteMemoryStore(path, clock=lambda: NOW)
    work = WorkstreamRef(external_id="DEMO-42")
    # Two supported memories, one intentionally stale decision, one invalidated record.
    for kind, text, ref in [
        (
            MemoryKind.DECISION,
            "Choose NewRoute for ledger",
            REF.model_copy(update={"version": "1"}),
        ),
        (MemoryKind.ATTEMPT, "LegacyRoute rejected due to unsigned balance incompatibility", REF),
        (MemoryKind.OPEN_QUESTION, "Open question: ledger rounding test", REF),
    ]:
        await store.create(
            MemoryCandidate(kind=kind, content=text, source_refs=(ref,), workstream=work),
            scope=SCOPE,
            approval=APPROVAL,
        )
    invalid = await store.create(
        MemoryCandidate(
            kind=MemoryKind.FINDING,
            content="Obsolete ledger recommendation",
            source_refs=(REF,),
            workstream=work,
        ),
        scope=SCOPE,
        approval=APPROVAL,
    )
    await store.invalidate(invalid.id, scope=SCOPE, expected_revision=1, reason="obsolete fixture")
    await store.close()
    store = SQLiteMemoryStore(path, clock=lambda: NOW)
    technical = Evidence(
        id="eval-test",
        text=(
            "LegacyRoute rejected due to unsigned balance incompatibility. "
            "Ledger rounding test remains open."
        ),
        source=REF.model_copy(update={"source_id": "ledger-test"}),
        tenant_id="demo",
        access_principals={"actor:alice"},
        trust_label="system_verified",
        workstream=work,
    )
    engine = ContextEngine(
        [FixtureProvider(), InMemoryProvider("tests", [technical]), MemoryProvider(store)],
        clock=lambda: NOW,
    )
    bundle = await engine.prepare(
        ContextRequest(
            query="Continue ledger NewRoute LegacyRoute rounding",
            scope=SCOPE,
            workstream=work,
            token_budget=16000,
        )
    )
    memories = [s for s in bundle.selected if s.memory_kind is not None]
    unsupported = [s for s in memories if not all(ref.version == "2" for ref in s.source_refs)]
    unsafe = [s for s in unsupported if not s.caveats]
    leaks = 0
    for other in [
        AccessScope(tenant_id="demo", actor_id="bob"),
        AccessScope(tenant_id="other", actor_id="alice"),
    ]:
        leaks += len((await engine.prepare(ContextRequest(query="ledger", scope=other))).selected)
    result = {
        "expected_memory_recall": len({s.memory_kind for s in memories}) / 3,
        "selected_memories": len(memories),
        "unsupported_memory_rate": len(unsupported) / len(memories),
        "uncaveated_unsupported_memory_rate": len(unsafe) / len(memories),
        "citation_coverage": sum(bool(s.citation and s.source_refs) for s in memories)
        / len(memories),
        "private_actor_and_tenant_leakage": leaks,
        "invalidated_memory_selected": any(
            s.evidence_id == f"memory:{invalid.id}" for s in bundle.selected
        ),
        "budget_adherence": bundle.estimated_tokens <= 16000,
    }
    assert result["expected_memory_recall"] == 1 and not unsafe and leaks == 0
    await store.close()
    return result


async def main() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="ei-context-eval-") as directory:
        root = Path(directory)
        return {
            "methodology": (
                "Synthetic only; 30 warm searches after reopening each DB. "
                "tracemalloc enabled during timing; SQLite native allocations excluded."
            ),
            "stores": [
                await measure_store(root / f"size-{size}.sqlite", size) for size in (100, 1000)
            ],
            "continuity_quality": await quality(root / "quality.sqlite"),
        }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(main()), indent=2))
