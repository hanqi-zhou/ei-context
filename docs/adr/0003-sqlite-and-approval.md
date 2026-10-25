# ADR 0003 — Local transactions, scoped FTS and explicit attestation

Accepted, 2026-10-25.

SQLite schema v1 uses atomic migrations, optimistic revisions and cascading source
indexes/revision history. ACLs, namespaces and source allowlists are applied in SQL
before bodies are loaded. Every historical revision has its own source index.

Instead of a global FTS index (whose ranking statistics could mix tenants), search
builds a transient FTS5 index ONLY from authorised active rows, drops it in finally,
and uses deterministic lexical overlap for final ordering. Without FTS5, the same
authorised corpus is matched with Python lexical terms. This is an intentional
v0.1 throughput tradeoff; it avoids persistent derived-text caches entirely.
FTS5 and fallback may differ in Unicode tokenisation; neither is semantic search.

The async API currently performs short synchronous SQLite operations on its owning
thread with a 100ms lock timeout. No background tasks. Higher throughput requires
a different MemoryStore adapter; hosts must not share a connection across threads.
Physical deletion removes records, all revisions and source indexes. secure_delete
is enabled; independent exports, OS snapshots and backups remain host-controlled.

ApprovalEvidence is an explicit trusted-host attestation: the approver confirms the
statement and its cited provenance. The library does not authenticate approvers or
independently verify arbitrary source URIs. A confirmation is not proof of technical
truth. Assembly flags unavailable or changed supporting evidence. No source-fetching
or external LLM is hidden in commit. Exact duplicate proposals are idempotent;
contradictory claims coexist until explicit correction/supersession.
