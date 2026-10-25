# ADR 0005 — Explicit observable events, staged private candidates and release gates

Accepted, 2026-10-25.

observe/distill do not save transcripts or unapproved candidates. A versioned event
contains authenticated identity, namespace, optional workstream, source references,
summary and optional structured proposal. The explicit-only extractor proposes
confirmed statements or caller-supplied structured candidates; raw tool output and
run completion text do not automatically become memory.

The manager authorises events and nested references BEFORE any optional extractor.
Extractor results must be private and preserve event workstream/namespace. Approval
is still required for all durable writes. Sharing is a separate explicit candidate
plus publication approval, never a model-inferred promotion. Sensitive-labelled
records require additional explicit approval; classification remains host-owned.

ContextEngine optionally receives a MemoryManager; MemoryProvider is registered
explicitly. close() closes that manager's store only. prepare/refresh and all
lifecycle methods are standalone calls, not execution scheduling or an agent loop.

The acceptance demo launches write and resume in different Python processes, passes
only a SQLite path, and blocks outbound network in both. Supporting docs change from
v1 memory provenance to v2 source evidence to exercise a review caveat. Actor/tenant
isolation assertions run in session B.

Release is a set of reviewable stacked PRs, not an automatic merge, deployment,
public license or PyPI upload. Python 3.11–3.13 CI is a gate; local Python 3.12
checks and synthetic metrics are reported separately from observed hosted results.
No production authentication, native EI integration, semantic entailment verifier,
remote storage or scale guarantee is claimed.
