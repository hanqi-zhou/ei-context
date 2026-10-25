# Implementation assumptions

- Python 3.11+; Pydantic 2; SQLite from Python's standard library.
- A trusted host authenticates actors. Request principal strings alone do not confer
  team access. An injected grant resolver verifies group membership; absent one,
  only private actor ownership is recognised. Org publication is disabled in v0.1.
- SQLite is a trusted local file, not an authentication server. Protect the file
  and backups with host filesystem permissions. No proprietary data in fixtures.
- All timestamps are timezone-aware; stored memory clock timestamps are normalised
  to UTC, while source snapshots may retain their explicit offset. Clocks are injectable.
- Unknown source version/validity is explicit null, never proof of freshness.
- Five dependent PRs are stacked in issue order; merge bottom-up and retarget the
  next PR to main. No license, package publication, service or deployment added.
