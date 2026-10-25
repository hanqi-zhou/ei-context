# v0.1 implementation and release checklist

2026-10-25. This checklist records implemented local gates; hosted CI status belongs
to the corresponding PR checks. No public package release, license, merge or deployment
has been performed. Review and merge the five PRs in dependency order.

| Milestone / acceptance | Result | Evidence |
|---|---|---|
| #1: standalone install, typed package, offline import | PASS locally | Exact editable install, network-audit import test, py.typed |
| #1: tests, lint, typecheck, builds | PASS locally | Commands below; Python 3.11–3.13 CI configured |
| #2: typed contracts, provenance, two generic providers | PASS | models.py, protocols.py, FixtureProvider, InMemoryProvider |
| #2: missing/forged scope, actor/tenant/source/namespace guards | PASS | security/test_providers.py and security/test_engine_access.py |
| #3: SQLite migrations, approved CRUD/history, FTS/fallback | PASS | integration/test_memory.py; schema v1 and scoped transient index |
| #3: restart, revision races, locks, rollback, TTL, supersession | PASS | Separate-process read; two connections; transaction-failure injection |
| #3: no private get/search/list/export/history/mutation leakage | PASS | security/test_memory_access.py, including restricted history refs |
| #3: invalidation and physical deletion of history/index rows | PASS | Integration assertions against all three SQLite tables |
| #4: deterministic rank/dedup, cited structured/rendered context | PASS | integration/test_engine.py; stable reasons and source versions |
| #4: full token/item estimate budgets, no clipped citations | PASS | Complete rendering counted; tiny-budget errors; item omission |
| #4: timeouts, cancellation, partial failures and empty hits | PASS | Provider coordinator integration tests; safe diagnostics |
| #4: injection remains quoted data, filtering before rankers | PASS | Security suite, source-reference laundering and forged-ranker tests |
| #4: stale/current source versions and conflict caveats | PASS | Active conflicting memories preserved; explicit supersession clears warning |
| #5: explicit event schema, optional extractor, staged proposals | PASS | Lifecycle tests; no automatic persistence or shared promotion |
| #5: decision/failure/open question resume in new process/engine | PASS | offline_resume.py; assertions with network disabled |
| #5: adapter compatibility and host lifecycle docs | PASS | ADAPTER_GUIDE.md and runnable examples/adapters.py |
| Synthetic relevance, latency, memory/citation/leakage metrics | MEASURED | EVALUATION.md; no baseline/production quality claim |
| Hosted CI for first four implementation branches | OBSERVED PASS | PRs #6–#9; all Python matrix jobs succeeded |
| Hosted CI for final implementation branch | REQUIRED PR GATE | Final PR checks are authoritative; result reported in PR description |
| Real EI Core/Server integration | DEFERRED | Source unavailable; Protocol/shim contract only |
| Production authentication, high-scale storage, exact model tokenizer | DEFERRED | Host responsibilities / future adapters; not v0.1 claims |
| Public license, PyPI publishing, services/UI/agent runtime | EXCLUDED | Explicitly outside authorised scope |

## Exact local commands and outcomes

- `python -m pip install -e '.[dev]'`: succeeded, including isolated editable build.
- `python -m pytest`: 43 passed on Python 3.12.14.
- `python -m ruff check .`: passed.
- `python -m mypy`: passed, strict mode, 18 source files.
- `python -m build --no-isolation`: sdist and wheel built successfully.
- `python examples/offline_resume.py`: OFFLINE CONTINUITY PASS.
- `python examples/adapters.py`: SYNTHETIC ADAPTER PASS.
- `python scripts/evaluate.py`: measured output recorded in EVALUATION.md.
- `python scripts/evaluate_memory.py`: measured output recorded in EVALUATION.md.

## Justified deviations and remaining boundaries

1. Scoped transient in-memory FTS replaces a global persistent text index. Only
   authorised SQL bodies enter it; it is removed after each search. Source indexes
   and revision history remain transactionally persisted. See ADR 0003.
2. Async store contracts currently wrap bounded synchronous local SQLite work.
   High concurrency requires another adapter. No background indexing is introduced.
3. Approval attests a user/system statement and cited provenance; it does not fetch
   arbitrary URIs or establish semantic truth. Current-source mismatch/missing support
   warnings remain visible. See ADRs 0003–0004 and SECURITY.md.
4. A conservative UTF-8 byte estimate budgets the complete rendered payload; exact
   tokenizer integration is a host extension. No truncated source citations.
5. Unapproved candidates are staged in caller memory; raw tool output is not
   automatically learned. Shared publication is a separate explicit approved write.
6. Identity, grant resolution, sensitivity classification and approval binding belong
   to a trusted host. Org publication is disabled. No production auth claim is made.

## Next steps after review

Merge scaffold → contracts/providers → SQLite memory → context assembly → continuity
in order, retargeting each dependent PR to main. Keep original implementation issues
open until the reviewed changes reach main. Then compare real EI APIs with the shim
and implement a narrow native-permission-aware adapter without changing package ownership.
