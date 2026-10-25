import pytest
from pydantic import ValidationError

from ei_context import AccessPolicy, AccessScope, ContextRequest, Evidence
from ei_context.errors import InvalidScope
from ei_context.providers import FixtureProvider, InMemoryProvider


@pytest.mark.parametrize("provider_class", [FixtureProvider, lambda: InMemoryProvider("empty", [])])
async def test_missing_scope(provider_class):
    provider = provider_class()
    with pytest.raises(InvalidScope):
        await provider.search("ledger", scope=None, workstream=None, limit=5)


async def test_all_paths_enforce_actor_tenant_source_namespace(scope):
    provider = FixtureProvider()
    assert len(await provider.search("ledger", scope=scope, workstream=None, limit=5)) == 1
    for blocked in [
        AccessScope(tenant_id="demo", actor_id="bob", principals=frozenset({"actor:alice"})),
        AccessScope(tenant_id="other", actor_id="alice"),
        scope.model_copy(update={"allowed_sources": frozenset()}),
        scope.model_copy(update={"allowed_namespaces": frozenset({"elsewhere"})}),
    ]:
        assert await provider.search("ledger", scope=blocked, workstream=None, limit=5) == ()
        assert await provider.list(scope=blocked) == ()
        assert await provider.get("ledger-doc-v2", scope=blocked) is None


async def test_team_hints_are_not_grants(scope, ref):
    e = Evidence(
        id="team-e", text="ledger", source=ref, tenant_id="demo", access_principals={"team:dev"}
    )
    hinted = scope.model_copy(update={"principals": frozenset({"team:dev"})})
    assert await InMemoryProvider("team", [e]).list(scope=hinted) == ()
    policy = AccessPolicy(
        lambda tenant, actor: frozenset({"team:dev"}) if actor == "alice" else frozenset()
    )
    assert len(await InMemoryProvider("team", [e], policy=policy).list(scope=scope)) == 1


def test_models_fail_closed(scope):
    with pytest.raises(ValidationError):
        ContextRequest(query="ledger")
    with pytest.raises(ValidationError):
        AccessScope(tenant_id=" ", actor_id="alice")
    forged = AccessScope.model_construct(tenant_id="", actor_id="alice")
    with pytest.raises(InvalidScope):
        AccessPolicy().validate_scope(forged)
    assert (
        ContextRequest.model_validate_json(
            ContextRequest(query="ledger", scope=scope).model_dump_json()
        ).scope
        == scope
    )
