import asyncio
import json
from datetime import timedelta

import pytest
from pydantic import ValidationError

from ei_context import ContextEngine, ContextRequest, Evidence
from ei_context.errors import BudgetExceeded
from ei_context.providers import InMemoryProvider
from ei_context.retrieval import ApproximateTokenCounter


def document(ref, **changes):
    return Evidence(
        id="doc",
        text="NewRoute ledger calculation",
        source=ref,
        tenant_id="demo",
        access_principals={"actor:alice"},
        trust_label="system_verified",
        **changes,
    )


async def test_determinism_dedup_citations_and_budgets(scope, ref, now):
    evidence = document(ref)
    provider = InMemoryProvider("docs", [evidence, evidence.model_copy(update={"id": "copy"})])
    engine = ContextEngine([provider], clock=lambda: now)
    request = ContextRequest(query="ledger NewRoute", scope=scope, token_budget=4000, max_items=1)
    first = await engine.prepare(request)
    assert first == await engine.prepare(request)
    assert len(first.selected) == 1
    assert first.omitted_count == 1
    selected = first.selected[0]
    assert selected.source == ref and selected.citation == "C1" and "lexical=" in selected.reason
    assert first.estimated_tokens == ApproximateTokenCounter().count(first.rendered_context)
    assert first.estimated_tokens <= request.token_budget
    payload = json.loads(first.rendered_context.split("\n", 1)[1])
    assert payload["evidence"][0]["source"]["source_id"] == ref.source_id
    for budget in (150, 300, 500, 900, 1500):
        bundle = await engine.prepare(request.model_copy(update={"token_budget": budget}))
        assert bundle.estimated_tokens <= budget
        assert all(s.source == ref for s in bundle.selected)
    with pytest.raises(BudgetExceeded):
        await engine.prepare(request.model_copy(update={"token_budget": 1}))


async def test_failure_timeout_and_concurrency(scope, ref, now):
    class Bad:
        provider_id = "bad"

        async def search(self, *args, **kwargs):
            raise RuntimeError("PRIVATE SECRET MUST NOT APPEAR")

    active = 0
    peak = 0

    class Slow:
        def __init__(self, index):
            self.provider_id = f"slow-{index}"

        async def search(self, *args, **kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(1)
            finally:
                active -= 1

    engine = ContextEngine(
        [InMemoryProvider("docs", [document(ref)]), Bad(), *[Slow(i) for i in range(5)]],
        clock=lambda: now,
        provider_timeout=0.01,
        max_concurrency=2,
    )
    result = await engine.prepare(ContextRequest(query="ledger", scope=scope))
    assert len(result.selected) == 1 and peak <= 2 and active == 0
    assert any("timeout" in w for w in result.warnings)
    assert any("unavailable" in w for w in result.warnings)
    assert "PRIVATE SECRET" not in str(result)


async def test_cancellation_propagates(scope):
    started = asyncio.Event()
    cancelled = asyncio.Event()

    class Wait:
        provider_id = "wait"

        async def search(self, *args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    task = asyncio.create_task(
        ContextEngine([Wait()]).prepare(ContextRequest(query="ledger", scope=scope))
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()


async def test_stale_conflicting_and_unknown_sources(scope, ref, now):
    old = document(ref.model_copy(update={"modified_at": now - timedelta(days=300)}))
    fresh = old.model_copy(
        update={
            "id": "new",
            "source": ref.model_copy(update={"version": "2", "modified_at": now}),
            "text": "NewRoute ledger calculation current",
        }
    )
    expired = fresh.model_copy(
        update={
            "id": "expired",
            "source": ref.model_copy(update={"source_id": "expired", "version": None}),
            "valid_until": now - timedelta(days=1),
        }
    )
    result = await ContextEngine(
        [InMemoryProvider("docs", [old, fresh, expired])], clock=lambda: now
    ).prepare(ContextRequest(query="ledger", scope=scope, token_budget=8000))
    assert result.selected[0].evidence_id == "new"
    assert any("older" in w for w in result.warnings)
    assert any("expired" in w for w in result.warnings)
    assert any("unknown" in w for w in result.warnings)


async def test_zero_results_and_missing_scope(scope):
    engine = ContextEngine([])
    bundle = await engine.prepare(ContextRequest(query="none", scope=scope))
    assert bundle.selected == () and bundle.omitted_count == 0
    with pytest.raises(ValidationError):
        await engine.prepare(ContextRequest.model_construct(query="test", scope=None))


async def test_provider_selection_exclusion_limits_and_expired_memory(scope, ref, now):
    from ei_context import MemoryKind, MemoryState

    docs = InMemoryProvider("docs", [document(ref)])
    request = ContextRequest(query="ledger", scope=scope, provider_ids=("missing",))
    empty = await ContextEngine([docs]).prepare(request)
    assert not empty.selected and "not registered" in empty.warnings[0]
    excluded = request.model_copy(
        update={"provider_ids": None, "excluded_source_ids": frozenset({ref.source_id})}
    )
    assert not (await ContextEngine([docs]).prepare(excluded)).selected
    old = document(ref).model_copy(
        update={
            "id": "inactive",
            "memory_kind": MemoryKind.DECISION,
            "memory_status": MemoryState.INVALIDATED,
        }
    )
    result = await ContextEngine(
        [InMemoryProvider("docs", [old, document(ref)])], clock=lambda: now
    ).prepare(ContextRequest(query="ledger", scope=scope, token_budget=8000))
    assert result.selected[0].evidence_id == "doc"
    assert any("inactive" in note for note in result.warnings)
