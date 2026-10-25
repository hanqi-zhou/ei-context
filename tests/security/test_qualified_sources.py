"""Provider collisions are rejected before retrieval, on every storage path."""

import json
import sqlite3
from datetime import timedelta

import pytest
from pydantic import ValidationError

from ei_context import (
    AccessPolicy,
    AccessScope,
    ContextEngine,
    ContextRequest,
    Evidence,
    MemoryUpdate,
    SourceIdentity,
    SQLiteMemoryStore,
    Visibility,
)
from ei_context.errors import AccessDenied, InvalidScope
from ei_context.providers import InMemoryProvider
from ei_context.providers.memory import MemoryProvider


async def test_same_bare_id_cannot_cross_provider_boundaries(
    tmp_path, scope, ref, candidate, approval, now
):
    a = ref.model_copy(update={"provider": "A", "source_id": "42"})
    b = ref.model_copy(update={"provider": "B", "source_id": "42"})
    narrow = scope.model_copy(update={"allowed_sources": frozenset({a.identity})})
    store = SQLiteMemoryStore(tmp_path / "qualified.sqlite", clock=lambda: now)
    permitted = await store.create(
        candidate.model_copy(update={"source_refs": (a,)}), scope=scope, approval=approval
    )
    denied = await store.create(
        candidate.model_copy(update={"source_refs": (b,)}), scope=scope, approval=approval
    )
    mixed = await store.create(
        candidate.model_copy(update={"source_refs": (a, b)}), scope=scope, approval=approval
    )
    for provider, source in (("A", a), ("B", b)):
        e = Evidence(
            id=provider,
            text="ledger",
            source=source,
            tenant_id="demo",
            access_principals={"actor:alice"},
        )
        local = InMemoryProvider(provider, [e])
        results = await local.search("ledger", scope=narrow, workstream=None, limit=5)
        assert bool(results) == (provider == "A")
        assert bool(await local.list(scope=narrow)) == (provider == "A")
        assert bool(await local.get(provider, scope=narrow)) == (provider == "A")
    for r in (denied, mixed):
        assert await store.get(r.id, scope=narrow) is None
        assert await store.history(r.id, scope=narrow) == ()
        for operation in (
            store.update(
                r.id,
                MemoryUpdate(content="attack", source_refs=(a,)),
                expected_revision=1,
                scope=narrow,
                approval=approval,
            ),
            store.delete(r.id, scope=narrow),
            store.invalidate(r.id, scope=narrow, expected_revision=1, reason="attack"),
        ):
            with pytest.raises(AccessDenied):
                await operation
    assert [r.id for r in await store.list(scope=narrow)] == [permitted.id]
    assert [
        r.id for r in await store.search("NewRoute", scope=narrow, workstream=None, limit=10)
    ] == [permitted.id]
    assert [r["id"] for r in json.loads(await store.export(scope=narrow))["records"]] == [
        permitted.id
    ]
    bundle = await ContextEngine([MemoryProvider(store)]).prepare(
        ContextRequest(query="ledger", scope=narrow)
    )
    assert [s.evidence_id for s in bundle.selected] == [f"memory:{permitted.id}"]
    await store.close()


async def test_primary_and_all_supporting_pairs_are_checked(scope, ref):
    a = ref.model_copy(update={"provider": "A", "source_id": "42"})
    b = ref.model_copy(update={"provider": "B", "source_id": "42"})
    scope = scope.model_copy(update={"allowed_sources": frozenset({a.identity})})
    for primary, supporting in ((b, (a,)), (a, (b,))):
        item = Evidence(
            id="forged",
            text="ledger secret",
            source=primary,
            source_refs=supporting,
            tenant_id="demo",
            access_principals={"actor:alice"},
        )
        assert not AccessPolicy().evidence_allowed(item, scope)
    # Delimiters in IDs cannot alias a different pair.
    assert SourceIdentity(provider="a:b", source_id="c") != SourceIdentity(
        provider="a", source_id="b:c"
    )


def test_legacy_restrictions_fail_closed_and_scope_v2_roundtrip(scope):
    with pytest.raises(ValidationError):
        AccessScope(tenant_id="demo", actor_id="alice", allowed_source_ids={"42"})
    forged = scope.model_copy(update={"allowed_source_ids": frozenset({"42"})})
    with pytest.raises(InvalidScope):
        AccessPolicy().validate_scope(forged)
    restricted = scope.model_copy(
        update={"allowed_sources": frozenset({SourceIdentity(provider="A", source_id="42")})}
    )
    assert AccessScope.model_validate_json(restricted.model_dump_json()) == restricted
    assert restricted.schema_version == "2"


async def test_v1_migration_uses_revision_snapshots(tmp_path, scope, candidate, approval, ref, now):
    path = tmp_path / "legacy.sqlite"
    b = ref.model_copy(update={"provider": "B", "source_id": "42"})
    a = ref.model_copy(update={"provider": "A", "source_id": "42"})
    store = SQLiteMemoryStore(path, clock=lambda: now)
    record = await store.create(
        candidate.model_copy(update={"source_refs": (b,)}), scope=scope, approval=approval
    )
    await store.update(
        record.id,
        MemoryUpdate(content="ledger corrected", source_refs=(a,)),
        scope=scope,
        expected_revision=1,
        approval=approval,
    )
    await store.close()
    # Construct the actual legacy schema, whose bare index cannot distinguish A/B.
    with sqlite3.connect(path) as db:
        db.execute("DROP INDEX source_lookup")
        db.execute("ALTER TABLE source_index RENAME TO qualified_index")
        db.execute(
            "CREATE TABLE source_index(memory_id TEXT NOT NULL REFERENCES memories(id) "
            "ON DELETE CASCADE, revision INTEGER NOT NULL, source_id TEXT NOT NULL, "
            "PRIMARY KEY(memory_id,revision,source_id))"
        )
        db.execute(
            "INSERT OR IGNORE INTO source_index "
            "SELECT memory_id,revision,source_id FROM qualified_index"
        )
        db.execute("DROP TABLE qualified_index")
        db.execute("CREATE INDEX source_lookup ON source_index(source_id,memory_id,revision)")
        db.execute("PRAGMA user_version=1")
    migrated = SQLiteMemoryStore(path, clock=lambda: now)
    narrow = scope.model_copy(update={"allowed_sources": frozenset({a.identity})})
    assert (await migrated.get(record.id, scope=narrow)).revision == 2
    assert [r.revision for r in await migrated.history(record.id, scope=narrow)] == [2]
    await migrated.close()
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert db.execute(
            "SELECT provider,revision FROM source_index ORDER BY revision"
        ).fetchall() == [("B", 1), ("A", 2)]
    reopened = SQLiteMemoryStore(path, clock=lambda: now)
    await reopened.delete(record.id, scope=narrow)
    assert json.loads(await reopened.export(scope=narrow))["records"] == []
    await reopened.close()


async def test_freshness_change_is_not_an_old_duplicate(
    tmp_path, scope, candidate, approval, ref, now
):
    store = SQLiteMemoryStore(tmp_path / "fresh.sqlite", clock=lambda: now)
    expired = ref.model_copy(update={"valid_until": now - timedelta(days=1)})
    first = await store.create(
        candidate.model_copy(update={"source_refs": (expired,)}), scope=scope, approval=approval
    )
    fresh = expired.model_copy(update={"valid_until": now + timedelta(days=1)})
    second = await store.create(
        candidate.model_copy(update={"source_refs": (fresh,)}), scope=scope, approval=approval
    )
    assert first.id != second.id and second.source_refs[0].valid_until > now
    later_read = fresh.model_copy(update={"retrieved_at": now + timedelta(seconds=1)})
    assert (
        await store.create(
            candidate.model_copy(update={"source_refs": (later_read,)}),
            scope=scope,
            approval=approval,
        )
    ).id == second.id
    await store.close()


def test_actor_principal_is_not_a_team(candidate):
    with pytest.raises(ValidationError, match="named team"):
        type(candidate).model_validate(
            {
                **candidate.model_dump(),
                "visibility": Visibility.TEAM,
                "team_principal": "actor:alice",
            }
        )
