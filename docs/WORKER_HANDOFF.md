# Worker Handoff — Build EI Context

**Repository**: `hanqi-zhou/ei-context`
**Starting point**: architecture documents only; the rest of EI Stack is unavailable on this machine.
**Goal**: deliver a working, independently installable `ei-context` Python library with offline persistent memory and evidence-backed context assembly.

## Start here

Read, in order:
1. [DESIGN.md](DESIGN.md) — responsibilities and security boundaries.
2. [CONTRACTS.md](CONTRACTS.md) — proposed public API and protocols.
3. [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — milestones, tests and definition of done.
4. [DX_BACKLOG.md](DX_BACKLOG.md) — broader opportunities; only P0 scope in initial build.
5. [ADR 0001](adr/0001-package-boundaries.md) — independent library, not an agent runtime.

Treat designs as intent, not pre-existing code. You can refine interface details for Python ergonomics, but preserve explicit scope, provenance, session independence and clean dependency boundaries. Record deviations in ADRs.

## Instructions to Worker

Build the actual code in this repository, not a report-only implementation. Start with milestone 0, then milestones 1–4. Use focused PRs with tests. Aim for the **smallest complete vertical slice** before sophisticated embeddings/agents:

- Write an explicit, scoped decision with source evidence.
- Persist it in SQLite.
- Close the engine and construct a new one.
- Ask a related query; retrieve and rank the right previous decision plus synthetic technical evidence.
- Assemble a cited ContextBundle under a budget.
- Demonstrate that a different actor or tenant cannot read that private memory.

### Non-negotiables

1. No dependencies on `ei-core`, `ei-server` or `ei-integration`. Do not invent their APIs.
2. No custom chat UI, developer dashboard, task board, PR surface or agent loop. These belong elsewhere.
3. No hidden requirement for external LLM/embedding API keys, production DB or internet access.
4. All examples are synthetic. Do not include real proprietary source code, tickets, API contracts, secrets or user conversations.
5. Enforce scope **before** any retrieval or external model processing. Do not assume query-time filters alone prevent leakage; test every path.
6. Treat retrieved source text as untrusted data, never as instructions; avoid prompt injection and memory poisoning.
7. Auto-extraction may propose memory candidates, but only verified/approved records become durable shared knowledge.
8. Preserve independent package boundaries so EI Core adapters and EI Server lifecycle hooks can be added later.
9. Do not add a public open-source license, publish a package, or deploy services without explicit approval.
10. Maintain high testability; use deterministic clocks, fake providers and offline fixtures.

## Suggested repository layout

```text
src/ei_context/
    __init__.py
    models.py
    errors.py
    protocols.py
    engine.py
    retrieval/{ranking,assembly,dedup}.py
    memory/{manager,sqlite}.py
    providers/{fixtures,memory}.py
    lifecycle/events.py
tests/{unit,integration,security}/
examples/offline_resume.py
docs/
.github/workflows/ci.yml
pyproject.toml
README.md
```

Worker may choose equivalent sensible module boundaries. Keep public imports predictable and document API decisions.

## Implementation prompts by phase

**PR 1:** Create a package scaffold and CI. Confirm `pip install -e ".[dev]"`, tests, lint and static checks run. No real adapters.

**PR 2:** Implement models and protocols with two fake providers. Add scope checks, provenance, typed errors and tests for access violation.

**PR 3:** Implement SQLite MemoryStore, schema migrations, FTS search or fallback, revision-aware updates, supersession, invalidation and deletion. Test fresh-process continuity and negative access cases.

**PR 4:** Implement ContextEngine retrieval, bounded fan-out, ranking, deduplication, budgeted assembly, source references, stale/partial-results warnings and prompt-injection framing. Include deterministic fixtures and quality evaluation script.

**PR 5:** Implement explicit memory events/proposals, end-to-end two-session example and adapter guide for EI Server/Core. Validate acceptance tests, README and security cases.

## Expected deliverables

- Working code on feature branches and a reviewable series of PRs.
- Typed API with docstrings, tests and minimal examples.
- Local README install/run instructions.
- Explicit compatibility contract for EI Core provider and EI Server lifecycle hooks.
- A synthetic benchmark/evaluation report noting methodology and limitations.
- Release checklist showing passes/failures against the implementation plan.

## Scope control

If uncertain whether a feature belongs in EI Context, use this test:

- **Does it decide what context is relevant, safe, current, remembered or assembled?** In scope.
- **Does it perform a domain-specific engineering check/search?** Existing EI Core/provider concern; add only a protocol/fixture.
- **Does it select tools, call LLM repeatedly, orchestrate runs or checkpoint the agent?** EI Server concern; expose hooks only.
- **Does it manage the human developer workspace or navigation?** Teammate's separate project; out of scope.

## First demonstration script (acceptance)

The script creates synthetic reference documents and a synthetic workstream, commits a decision and an unsuccessful approach, reopens persisted state using a new context engine instance, then constructs a response bundle including:
- the chosen approach;
- why the alternative was rejected;
- the source references;
- one open question; and
- warnings where supporting evidence is stale or missing.

It must demonstrate that unrelated actor/tenant queries do not disclose private information. Include assertions so the demo can serve as an integration test.

## Reporting format after each PR

Report: **Implemented | Tests run (exact commands/results) | Acceptance conditions met | Security considerations | Open questions | Next PR**. Do not claim an unrun test passed. Do not silently broaden scope.

Do not wait for unavailable EI Stack source; the goal is to finish a useful independent package today and attach EI adapters later.
