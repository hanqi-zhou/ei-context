import json

import pytest

from ei_context import AccessPolicy, AccessScope, MemoryUpdate, SQLiteMemoryStore, Visibility
from ei_context.errors import AccessDenied


async def test_private_access_all_paths(tmp_path, scope, candidate, approval, now):
    store = SQLiteMemoryStore(tmp_path / "acl.sqlite", clock=lambda: now)
    r = await store.create(candidate, scope=scope, approval=approval)
    for denied in [
        AccessScope(tenant_id="demo", actor_id="bob", principals={"actor:alice"}),
        AccessScope(tenant_id="other", actor_id="alice"),
        scope.model_copy(update={"allowed_source_ids": frozenset()}),
        scope.model_copy(update={"allowed_namespaces": frozenset({"other"})}),
    ]:
        assert await store.get(r.id, scope=denied) is None
        assert await store.list(scope=denied, include_inactive=True) == ()
        assert await store.search("NewRoute", scope=denied, workstream=None, limit=10) == ()
        assert await store.history(r.id, scope=denied) == ()
        assert json.loads(await store.export(scope=denied))["records"] == []
        with pytest.raises(AccessDenied):
            await store.update(
                r.id,
                MemoryUpdate(content="stolen", source_refs=candidate.source_refs),
                expected_revision=1,
                scope=denied,
                approval=approval,
            )
        with pytest.raises(AccessDenied):
            await store.invalidate(r.id, expected_revision=1, scope=denied, reason="attack")
        with pytest.raises(AccessDenied):
            await store.supersede(r.id, r.id, expected_revision=1, scope=denied)
        with pytest.raises(AccessDenied):
            await store.delete(r.id, scope=denied)
    await store.close()


async def test_team_requires_verified_grants_and_publication(
    tmp_path, scope, candidate, approval, now
):
    policy = AccessPolicy(
        lambda tenant, actor: frozenset({"team:dev"}) if tenant == "demo" else frozenset()
    )
    store = SQLiteMemoryStore(tmp_path / "team.sqlite", policy=policy, clock=lambda: now)
    team = candidate.model_copy(
        update={"visibility": Visibility.TEAM, "team_principal": "team:dev"}
    )
    with pytest.raises(AccessDenied):
        await store.create(team, scope=scope, approval=approval)
    r = await store.create(
        team, scope=scope, approval=approval.model_copy(update={"allow_publication": True})
    )
    bob = AccessScope(tenant_id="demo", actor_id="bob")
    assert await store.get(r.id, scope=bob) is not None
    with pytest.raises(AccessDenied):
        await store.delete(r.id, scope=bob)
    with pytest.raises(AccessDenied):
        await store.create(
            candidate.model_copy(update={"visibility": Visibility.ORG}),
            scope=scope,
            approval=approval,
        )
    await store.close()
    denied_store = SQLiteMemoryStore(tmp_path / "team.sqlite", clock=lambda: now)
    assert (
        await denied_store.get(
            r.id, scope=scope.model_copy(update={"principals": frozenset({"team:dev"})})
        )
        is None
    )
    await denied_store.close()


async def test_old_revision_source_restrictions(tmp_path, scope, candidate, approval, now, ref):
    store = SQLiteMemoryStore(tmp_path / "history.sqlite", clock=lambda: now)
    r = await store.create(candidate, scope=scope, approval=approval)
    new_ref = ref.model_copy(update={"source_id": "public-ref"})
    await store.update(
        r.id,
        MemoryUpdate(content="public correction", source_refs=(new_ref,)),
        expected_revision=1,
        scope=scope,
        approval=approval,
    )
    narrow = scope.model_copy(update={"allowed_source_ids": frozenset({"public-ref"})})
    assert [h.revision for h in await store.history(r.id, scope=narrow)] == [2]
    await store.close()
