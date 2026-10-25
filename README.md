# EI Context

An independently installable Python 3.11+ library for scoped evidence retrieval,
persistent work memory and cited context assembly. Works offline with SQLite,
Pydantic and synthetic providers. No EI Core/Server dependency, model keys, agent
loop, dashboard, workspace, hosted service or package publication.

## Install and validate

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
python -m ruff check .
python -m mypy
python -m build
python examples/offline_resume.py
python examples/adapters.py
python scripts/evaluate.py
python scripts/evaluate_memory.py
```

Installing dependencies may need a package index; running the installed library,
tests and synthetic examples needs no network or credentials. The continuity demo
actively rejects outbound network access. No public license has been selected and
nothing is published automatically.

## Retrieve context directly

```python
import asyncio
from ei_context import AccessScope, ContextEngine, ContextRequest
from ei_context.providers import FixtureProvider


async def main():
    engine = ContextEngine([FixtureProvider()])
    bundle = await engine.prepare(
        ContextRequest(
            query="Which route supports ledger calculation?",
            scope=AccessScope(tenant_id="demo", actor_id="alice"),
            token_budget=4000,
        )
    )
    print(bundle.rendered_context)
    print(bundle.warnings)


asyncio.run(main())
```

Every selected excerpt includes a stable evidence ID, source snapshot/version,
citation, selection reason and caveats. JSON rendering frames all retrieved text
and metadata as untrusted data. The complete rendering fits the declared estimate
and item budget. The default counter counts UTF-8 bytes conservatively; inject a
model-specific `TokenCounter` for exact target-model accounting. Whole items may
be omitted; citations are never clipped. Budgets too small for framing raise
`BudgetExceeded`.

## Persist explicitly approved work memory

```python
from datetime import datetime, UTC
from ei_context import (
    AccessScope,
    ApprovalEvidence,
    ContextEngine,
    ContextRequest,
    MemoryCandidate,
    MemoryKind,
    MemoryManager,
    SourceRef,
    SQLiteMemoryStore,
    WorkstreamRef,
)
from ei_context.providers.memory import MemoryProvider


async def remember_and_resume():
    scope = AccessScope(tenant_id="demo", actor_id="alice")
    work = WorkstreamRef(external_id="DEMO-42")
    now = datetime.now(UTC)
    store = SQLiteMemoryStore("work.sqlite")
    manager = MemoryManager(store)
    await manager.commit(
        MemoryCandidate(
            kind=MemoryKind.DECISION,
            content="Choose NewRoute; LegacyRoute failed the synthetic balance test.",
            source_refs=(
                SourceRef(
                    provider="tests", source_id="balance-test", version="1", retrieved_at=now
                ),
            ),
            workstream=work,
        ),
        scope=scope,
        approval=ApprovalEvidence(
            actor_id="alice",
            method="user_confirmed",
            reference="approval:demo-42",
            approved_at=now,
        ),
    )
    await store.close()

    fresh_store = SQLiteMemoryStore("work.sqlite")
    engine = ContextEngine([MemoryProvider(fresh_store)], memory_manager=MemoryManager(fresh_store))
    bundle = await engine.prepare(
        ContextRequest(
            query="Continue DEMO-42 ledger work",
            scope=scope,
            workstream=work,
        )
    )
    await engine.close()
    return bundle
```

Only the SQLite path connects these sessions. Without the technical provider the
bundle warns that supporting evidence was not independently retrieved. Approval
is a host attestation about the statement and provenance, not proof of technical
truth or a hidden URI fetch. A user-confirmed claim remains labelled as such.
See the asserted [two-process demo](examples/offline_resume.py) for decision,
failed attempt, open question, changed source version and access-isolation checks.

`store.get/history/list/export` require a scope. Search and default listing return
active, unexpired memories; direct lookup, history and diagnostic export preserve
status/TTL for inspection. `update` requires `MemoryUpdate`, approval and an
expected revision. Corrections keep history; `supersede` links a matching approved
replacement; `invalidate` records a reason; `delete` removes all record revisions
and source-index rows. Exact duplicate proposals are idempotent. Conflicting active
decisions coexist and produce review warnings; no automatic truth resolution.

## Identity and security contract

The trusted host authenticates actors and constructs `AccessScope`. Actor strings
are not a production login system. Private memory belongs exclusively to its owner
within its tenant and namespace. Principal strings supplied in a request confer
no rights. Team access requires an injected host `GrantResolver`; team creation
also requires separate publication approval. Org publication is disabled.
Source allowlists restrict every supporting reference, including historical
revisions. Memory-derived evidence uses the original source IDs for these filters;
its synthetic memory ID is not a substitute for provenance. Sensitive-classified
memory requires `allow_sensitive=True`; the caller classifies sensitivity, as no
classifier can guarantee that arbitrary secrets have been found.

Providers must authorise against their native source before lexical, embedding or
model processing. The engine checks again before custom ranking. SQLite enforces
ACLs before bodies enter its per-query FTS5 index; deterministic lexical fallback
works without FTS5. No global text index, result cache, default LLM or logging of
source contents. `refresh` recomputes using current grants. Earlier exported
bundles remain caller-owned snapshots and cannot be remotely revoked.

Protect SQLite files, exports and backups with host permissions. Local transactions
are synchronous behind an async protocol, with a 100ms busy timeout; shared or
high-throughput deployments should provide another `MemoryStore`. Providers must
be async and cooperate with cancellation. Host timeouts cannot interrupt blocking
third-party code. See [SECURITY.md](SECURITY.md).

## Events and future integrations

`observe`/`distill` stage private pending `MemoryCandidate`s from explicit observable
`ContextEvent`s. Nothing is durable until `commit_memory` receives explicit approval.
Raw tool text does not become memory under the default `ExplicitOnlyExtractor`.
Optional `MemoryExtractor`s receive pre-authorised events and cannot publish shared
knowledge. No transcript scraping, scheduling, checkpoints or model/tool loop.

Use [the adapter guide](docs/ADAPTER_GUIDE.md) and [runnable synthetic shim](examples/adapters.py)
for future EI Core providers and EI Server lifecycle calls. These are independent
protocols; actual EI package APIs remain unavailable and are not assumed.

## Implementation references

- [Worker handoff](docs/WORKER_HANDOFF.md), [design](docs/DESIGN.md), [contracts](docs/CONTRACTS.md), [plan](docs/IMPLEMENTATION_PLAN.md)
- [Acceptance and release checklist](docs/RELEASE_CHECKLIST.md)
- [Measured synthetic evaluation and limitations](docs/EVALUATION.md)
- [Implementation assumptions](docs/assumptions.md), [ADRs](docs/adr/), [retained DX backlog](docs/DX_BACKLOG.md)
- [Changelog](CHANGELOG.md)

Five focused PRs are stacked in implementation order. Merge bottom-up, retargeting
the next PR to `main` after each merge. No merge or deployment happens automatically.
