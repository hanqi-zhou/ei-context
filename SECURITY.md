# Security boundary and limitations

This is a local library, not an authentication service or multi-tenant server.
Use an authenticated trusted host to construct scopes, verify grants and bind
approvals to content/provenance. Request principal strings grant no access.

SQL restricts tenants, namespaces, private owners, verified teams and source IDs
before returning content. Historical revisions have independent source indexes.
The temporary FTS index uses only authorised active records and stays in memory.
It is dropped after each query; no result/embedding caches or telemetry are retained.
Hard deletion cascades through history and indexes. secure_delete is enabled, but
OS snapshots, exported bundles, backups and forensic erasure remain host concerns.

Use filesystem encryption/permissions if real confidential data is ever stored.
Do not expose direct SQLite access to untrusted actors. Do not accept arbitrary
AccessScope or ApprovalEvidence JSON from a client as authenticated authority.
No production EI source or real user data is included in this repository.

Retrieved text, metadata and memory are untrusted evidence. JSON quoting prevents
rendering delimiter breakout, but cannot guarantee downstream LLM behaviour. Keep
bundles in a data role and enforce tool permissions outside this library. No source
text can trigger execution or permission changes in EI Context itself.

No automatic truth verification, secret detector or source-URI fetch is implied by
approval. Hosts classify sensitivity; sensitive writes require explicit approval.
Missing/changed evidence and conflicting current decisions are caveated. Optional
external extractors/rankers must respect native source and transmission permissions.

Default logs contain no source contents, secrets, tokens or raw exceptions. Provider
failure warnings are intentionally generic. Providers must filter before their own
external processing and cooperate with cancellation. Local SQLite is synchronous
with bounded lock wait; it is not intended for high-concurrency production hosting.

Tests cover direct-ID/search/list/export/history/mutation access, cross-actor and
cross-tenant isolation, forged group hints, source restrictions, pre-ranker/extractor
filtering, hostile documents, revision races, rollback and deletion consistency.
