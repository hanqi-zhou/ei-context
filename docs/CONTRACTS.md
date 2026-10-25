# EI Context — Proposed Python Contracts (v0.1)

**Status:** implementation target, not existing code. All examples are illustrative. Keep contract churn explicit in CHANGELOG/ADRs.

## 1. Public import surface

```python
from ei_context import (
    AccessScope,
    WorkstreamRef,
    ContextRequest,
    ContextBundle,
    Evidence,
    SourceRef,
    MemoryRecord,
    MemoryCandidate,
    ContextEngine,
    MemoryManager,
)
from ei_context.protocols import (
    ContextProvider,
    MemoryStore,
    TokenCounter,
    MemoryExtractor,
)
```

Target install: `pip install ei-context` once published; `pip install -e ".[dev]"` for local development. Do not publish to PyPI automatically.

## 2. Types (proposed shape)

```python
from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field


class MemoryState(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"


class MemoryKind(StrEnum):
    DECISION = "decision"
    FINDING = "finding"
    ATTEMPT = "attempted_approach"
    OPEN_QUESTION = "open_question"
    TASK_SUMMARY = "task_summary"


class Visibility(StrEnum):
    PRIVATE = "private"
    TEAM = "team"  # requires verified grants, not just a string
    ORG = "org"  # disabled by default


class AccessScope(BaseModel):
    tenant_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    # Authenticated grants are supplied by a trusted host, not end users or LLMs:
    principals: frozenset[str] = frozenset()
    allowed_source_ids: frozenset[str] | None = None


class WorkstreamRef(BaseModel):
    external_id: str
    system: str | None = None  # e.g. ticketing system, no vendor dependency


class SourceRef(BaseModel):
    provider: str
    source_id: str
    uri: str | None = None
    version: str | None = None
    retrieved_at: datetime
    modified_at: datetime | None = None


class Evidence(BaseModel):
    id: str
    text: str
    source: SourceRef
    tenant_id: str
    access_principals: frozenset[str]
    trust_label: str = "unverified"
    metadata: dict[str, str] = Field(default_factory=dict)


class ContextRequest(BaseModel):
    query: str = Field(min_length=1)
    scope: AccessScope
    workstream: WorkstreamRef | None = None
    token_budget: int = Field(default=4000, gt=0)
    max_items: int = Field(default=20, gt=0)
    provider_ids: list[str] | None = None


class SelectedContext(BaseModel):
    evidence_id: str
    excerpt: str
    source: SourceRef
    reason: str
    estimated_tokens: int


class ContextBundle(BaseModel):
    schema_version: str = "1"
    rendered_context: str
    selected: list[SelectedContext]
    estimated_tokens: int
    warnings: list[str] = Field(default_factory=list)
    omitted_count: int = 0
```

Implementation may refine the exact fields but must preserve: stable IDs, traceable provenance, strict scope, timestamps, token/item budgets, and versioned serialisation. Strictly define null vs absent for unknown source validity. Default deny access when grants cannot be evaluated.

MemoryRecord must include: `id`, `tenant_id`, `actor_id`, `visibility`, `workstream`, `kind`, `content`, `source_refs`, `status`, `revision`, `created_at`, `updated_at`, `valid_until`, `verified_by` or confirmation provenance; avoid hard-coding workflow roles. MemoryCandidate should include proposed content, kind, source refs, source event, uncertainty and status pending review. All records must be serialisable, with no raw model objects in persistence.

## 3. Provider and storage protocols

```python
from typing import Protocol, Sequence


class ContextProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    async def search(
        self,
        query: str,
        *,
        scope: AccessScope,
        workstream: WorkstreamRef | None,
        limit: int,
    ) -> Sequence[Evidence]: ...


class MemoryStore(Protocol):
    async def create(self, candidate: MemoryCandidate, *, scope: AccessScope) -> MemoryRecord: ...

    async def get(self, memory_id: str, *, scope: AccessScope) -> MemoryRecord | None: ...

    async def search(
        self, query: str, *, scope: AccessScope, workstream: WorkstreamRef | None, limit: int
    ) -> Sequence[MemoryRecord]: ...

    async def update(
        self,
        memory_id: str,
        *,
        expected_revision: int,
        scope: AccessScope,
        **changes: object,
    ) -> MemoryRecord: ...

    async def invalidate(
        self,
        memory_id: str,
        *,
        scope: AccessScope,
        expected_revision: int,
        reason: str,
    ) -> MemoryRecord: ...

    async def delete(
        self,
        memory_id: str,
        *,
        scope: AccessScope,
    ) -> None: ...
```

Specify real concrete types instead of `**changes` in implementation; use explicit update DTOs. Need list/export operations, plus supersede where appropriate. Raise typed errors: `AccessDenied`, `InvalidScope`, `RevisionConflict`, `BudgetExceeded`, `ProviderUnavailable`. Providers are not trusted just because they implement a protocol: apply engine-side policy checks too.

Important authorization invariant: within tenant, private memory is accessible only to the owning authenticated principal. Team/org visibility requires a trusted, verified grant. A client cannot gain broader access by adding strings to a request.

## 4. Memory manager

```python
class MemoryManager:
    async def propose_from_event(
        self, event: "ContextEvent", *, scope: AccessScope
    ) -> list[MemoryCandidate]: ...

    async def commit(
        self, candidate: MemoryCandidate, *,
        scope: AccessScope, approval: "ApprovalEvidence"
    ) -> MemoryRecord: ...

    async def search(
        self, query: str, *, scope: AccessScope,
        workstream: WorkstreamRef | None = None,
    ) -> list[MemoryRecord]: ...

    async def supersede(...): ...
    async def invalidate(...): ...
    async def delete(...): ...
```

Default extractor is **explicit-only**, accepting caller-supplied confirmed decision/finding events with evidence references. Optional model-assisted extraction must be behind `MemoryExtractor`, off by default, and produce candidates, not authoritative team memories. Distinguish a developer's statement from verified technical fact.

## 5. Engine and optional lifecycle

```python
engine = ContextEngine(
    providers=[mock_api_provider, mock_docs_provider, memory_provider],
    token_counter=approximate_token_counter,
    ranker=hybrid_lexical_ranker,
)

bundle = await engine.prepare(
    ContextRequest(
        query="Continue investigating the synthetic ledger API",
        scope=scope,
        workstream=WorkstreamRef(external_id="DEMO-42"),
        token_budget=2400,
    )
)
print(bundle.rendered_context)
```

`prepare` is deterministic for frozen providers, clock and ranker. Provide `refresh` to recompute when sources change. `observe` and `distill` may be introduced later, and must only process observable events. No implicit call to the LLM or tool loop, and no cross-agent session scraping.

A context bundle is **data**, not executable agent instructions. Provide both structured fields and a readable rendering with source markers. A renderer must frame retrieved text as untrusted quoted evidence, never system messages.

## 6. Source adapter contract

EI Core later supplies wrappers only:

```python
class EICoreApiProvider:
    provider_id = "ei-core-api"

    def __init__(self, api_search_client):
        self.client = api_search_client

    async def search(self, query, *, scope, workstream, limit):
        # Authenticate/authorise against native source first.
        # Translate source hits into Evidence + SourceRef.
        # Do not import EI Server or include tool-loop logic here.
        ...
```

Because other EI source isn't available on this machine, implement `FixtureProvider` and `InMemoryProvider` first. Do NOT invent concrete EI Core module paths.

## 7. Security and privacy tests (mandatory)

1. No `scope` -> validation error before querying any provider.
2. Actor A cannot retrieve/update/delete actor B's private memory, even if exact ID is known.
3. Tenant A cannot retrieve tenant B content under lexical, cache or direct-ID lookup.
4. Unverified group names from the caller do not imply team access.
5. A malicious Evidence excerpt saying “ignore previous instructions” is carried as source content, not executed or elevated.
6. Scope filtering must occur before information is sent to any optional external ranker or embedding service.
7. Deletion updates the primary store, search index and caches; deleted content never appears in exports.
8. Invalidated/superseded memories are not presented as current decisions without caveats.
9. There are no source contents, tokens, secrets or unredacted transcripts in default logs.

## 8. Package and test targets

```text
pyproject.toml
src/ei_context/
  __init__.py
  models.py
  errors.py
  protocols.py
  engine.py
  retrieval/
    ranking.py
    assembler.py
    dedup.py
  memory/
    manager.py
    sqlite.py
  providers/
    fixtures.py
    memory.py
  lifecycle/
    events.py
tests/
  unit/
  integration/
  security/
examples/
  offline_resume.py
```

Minimum support: Python 3.11+, Ruff, pytest/pytest-asyncio, mypy or pyright, Pydantic 2, SQLite. Prefer no network-bound install-time side effects. CLI/API/MCP are optional and should not block library v0.1.

## 9. Integration test to prove value

Session 1: in a synthetic workstream, record an attempted API route, failure evidence, verified alternative and remaining question. Close and reconstruct a **new** ContextEngine instance with the same persistent SQLite store, but no previous chat transcript. Session 2: ask to continue. Expected: correct alternative, reason, source attribution and unresolved question; **not** stale failed choice. Repeat with another actor and ensure private memory is invisible.

See [DESIGN.md](DESIGN.md) for non-functional requirements and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for milestones.

