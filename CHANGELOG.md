# Changelog

## 0.2.0 — Provider-qualified authorisation and event lineage (not published)

- AccessScope schema 2 with typed SourceIdentity allowlists; legacy bare restrictions fail closed.
- Atomic SQLite schema v1→v2 migration restores provider identity from all revisions.
- Extracted/explicit nested proposals must cite exact authorised source-event snapshots.
- Source validity/modified/URI metadata participates in duplicate detection; retrieval time alone does not.
- Actor principals cannot masquerade as team grants. New collision/migration/lineage regressions.
- Remains independent of EI Learning, EI Core and EI Server.


## 0.1.0 — Initial implementation (2026-10-25; not published)

- Independent Python package, typed Pydantic models, async provider/store contracts.
- SQL-scoped SQLite memory with approval, history, revisions, expiry, supersession,
  invalidation, export and deletion; transient scoped FTS5 with lexical fallback.
- Two local providers plus memory adapter; host-verified grant resolver and default
  private access. No org publication or implicit team promotion.
- Bounded retrieval, deterministic ranking/dedup, cited budgeted JSON bundles,
  stale/conflict/partial-result caveats and permission-aware refresh without caches.
- Explicit observable events, private staged proposals and approval-only commit.
- Process-separated offline demo, synthetic adapters, evaluation and security tests.

Refinements to the proposed contracts: concrete MemoryUpdate/ApprovalEvidence DTOs;
immutable tuples/frozensets; namespaces and source allowlists; host GrantResolver;
conservative complete-payload token estimate; explicit memory manager attachment;
caller-owned proposal staging; synchronous local transactions under async API.
See ADRs 0002–0005 and the release checklist for limitations and deferred integrations.
