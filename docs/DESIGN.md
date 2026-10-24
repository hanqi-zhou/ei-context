# EI Context — Architecture & Product Design
Version: 0.1 (2026-10-24) | Status: proposed | Owner: EI Context

## 1. Executive decision

Build **EI Context as an independently installable Python library**. It provides context retrieval, persistent work memory, evidence provenance, relevance ranking, context assembly and lifecycle operations. It MUST NOT own agent execution, model/tool loops, task management, PR dashboards, or user-facing workspaces.

This is a standalone GitHub repository because the other EI packages already exist elsewhere and their interfaces are not yet accessible. **Do not guess their code structure, copy their APIs, or block this implementation on their arrival.** Define thin contracts and synthetic integration fixtures today; align adapters later.

## 2. Problem and hypothesis

Engineering assistants repeatedly lose:
- earlier technical decisions, rationale, unsuccessful attempts and open questions across sessions;
- relevant knowledge scattered across repositories, documentation, API catalogues and policy systems;
- context linking work that spans tools, sources, sessions or repositories;
- traceable provenance, validity and access rights for evidence brought into prompts.

Hypothesis: context assembled from scoped, attributed evidence + explicit durable memory produces better cross-session task continuation, with less repetition and fewer stale or ungrounded recommendations, than chat history alone.

Success is NOT amount of memory stored. Success is recovering **correct, relevant, authorised** context at bounded cost.

## 3. Goals / non-goals

### Goals (v0–v1)
1. `pip install -e .`, no EI package or proprietary system needed.
2. Async typed public interfaces supporting retrieval, memory write/read/update/delete, context assembly and optional event observation.
3. Local/offline deterministic path: SQLite persistence, SQLite FTS5/lexical search (with graceful fallback where FTS5 unavailable), synthetic fixtures, no external credentials.
4. Session-independent workstream context scoped by actor and visibility.
5. Retrieval from heterogeneous sources using an adapter/Provider protocol, with at least two toy providers and one memory provider.
6. Rank, deduplicate and budget evidence; assemble portable ContextBundle with source citations, why-selected information and caveats.
7. Memory capture of user-confirmed decisions/discoveries and explicit reflection with an optional extractor; conflict handling, revision history, timestamps and invalidation.
8. Security-by-design: fail closed on missing scope, enforce authorisation before content reaches retrieval/ranking/LLMs, guard against prompt injection and sensitive logging.
9. Document extension points for EI Core adapters, EI Server lifecycle integration and eventual MCP without requiring those dependencies.

### Non-goals
- Agent loops, tool choice, autonomous execution, model hosting, chat UI, dashboards, PR review UI or IDE replacement.
- Duplicating API/code/wiki search implementations; adapt existing tools later.
- Agent checkpoint persistence or durable run orchestration (EI Server responsibility).
- Scraping arbitrary private conversations from third-party agents; explicit integrations only.
- Automatically publishing private personal memories as team knowledge.
- Unbounded embeddings, knowledge graph or hosted vector infrastructure by default.
- Production integration with private systems until separately approved.

## 4. Bounded contexts and interfaces

| Component | Owns | Does not own |
|---|---|---|
| EI Core (future external dependency) | Engineering capabilities, source-specific discovery, policy/dependency checks | Cross-session memory or agent loop |
| **EI Context** | Retrieval coordination, memory semantics, provenance, ranking, budgeted assembly, freshness/invalidation rules | UI, model/tool loop, agent checkpoints |
| EI Server (future) | Request identities, agent loop, execution scheduling, tool calls, checkpoints, HTTP APIs | Internal context retrieval algorithms |
| EI Integration (future) | Teams/Web/CLI/IDE adapters | Evidence policies or memory algorithms |

The dependency direction is **Server -> Context, Server -> Core**. EI Context MUST NOT import EI Server or EI Core. Any Core connection is a separate adapter implementing `ContextProvider`.

Context may use configurable optional LLM extractors but must expose an LLM-free deterministic path.

## 5. Reference architecture

```text
Integration: Teams | UI | CLI | IDE | external agent
                      |
                      v
EI Server: identity + agent runtime + tool loop + checkpoints
               /                          \
              v                            v
        EI Core tools                   EI Context
           (future)             +-------------------------+
              |                 | ContextEngine           |
              +--adapter------->| - retrieval coordinator |
                                | - evidence ranking      |
Other providers ---------------->| - deduplication         |
                                | - bounded assembly      |
Memory provider <-------------->| - memory manager        |
                                | - lifecycle policies    |
                                +-------------------------+
                                          |
                              MemoryStore / index backends
                              SQLite (default) / future PG
```

`ContextEngine.prepare(request)` produces a cited `ContextBundle`; EI Server chooses when to call it. `ContextEngine.observe(event)` can extract candidates, but should never change authoritative memory on a mere model guess. `ContextEngine.commit_memory(...)` persists explicit and validated records. Every method may be called directly by third-party applications.

## 6. Core domain objects

- **AccessScope**: authenticated `actor_id`, `tenant_id`, allowed namespaces and visibility constraints, optionally allowed source IDs; required for EVERY retrieval or mutation. Client requests must not self-declare team membership in untrusted deployments.
- **WorkstreamRef**: optional external task/workstream ID and related repository references. Do not implement an issue tracker.
- **SourceRef**: stable URI/opaque source ID, source type, retrieved timestamp and optionally last-modified/version, applicable scope.
- **Evidence**: source-backed content or excerpt with provenance and validity/freshness flags; provider-supplied trust label, not blindly derived from text.
- **MemoryRecord**: stable ID, kind (decision, finding, attempted_approach, open_question, task_summary), content, actor/workstream, visibility, evidence refs, created/updated/validity timestamps, state (active/superseded/invalidated), revision, sensitivity classification and optional confirmation status.
- **ContextRequest**: question, mandatory scope, optional workstream and source constraints, maximum tokens/items, target usage and exclusions.
- **ContextBundle**: selected evidence, selected memories, compact rendered context, citations, token estimate, omitted-count and warnings. Never return unsupported statements as verified facts.
- **ContextEvent**: adapter-neutral event such as tool_result, user_confirmed_decision or run_completed; no private internal reasoning or implicit access to other agents' sessions.
- **MemoryCandidate**: extracted candidate pending validation/explicit approval, with source and confidence/uncertainty metadata. Do not auto-promote candidates to organisation-scoped knowledge.

Use Pydantic 2 for serialisable public models; `typing.Protocol` for pluggable stores, retrievers, extractors, token counters and policies. Provide schema compatibility/version tags for persistence and exported bundles.

## 7. Retrieval and assembly sequence

1. **Validate caller context**: require scoped identity, source restrictions and max budget.
2. **Recall explicit work memory** by workstream and query; get recent relevant prior decisions and outcomes.
3. **Query eligible providers** using bounded concurrency and timeouts. Providers MUST filter by scope before returning text; engine performs defence-in-depth filtering.
4. **Normalise and deduplicate** evidence using stable source IDs, version and content hashes.
5. **Rank** via configurable lexical relevance, workstream match, evidence quality, recency and decision importance. Fresh current source evidence should supersede stale recollection when contradictory; record uncertainty.
6. **Assemble** within item and token budgets. Keep citations, short snippets and rationale; leave out irrelevant or duplicate data.
7. **Return** both machine-readable results and a human-readable rendering. Mark unavailable sources/timeouts and stale content explicitly.

No mandatory vector database. Start with BM25/FTS-style lexical retrieval and structured filters; make embeddings/rerankers optional providers behind interfaces. The library must remain functional with zero API keys.

## 8. Memory semantics and lifecycle

Differentiate:
- **Session transcript / run checkpoint**: runtime state; owned externally by EI Server.
- **Work memory**: durable, curated facts about what happened and why; owned by EI Context.
- **Source evidence**: authoritative source snapshot or pointer; owned by source system or provider.
- **Procedural skill**: instructions for repeatable tasks; not automatically minted from every session.

Memory lifecycle:
- `propose`: extractor or caller submits candidate with provenance.
- `validate`: check permissions, duplication, contradictions, sensitive data and evidence existence.
- `commit`: explicit mutation with version and scope; source `user_confirmed` or `system_verified` where available.
- `retrieve`: apply scope first, then rank.
- `revise/supersede`: retain lineage while replacing stale active memory.
- `invalidate`: deactivate source-linked claims when changed/expired.
- `delete`: remove memory and index entries subject to explicit retention policy; no dangling snippets.
- `export`: export authorised records with provenance (not broader private context).

Do not silently merge contradictory decisions; present conflict and timestamps. A newer memory is not automatically more authoritative. Team/public publication requires an explicit, separately authorised operation; default visibility is private.

## 9. Execution integration without runtime ownership

Optional lifecycle operations:
- `prepare(request)` at new task/session start;
- `refresh(request, previous_bundle)` after relevant changes or when budget exhausted;
- `observe(event)` to stage candidate memories from explicit observable outcomes;
- `distill(events)` to produce memory candidates at run completion;
- `commit_memory(candidate, ...) ` after validations.

EI Server retains agent loop, model calls, retries, tool permissions, checkpoints, session transcript, run state and event scheduling. EI Context MUST NOT orchestrate a model/tool conversation. Long-running indexing/ingestion will later be owned by a host worker, with engine-level functions reusable synchronously/on demand.

External agents without EI Server can call the library directly. A future MCP adapter exposes controlled operations; it is an adapter, not a second engine.

## 10. Persistence and extensibility

Initial: SQLite (`sqlite3` or `aiosqlite` adapter), schema migrations, lexical index, transactionally consistent record/index updates, tenant and scope fields indexed. SQLite is for trusted local use, tests and demos. Never present local actor strings as sufficient production authentication.

Future: PostgreSQL adapter, enterprise search/vector adapter, optional extractor LLMs, optional embedding backends. Avoid vendor dependence in public contracts.

Provider interface: `search(query, scope, workstream, limit) -> list[Evidence]`. Store interface: `add/get/search/list/update/invalidate/delete`, always scoped, with version checks and hard-delete behaviour documented.

Use an explicit cancellation/timeout strategy and partial-results warnings. Provider failures must not be confused with 'no results'.

## 11. Security, privacy and trust requirements

- Trust boundary: an authenticated host supplies `AccessScope`; EI Context enforces it; source adapters apply native permissions. Never accept model-generated scopes.
- **Fail closed**: missing/inconsistent scope must error, including on writes, exports and cache hits.
- Tenant isolation at SQL query and index retrieval boundaries, not just after ranking.
- Source text and prior conversations are **untrusted data**; they cannot instruct tool execution, secret access, policy override, or memory permission changes.
- No secrets, raw transcripts or evidence contents in default logs. Redacted structured telemetry only.
- Make offline mode default; do not transmit source data to external embedding/LLM services by default.
- TTL, invalidation, export and deletion must cover indexes, derived data and caches.
- Preserve attribution, visibility and original version to avoid laundering obsolete claims into 'facts'.
- Add tests for adversarial retrieval attempts, cross-tenant leakage, injection-containing documents, and stale conflicting memory.
- Public repository must use **synthetic examples only**. Check employer policy before linking real internal systems, regardless of repository visibility.

## 12. Quality, evaluation and performance

Evaluation fixtures should cover:
- New-session continuation of a technical investigation (with no shared transcript).
- Correct retrieval of current technical evidence vs stale memory.
- Scoped isolation across actors, tenants and private/team records.
- Multi-source deduplication and citation completeness.
- Contrary decisions and supersession handling.
- Bounded token/item assembly and deterministic ordering.
- Offline operation, no credentials or network.
- Provider failures, slow sources and graceful partial results.

Report top-k recall/precision on a labelled synthetic set, citation coverage, unsupported-memory rate, leakage tests, execution latency distribution and budget adherence. Never claim benchmark improvement without measured baseline. Include structured tracing of source IDs and selection reasons but not source contents by default.

## 13. Design decisions and trade-offs

1. **Separate library, not separate service**: deploy an API only if multi-client shared auth, scaling or operations justify it.
2. **No cyclic EI dependencies**: Core adapters may live in a separate optional integration module.
3. **Structured memory rather than transcript-as-truth**: retain evidence refs and revisions.
4. **Permission filtering before semantic retrieval**: security takes precedence over ranking accuracy.
5. **Incremental retrieval before graph/vector complexity**: measure first.
6. **Host-controlled lifecycle**: preserve compatibility with multiple agent runtimes and workspace UIs.
7. **No unapproved team-memory learning**: prevent accidental private-context disclosure.

## 14. Deferred questions (do not block P0)

- Which organisational identity provider will EI Server use?
- Whether production storage needs PostgreSQL, search service, or encryption configuration.
- Which external agents support lifecycle callbacks vs MCP-only access.
- Whether team memories require human review or a policy engine.
- Precise tokenisation strategy per target model.
- Evaluation datasets sourced from approved internal systems (not for public repo).
- Whether EI Core APIs require adapters or already conform to protocols.

Record decisions as ADRs when resolved. See [implementation plan](IMPLEMENTATION_PLAN.md) and [contracts](CONTRACTS.md).
