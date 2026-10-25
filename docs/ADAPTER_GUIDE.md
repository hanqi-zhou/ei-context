# EI Context adapter and lifecycle guide (implemented v0.1)

EI Context is called by a host. It does not import EI Core, EI Server, an agent SDK
or a web framework. Public contracts use Pydantic models (schema version `1`) and
async Python Protocols. Python >=3.11 and Pydantic >=2.7,<3 are supported.

## EI Core or other engineering capability provider

Implement `ContextProvider.provider_id` and async
`search(query, *, scope, workstream, limit) -> Sequence[Evidence]`.

1. The host authenticates actor/tenant and resolves native source permissions.
2. Apply source, namespace and native ACL restrictions BEFORE fetching text,
   lexical/vector search or remote model processing. Do not globally search and
   then rely on EI Context to redact results.
3. Translate hits to `Evidence` and immutable `SourceRef` snapshots. Source IDs are
   stable within a provider; globally unique Evidence IDs must not collide across
   providers. Source allowlists match source_id strings: use globally unique,
   provider-qualified source IDs in native adapters to avoid cross-provider ambiguity.
   Include accurate tenant, namespace, effective actor/team principals,
   version, timestamps, source URI and provider-declared trust. Unknown version or
   validity is null; do not invent freshness or `system_verified` labels.
4. Honour bounded limits, asyncio cancellation and timeout. Raise failures instead
   of returning an empty list on outage. The engine sanitises failure diagnostics.
5. The engine applies ACL/source restrictions again BEFORE custom rankers. A custom
   ranker may reorder/score authorised evidence, never alter or invent it.

Run `python examples/adapters.py`. Its `NativeSearchShim` is an illustrative host
translation layer; it is NOT a proposed method on the unavailable EI Core source.
Replace only that shim when real APIs arrive. Source-specific discovery/checks
remain EI Core responsibilities. No cyclic dependency or EI package path is assumed.

## Trusted identity and grants

Pass the same `AccessPolicy(grant_resolver)` to the engine, memory store, manager
and local providers when enabling teams. Resolver inputs are authenticated tenant
and actor IDs; its result comes from a trusted membership source, not an LLM or
request `principals`. Resolve fresh grants rather than caching permissions in bundles.
Default policy recognises owner-private access only. Team readers cannot mutate
another owner's records. Team writes require both membership and
`ApprovalEvidence.allow_publication`; sensitive-classified writes additionally
require `allow_sensitive`. Org publication is disabled.

Scopes and approvals are trusted-host attestations, not authentication tokens.
Bind approvals to the actual candidate and source references in the host review
workflow. The library deliberately performs no hidden network validation of arbitrary
URIs. Approval of a statement does not establish technical truth. Adapter retrieval
must verify actual source access and supply current evidence at prepare/refresh.

## EI Server or third-party host lifecycle

```python
# At run/session start, with host-authenticated request scope:
bundle = await engine.prepare(request)
# Keep rendered_context in a data/tool-result role. Never elevate source text to
# system instructions. Let the host decide tool/model/run orchestration.

# After an observable outcome (not private reasoning or a raw transcript):
candidates = await engine.observe(event, scope=scope)
# Or at completion, distill a bounded sequence of explicit observable events:
candidates = await engine.distill(events, scope=scope)

# Present a candidate to the authenticated approver or verified policy system.
# Only after approval:
record = await engine.commit_memory(candidate, scope=scope, approval=approval)

# After source/grant changes:
bundle = await engine.refresh(request, previous_bundle=bundle)
# On host shutdown, when engine owns this attached manager's store:
await engine.close()
```

Construct with explicit providers and `memory_manager=MemoryManager(store)`;
include `MemoryProvider(store)` in providers to recall memories. Attaching a
manager does not silently register providers. Standalone retrieval engines can
omit the manager. `close()` closes only the attached manager's store; provider
clients and independent stores remain host-owned.

Events support `user_confirmed_decision`, `user_confirmed_finding`, `tool_result`,
`run_completed` and `context_refresh`. They are versioned, scoped and carry source
references and optional structured proposals. Default extraction proposes confirmed
statements or explicit proposals only. A tool result/run completion is never an
implicit durable write. Candidates stay in caller memory until approved; unapproved
proposals are not written to SQLite. Optional extractors receive authorised events
only and must return private proposals preserving event workstream/namespace.
No event scheduler, runtime checkpoint, task tracker or model conversation is added.

## Alternate backends and model components

Implement `MemoryStore` to replace local SQLite. Preserve ACLs before indexing,
optimistic revisions, atomic record/history/index changes, TTL and deletion semantics.
Implement `TokenCounter` for exact host-model accounting. `Ranker` is synchronous
in v0.1 and receives only authorised evidence; heavy/remote ranking should be wrapped
by the host with explicit cost and cancellation controls, or motivate a future async
contract ADR. Optional `MemoryExtractor` is async and never writes automatically.

No automatic embeddings or LLM dependencies are installed. Remote services must be
explicitly configured by a host with permission to transmit the relevant scoped data.
