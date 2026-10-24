# EI Context — Implementation Plan

Version 0.1 | 2026-10-24 | Delivery mode: incremental PRs | Implementation by Worker

## Guiding principle

Prove cross-session recovery and evidence-backed context assembly **without relying on EI Core, EI Server, production data, a model provider, or a hosted vector DB**. Build the smallest independently useful library first; preserve interfaces for later integration.

## Implementation order

### Milestone 0 — Repository and delivery foundations (P0)

**Tasks**
- Initialise Python 3.11+ `src/` package, `pyproject.toml`, `py.typed`, Ruff, pytest + pytest-asyncio, static typing, GitHub Actions CI, `.gitignore`.
- Add `LICENSE` only if repository owner explicitly approves one. No automatic PyPI publishing.
- Make dependencies minimal and pin compatible bounds; Pydantic 2 and SQLite offline path.
- Read DESIGN/CONTRACTS/this plan; add a short `docs/assumptions.md` for choices not settled.

**Acceptance**
- `pip install -e ".[dev]"` succeeds cleanly.
- `pytest`, `ruff check .`, and chosen type checker pass in CI.
- Importing `ei_context` does not contact a network or require secrets.
- Examples and tests contain synthetic data only.

### Milestone 1 — Scope, provenance and provider interfaces (P0)

**Tasks**
- Build typed `AccessScope`, `WorkstreamRef`, `SourceRef`, `Evidence`, `ContextRequest`, `ContextBundle`, `MemoryRecord`, error taxonomy and protocols.
- Implement `FixtureProvider`, `InMemoryProvider` using synthetic records.
- Add authorised filtering *inside* providers and defence-in-depth checks in engine; test direct-ID and list paths as well.
- Define stable source ID, revision, trust label and explicit unknown validity.

**Acceptance**
- Both providers can be queried without the server.
- Missing tenant/actor identity fails closed.
- Cross-tenant and cross-actor access attempts fail before content is returned.
- Every Evidence has source and access metadata.

### Milestone 2 — Offline work memory (P0)

**Tasks**
- Implement `SQLiteMemoryStore` with migrations, CRUD, versioned updates, TTL/invalidation/supersession and physical deletion.
- Implement lexical search using SQLite FTS5 if present, with documented fallback. Enforce scope in DB queries; never query globally then redact.
- Implement `MemoryManager` for explicit confirmed decision/finding/attempt/open-question events; stage proposals for anything unconfirmed.
- Include deduplication and conflict handling; don't silently overwrite existing memories.
- Keep indexing, deletion and updates transactionally consistent.

**Acceptance**
- Write in session A, close process/engine, recall in session B using same DB without old transcript.
- Revision mismatch yields typed conflict error.
- Invalidated records not treated as active; delete removes index/caches as well.
- Other actor/tenant cannot read private records via direct lookup, search or export.
- No default LLM/network requirement.

### Milestone 3 — Retrieval and context assembly (P0)

**Tasks**
- Implement provider coordinator with limits, timeouts and partial-failure diagnostics.
- Merge sources/memory, normalise, deduplicate, rank deterministically, prefer source-backed evidence, flag stale/conflicting records.
- Implement token/item budget with pluggable counter and documented approximate fallback.
- Build structured `ContextBundle` and citation-rich human-readable rendering.
- Expose why-selected metadata, omissions and warnings.

**Acceptance**
- Bundles never exceed requested item budget or declared token estimate budget; never silently truncate citations.
- 100% of externally sourced excerpts in test fixtures have linked provenance.
- Identical frozen inputs generate deterministic selection and order.
- Provider unavailable yields partial results + warning rather than fabricated evidence.
- Prompt injection inside retrieved content remains inert data.
- Add measured eval output for retrieval relevance and latency on synthetic fixtures.

### Milestone 4 — Lifecycle and SDK demo (P1)

**Tasks**
- Add stable event schema for `user_confirmed_decision`, `tool_result`, `run_completed` and context refresh.
- Define `observe`/`distill` for staging memory candidates. No silent publishing to team/org scope.
- Implement `prepare`, optional `refresh`, memory proposal/commit with explicit approval evidence.
- Provide `examples/offline_resume.py` showing two independent agent sessions, same persistent memory, multiple knowledge providers and correctly attributed answer context.
- Document minimal adapter example for future EI Core and lifecycle hooks for EI Server.

**Acceptance**
- `python examples/offline_resume.py` runs offline end-to-end.
- Session 2 recovers decision, prior failure and open question from memory without session 1 transcript.
- Separate tenant/actor cannot read session 1 private memory.
- EI Core and EI Server are not imports or dependencies.

### Milestone 5 — Optional integration and optimisation (P2; not required for initial release)

Only after milestones 0–4 meet gates and benchmarks:
- Optional package extras for embedders, rerankers, remote stores or model-assisted candidate extraction.
- Safe MCP adapter with explicit host identity and tool permissions, if needed; do not create an agent loop.
- PostgreSQL backend when production concurrency/operations warrant.
- Memory quality evaluation on approved anonymised or synthetic datasets.
- Source invalidation hooks, changed-document reconciliation and team publication workflow.
- Potential graph relationships only if conventional structured lookup and hybrid search prove insufficient.

## Cross-cutting tests

**Security**: negative authorisation, cross-tenant isolation, attempts to bypass via cached results, accidental log content, hostile retrieved text, deletion of index-derived content, export scope.

**Correctness**: duplicate sources, missing source version, contradictory decisions, invalidation, stale technical knowledge, ranking ties, deterministic budgets, zero search results.

**Reliability**: provider timeouts, cancellations, concurrent revisions, SQLite lock contention, app restart, partial failures.

**Performance**: synthetic fixtures representing small and medium stores; collect p50/p95 retrieval latency (do not declare unmeasured targets), memory usage, context size and citation coverage. No extraneous external calls.

## Demo data and benchmark scenarios

Use an invented 'ledger calculation service' domain, fake ticket `DEMO-42`, invented API names and fake repository links.

1. Decision: LegacyRoute rejected due to fictional incompatibility in a fixture test.
2. NewRoute selected after comparing documentation versions.
3. Tool_result: a test has failed and needs a follow-up.
4. New session: 'Continue DEMO-42 and explain why LegacyRoute was rejected.'
5. Verify: NewRoute correctly recovered; original references shown; unresolved test remains; no transcript was passed.
6. Change source version: verify invalidation/freshness warning.
7. Another actor and tenant: zero private-memory leakage.

## Proposed PR sequence

1. `feat/scaffold` — packaging, lint, CI, test harness.
2. `feat/contracts-providers` — public models, protocols and local providers.
3. `feat/sqlite-memory` — persistence, scoping and lifecycle.
4. `feat/context-assembly` — orchestration, ranking, source-backed bundles.
5. `feat/offline-continuity-demo` — event capture, documentation, eval and integration example.
6. Optional follow-up PRs after benchmark review.

Each PR should include: scope summary, changed files, tests actually run and results, security impact, limitations and next steps. Avoid combining all work into an unreviewable first PR.

## Definition of Done (first usable release)

- [ ] Independent pip-installable Python library, functioning offline.
- [ ] No dependency on missing EI packages or external models.
- [ ] Well-defined, versioned typed contracts.
- [ ] Two generic providers + persistent scoped memory provider.
- [ ] New-session continuity demo passes after process/engine recreation.
- [ ] Source citations, scope, validity and ranking trace are visible.
- [ ] Memory correction, supersession, invalidation, delete and export safety tested.
- [ ] No agent loops/UI/dashboard/code-search duplication.
- [ ] Full tests, type checks, lint and CI pass.
- [ ] Synthetic fixture evaluation reports quality/latency; gaps honestly documented.
- [ ] README documents usage and future EI Core/Server adapter boundaries.

## Known risks / mitigation

| Risk | Mitigation |
|---|---|
| Coupling to unavailable EI source | Port protocols and fixtures; adapter later |
| Sensitive context leakage | Fail-closed scope + pre-retrieval filtering + negative tests |
| Memory misinformation | Provenance, approval/verification, supersession, expiry |
| Overbuilding agent framework | No agent loop, no execution checkpoints |
| Heavy infrastructure | SQLite/lexical-first, optional enhancements only |
| Unbounded prompt bloat | Budgeted assembly and relevance evaluation |
| Hidden implementation creep | Phase gates and explicit non-goals |

## Follow-up integrations once EI code arrives

1. Compare actual EI Core APIs to `ContextProvider` and write a narrow adapter.
2. EI Server calls `prepare` at run start, `refresh` on evidence changes, `distill` on observable outcomes; EI Server remains in charge of run state.
3. EI Integration may show evidence/citations and memory history, without EI Context owning an interface.
4. Do not refactor library concepts around implementation quirks until end-to-end scenarios establish need.
