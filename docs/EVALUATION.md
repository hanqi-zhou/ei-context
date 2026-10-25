# Synthetic evaluation — 2026-10-25

Environment: Python 3.12.14, Pydantic 2.14.1, Linux container. No network,
credentials, proprietary data, model APIs or baseline comparison. The tiny lexical
fixture is a correctness smoke benchmark, not evidence of production quality.

## Retrieval relevance and cited assembly

Command: `python scripts/evaluate.py`.

36 documents (six synthetic technical topics plus 30 unrelated distractors), six
labelled queries repeated 20 times, max two items, 4000 declared estimated tokens.
Precision@2 divides relevant returned items by actual returned items (not a forced
size of two); recall@2 divides relevant returned items by labelled relevant items.
All queries returned their labelled item. Citation coverage checks linked provenance
for all selected excerpts. Latencies include provider coordination and assembly.

```json
{
  "python": "3.12.14",
  "dataset": "36 synthetic docs, 6 labelled queries x 20 repeats",
  "precision_at_2": 1.0,
  "recall_at_2": 1.0,
  "citation_coverage": 1,
  "budget_adherence": 1,
  "latency_ms_p50": 0.40619700007482606,
  "latency_ms_p95": 0.6209010000475246,
  "actor_leakage_count": 0,
  "unsupported_memory_rate": null,
  "limitations": "Small lexical fixtures; no real data, embeddings, human judgement or baseline. Unsupported-memory rate not measured here; lifecycle suite covers memory."
}
```

## Memory continuity and storage measurements

Command: `python scripts/evaluate_memory.py`.

The quality fixture writes three memories, invalidates a fourth, closes/reopens
SQLite, then retrieves with two technical providers and the memory adapter. One of
three active memories deliberately cites outdated docs v1 while docs v2 is returned.
"Unsupported-memory rate" here means missing exact provenance-version support,
not semantic entailment. The stale memory remains useful historical context but is
caveated: 1/3 unsupported, zero uncaveated unsupported memories. This benchmark does
not establish that a cited document logically proves every statement.

The performance fixture creates 100 and 1000 synthetic approved records in separate
DBs, closes/reopens each, then runs 30 warm searches with FTS5. Python tracemalloc
is enabled DURING timing, increasing latency; peak bytes exclude native SQLite
allocations. No cold-start, concurrent-load or maximum-throughput claim is made.

```json
{
  "methodology": "Synthetic only; 30 warm searches after reopening each DB. tracemalloc enabled during timing; SQLite native allocations excluded.",
  "stores": [
    {
      "records": 100,
      "searches": 30,
      "fts5": true,
      "latency_ms_p50": 4.739263000033134,
      "latency_ms_p95": 5.7347879999269935,
      "python_peak_bytes_during_search": 717395
    },
    {
      "records": 1000,
      "searches": 30,
      "fts5": true,
      "latency_ms_p50": 54.32668549997288,
      "latency_ms_p95": 65.75214300005428,
      "python_peak_bytes_during_search": 6564917
    }
  ],
  "continuity_quality": {
    "expected_memory_recall": 1.0,
    "selected_memories": 3,
    "unsupported_memory_rate": 0.3333333333333333,
    "uncaveated_unsupported_memory_rate": 0.0,
    "citation_coverage": 1.0,
    "private_actor_and_tenant_leakage": 0,
    "invalidated_memory_selected": false,
    "budget_adherence": true
  }
}
```

## Security and end-to-end evidence

`python examples/offline_resume.py` launches two different Python processes and
passes only a SQLite path. It asserts recovery of the NewRoute decision, rejected
LegacyRoute rationale, original citations and rounding open question; a changed
supporting source version warns. Unrelated actor and tenant cannot read the records
or exports. An audit hook rejects outbound socket/DNS activity in both sessions.
`python examples/adapters.py` also passes with a synthetic permission-aware shim.

43 unit/integration/security tests pass locally, including scoped FTS and forced
fallback, all store read/mutation paths, history source restrictions, grant revocation,
pre-ranker/extractor filtering, delimiter injection, TTL/version conflicts, source
expiry, transactions/rollback, two-connection revisions, cancellation and timeouts.
See RELEASE_CHECKLIST.md and current PR checks for the required hosted CI gate.

## Limits and next experiments

- Labels are small, synthetic and closely matched to query vocabulary; no semantic,
  multilingual, paraphrase or human relevance evaluation is claimed.
- No measured improvement over chat-only or another retriever; no baseline exists.
- Conflict warnings are conservative lexical/structured checks, not truth inference.
- FTS/fallback Unicode tokenisation may differ. Ranking and byte token estimation
  are replaceable; exact target-model limits require a host TokenCounter.
- Per-query authorised indexing/loading grows with the actor-visible corpus; larger
  or concurrent stores need measured adapter work, not a production SQLite promise.
- Native EI integration/authentication and approved real-world datasets remain future
  host integration tasks, once their actual source/contracts are available.
