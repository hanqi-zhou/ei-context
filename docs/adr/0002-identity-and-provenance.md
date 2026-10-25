# ADR 0002 — Host grants, immutable contracts and conservative publication

Accepted, 2026-10-25.

The proposed principal strings cannot prove membership. `AccessPolicy` therefore
uses an injected `GrantResolver(tenant_id, actor_id)`; request principals grant no
access. No resolver means actor-private access only. The authenticated host is
trusted to construct scopes; this library cannot authenticate arbitrary callers.

Namespaces and source allowlists apply to every path. Source references identify
provider snapshots; unknown version and validity remain null. Memory keeps its
original evidence references as well as its own stable identity.

Public models reject extras and are frozen, and boundaries revalidate models.
Collections use tuples/frozensets where practical. Excerpts and metadata are data,
never executable instructions. Publication requires separate explicit approval;
org publication is disabled. No change to EI package boundaries.
