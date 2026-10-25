# Qualified permissions and observed provenance — v0.2

Implements security issue #12 and integrity issue #13, with additional review fixes
for freshness-aware deduplication and actor principals incorrectly labelled as teams.
No new service, agent loop, model dependency, memory store or production integration.

## Contract and compatibility

`AccessScope.schema_version` is `2`. Its optional `allowed_sources` is a frozenset of
frozen `SourceIdentity(provider, source_id)` models. Null means unrestricted sources
inside the existing actor/tenant/namespace grants; empty means no source access.
A source identity is an exact pair, not an ambiguous concatenated string. Versions
remain provenance/freshness metadata, not a substitute for native authorisation.

Legacy `allowed_source_ids=None` is accepted but excluded from new serialisation.
Any non-null bare allowlist fails validation. No guessed provider, wildcard matching
or silent permission expansion is permitted. Model-copy and constructed scopes are
revalidated at access boundaries. Update restricted callers explicitly before use.
Stored MemoryRecord and SourceRef snapshots keep their existing compatible shape.
Export envelopes report schema version 2.

SQLite schema version 2 adds provider to the revision/source index primary key.
The atomic v1 migration reads every stored revision's original SourceRef snapshots,
rebuilds the index, recalculates current duplicate fingerprints and advances
user_version only in the same successful transaction. It never guesses a provider
from the old bare-ID index. Make a backup before upgrade; old binaries refuse this
new schema instead of weakening permissions. Exports/backups remain host-owned.

## Authorisation paths

Local provider search/get/list, engine pre-ranker filtering, all memory reads,
search, history, export and mutations use qualified source permissions. Both primary
source and all supporting references are checked. The persistent MemoryProvider's
synthetic memory citation is only an internal identity: original references remain
mandatory and carry the source restriction. No source text can grant access.

Source indexes include every revision independently. A current permitted correction
does not reveal an old revision supported by another provider. Shared memory still
requires a verified named team and explicit publication approval; an actor principal
cannot be used as a team principal, even by the record owner.

## Observed source lineage

Event-derived candidates must cite an exact subset of the event's authorised source
snapshots (provider, ID, version, URI and timestamps). The same check applies to
nested explicit proposals BEFORE optional extraction and to extractor results.
Changing or adding evidence requires a separately observed event, not a fabricated
reference returned by an extractor. Records persist the validated event ID and
selected original source snapshots; raw events/transcripts are not persisted.
Approval remains host attestation and does not prove semantic correctness.

## Verified regressions

`python -m pytest -q`: 51 tests passed locally; strict mypy and Ruff pass. Added tests
cover equal bare IDs in A/B providers, primary/supporting-reference laundering,
get/search/list/history/export/update/invalidate/delete denial, constructed legacy
restrictions, exact SourceIdentity roundtrip, v1 database migration, independent
historical revision access, deletion after migration, changed source validity,
forged source provider/version/URI and pre-extractor lineage checks. Existing
process-separated offline continuity remains a required CI gate.

## Next shared direction

Stabilise these access/provenance contracts before a read-only Learning adapter.
The coding-agent harness belongs only in EI Learning. Its primary score is executable
held-out acceptance, with strong handoff and memory controls, total acquisition cost,
negative transfer and unaffected-task retention. No Context retrieval score is a
claim of improved agent behaviour. Topic-aware conflict handling (#15) and measured
retrieval scaling (#14) remain tracked; neither requires adding an agent runtime here.
