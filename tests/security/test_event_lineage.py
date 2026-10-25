import pytest

from ei_context import ContextEvent, MemoryManager, SQLiteMemoryStore
from ei_context.errors import InvalidMemory


async def test_extractor_cannot_fabricate_or_rewrite_event_evidence(
    tmp_path, scope, candidate, approval, ref, now
):
    store = SQLiteMemoryStore(tmp_path / "lineage.sqlite", clock=lambda: now)
    event = ContextEvent(
        id="event:observed",
        kind="tool_result",
        tenant_id="demo",
        actor_id="alice",
        occurred_at=now,
        source_refs=(ref,),
    )

    class Extractor:
        def __init__(self, source):
            self.source = source

        async def extract(self, event, *, scope):
            return [candidate.model_copy(update={"source_refs": (self.source,)})]

    for source in [
        ref.model_copy(update={"provider": "fabricated"}),
        ref.model_copy(update={"source_id": "new"}),
        ref.model_copy(update={"version": "future"}),
        ref.model_copy(update={"uri": "https://example.invalid/fake"}),
    ]:
        manager = MemoryManager(store, extractor=Extractor(source))
        with pytest.raises(InvalidMemory, match="provenance"):
            await manager.propose_from_event(event, scope=scope)
    assert await store.list(scope=scope) == ()
    second = ref.model_copy(update={"source_id": "second"})
    valid_event = event.model_copy(update={"source_refs": (ref, second), "proposal": candidate})
    manager = MemoryManager(store)
    proposals = await manager.propose_from_event(valid_event, scope=scope)
    saved = await manager.commit(proposals[0], scope=scope, approval=approval)
    assert saved.source_event == event.id and saved.source_refs == (ref,)
    await store.close()


async def test_nested_fabricated_proposal_never_reaches_extractor(
    tmp_path, scope, candidate, ref, now
):
    store = SQLiteMemoryStore(tmp_path / "before.sqlite")
    calls = []

    class Spy:
        async def extract(self, event, *, scope):
            calls.append(event.id)
            return []

    bad = candidate.model_copy(
        update={"source_refs": (ref.model_copy(update={"version": "forged"}),)}
    )
    event = ContextEvent(
        id="event:bad",
        kind="tool_result",
        tenant_id="demo",
        actor_id="alice",
        occurred_at=now,
        source_refs=(ref,),
        proposal=bad,
    )
    with pytest.raises(InvalidMemory):
        await MemoryManager(store, extractor=Spy()).propose_from_event(event, scope=scope)
    assert calls == []
    await store.close()
