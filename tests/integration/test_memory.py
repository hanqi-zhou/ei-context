import asyncio
import json
import sqlite3
import sys
from datetime import timedelta

import pytest

from ei_context import MemoryUpdate, SQLiteMemoryStore, WorkstreamRef
from ei_context.errors import InvalidMemory, RevisionConflict, StoreUnavailable


@pytest.mark.parametrize("use_fts", [True, False])
async def test_persistence_revision_search_deletion(
    tmp_path, scope, candidate, approval, now, use_fts
):
    path = tmp_path / "memory.sqlite"
    store = SQLiteMemoryStore(path, clock=lambda: now, use_fts=use_fts)
    record = await store.create(candidate, scope=scope, approval=approval)
    assert (await store.create(candidate, scope=scope, approval=approval)).id == record.id
    await store.close()
    store = SQLiteMemoryStore(path, clock=lambda: now, use_fts=use_fts)
    assert (await store.search("NewRoute", scope=scope, workstream=None, limit=10))[
        0
    ].id == record.id
    changed = await store.update(
        record.id,
        MemoryUpdate(content="NewRoute corrected.", source_refs=candidate.source_refs),
        expected_revision=1,
        scope=scope,
        approval=approval,
    )
    with pytest.raises(RevisionConflict):
        await store.update(
            record.id,
            MemoryUpdate(content="Race", source_refs=candidate.source_refs),
            expected_revision=1,
            scope=scope,
            approval=approval,
        )
    assert len(await store.history(record.id, scope=scope)) == 2
    invalid = await store.invalidate(
        record.id, scope=scope, expected_revision=2, reason="source changed"
    )
    assert invalid.status.value == "invalidated"
    assert await store.search("NewRoute", scope=scope, workstream=None, limit=10) == ()
    assert changed.revision == 2
    await store.delete(record.id, scope=scope)
    assert await store.get(record.id, scope=scope) is None
    assert await store.history(record.id, scope=scope) == ()
    assert json.loads(await store.export(scope=scope))["records"] == []
    await store.close()
    with sqlite3.connect(path) as db:
        for table in ("memories", "revisions", "source_index"):
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    with pytest.raises(StoreUnavailable):
        await store.list(scope=scope)


async def test_fresh_process(tmp_path, scope, candidate, approval, now):
    path = tmp_path / "fresh.sqlite"
    store = SQLiteMemoryStore(path, clock=lambda: now)
    record = await store.create(candidate, scope=scope, approval=approval)
    await store.close()
    code = """
import asyncio,sys
from ei_context import AccessScope,SQLiteMemoryStore
async def read():
    store=SQLiteMemoryStore(sys.argv[1])
    scope=AccessScope(tenant_id='demo',actor_id='alice')
    rows=await store.search('NewRoute',scope=scope,workstream=None,limit=5)
    assert len(rows)==1 and rows[0].id==sys.argv[2]
    await store.close()
asyncio.run(read())
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        code,
        str(path),
        record.id,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    assert process.returncode == 0, stderr.decode()


async def test_ttl_supersession_and_concurrent_writers(tmp_path, scope, candidate, approval, now):
    clock = [now]
    store = SQLiteMemoryStore(tmp_path / "ttl.sqlite", clock=lambda: clock[0])
    expiring = candidate.model_copy(
        update={
            "valid_until": now + timedelta(seconds=1),
            "workstream": WorkstreamRef(external_id="W"),
        }
    )
    old = await store.create(expiring, scope=scope, approval=approval)
    replacement = await store.create(
        expiring.model_copy(update={"content": "Choose safer NewRoute"}),
        scope=scope,
        approval=approval,
    )
    await store.supersede(old.id, replacement.id, expected_revision=1, scope=scope)
    assert [r.id for r in await store.list(scope=scope)] == [replacement.id]
    assert len(await store.list(scope=scope, include_inactive=True)) == 2
    clock[0] += timedelta(seconds=2)
    assert await store.list(scope=scope) == ()
    with pytest.raises(InvalidMemory):
        await store.create(expiring, scope=scope, approval=approval)
    await store.close()
    a = SQLiteMemoryStore(tmp_path / "race.sqlite", clock=lambda: now)
    b = SQLiteMemoryStore(tmp_path / "race.sqlite", clock=lambda: now)
    r = await a.create(candidate, scope=scope, approval=approval)

    async def edit(s):
        return await s.update(
            r.id,
            MemoryUpdate(content="race result", source_refs=candidate.source_refs),
            expected_revision=1,
            scope=scope,
            approval=approval,
        )

    results = await asyncio.gather(edit(a), edit(b), return_exceptions=True)
    assert sum(isinstance(result, RevisionConflict) for result in results) == 1
    await a.close()
    await b.close()


async def test_lock_contention_and_future_schema(tmp_path, scope, candidate, approval, now):
    path = tmp_path / "locked.sqlite"
    store = SQLiteMemoryStore(path, clock=lambda: now)
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(StoreUnavailable):
            await store.create(candidate, scope=scope, approval=approval)
        db.rollback()
    await store.close()
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=999")
    with pytest.raises(StoreUnavailable):
        SQLiteMemoryStore(path)


async def test_transaction_rollback_removes_partial_record(
    tmp_path, scope, candidate, approval, now
):
    path = tmp_path / "rollback.sqlite"
    store = SQLiteMemoryStore(path, clock=lambda: now)
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TRIGGER fail_source BEFORE INSERT ON source_index "
            "BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END"
        )
    with pytest.raises(StoreUnavailable):
        await store.create(candidate, scope=scope, approval=approval)
    assert await store.list(scope=scope, include_inactive=True) == ()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 0
        db.execute("DROP TRIGGER fail_source")
    assert await store.create(candidate, scope=scope, approval=approval)
    await store.close()
