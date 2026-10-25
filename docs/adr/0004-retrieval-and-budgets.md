# ADR 0004 — Bounded, quoted, deterministic context

Accepted, 2026-10-25.

Providers are limited to 32, concurrent calls to configurable 1..32, each result to
1..1000 candidates, and each call has a timeout. Cancellation propagates; adapters
must cooperate with asyncio cancellation and avoid blocking I/O. Failure diagnostics
exclude exception details and source contents. Provider failures differ from empty hits.
No caches or background tasks. Refresh always rechecks permissions.

The default ranker uses lexical overlap, workstream match, declared provider trust,
recency and memory importance. No semantic understanding or automatic truth finding.
The engine filters ACLs before ranking, including replaceable rankers, and checks
that a ranker cannot invent or change authorised evidence. Deterministic ties use
provider and evidence IDs. Frozen inputs/clock/policy yield equal bundles.

Deduplication uses provider/source/version/content hash and preserves supporting
references. Different versions remain visible with caveats. Explicit timestamps,
not lexicographic version strings, identify older snapshots. Potentially conflicting
active decisions coexist, with review warnings. Missing source evidence is not
interpreted as proof that a memory is false or independently verified.

The default token counter conservatively counts UTF-8 bytes as estimated tokens.
Inject an exact model counter if required. Budgets include the full JSON rendering,
framing, metadata and citations. Whole items are omitted when they do not fit;
citations are never truncated. Excerpts cap at 1200 characters with an explicit
caveat. Tiny budgets raise BudgetExceeded. Warnings are structured diagnostics,
not extra source content inserted outside the budgeted payload.

Retrieved data, metadata, reasons and provenance are JSON-quoted beneath an
untrusted-data framing. This prevents delimiter breakout; the consuming host must
still keep it in a data role and must never execute retrieved instructions.
