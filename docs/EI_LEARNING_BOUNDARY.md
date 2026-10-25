# EI Context boundaries with EI Learning

**Date:** 2026-10-25 | **Status:** cross-repository implementation coordination.

**EI Context owns trusted, appropriately scoped and provenance-backed prior information. EI Learning studies how observable experiences should change future agent behaviour.** These are separate responsibilities.

| Aspect | EI Context | EI Learning |
|---|---|---|
| Public API and package | Installable Python context/memory library | Standalone research code/harness; no dependency imposed on Context |
| Data | Source evidence, authored/approved work memory, revisions, validation/invalidation, permissions | Task outcomes, feedback, learning hypotheses, policies and experimental results |
| Retrieval | Candidate discovery, scope filtering, citations, context assembly and budgets | Tests what retrieved context caused an agent to do |
| Learning | May store a validated, approved strategy artifact in future; does not invent policies | Proposes, learns, evaluates, compares and retires strategies from feedback |
| Performance | Scoped retrieval correctness, storage latency, security, budget | End-to-end task success, transfer, interference, adaptation, token/cost effectiveness |
| Agent lifecycle | Exposes prepare/refresh/propose/commit APIs | Experimental runner is permitted; production loop belongs to EI Server |

## Integration rule

**Dependency direction:** EI Learning may optionally call EI Context through a pinned, public API adapter; EI Context MUST NOT import EI Learning. The adapter should first live in `ei-learning/experiments/adapters/`. No duplication of SQLite, access-policy, provenance, source version or memory retrieval logic.

Host provides authenticated scope and source-specific permissions; Context enforces access before exposing evidence to Learning or model components. Any learning-derived artifact must be treated as a **candidate**, not automatically authoritative or published. Host verification and explicit approved commit are required before durable shared memory updates.

Observations and verified results are different from causal explanations. Learning experiments must not read hidden evaluation tests or future task outcomes while choosing actions.

## Who owns evaluation?

- EI Context maintains **component** evaluation: relevant evidence retrieved, provenance, stale/conflicting source caveats, visibility safety, item/token budgets, query latency and memory persistence.
- EI Learning maintains **end-to-end agent-outcome** evaluation: test-scored task completion, generalisation on new tasks, learning overhead, time/tokens/tools, negative transfer and knowledge changes.
- Cross-project scenario: run a fixed agent with (A) no context; (B) handoff; (C) EI Context memory only; (D) EI Context evidence plus EI Learning adaptive strategy; (E) diagnostic oracle. Both teams contribute, but one harness/scorer (in Learning) avoids duplicated runtimes.

## Work coordination

1. Review and land Context PRs #6–#10; do not claim current main contains their implementation while they remain open.
2. Prioritise [provider-qualified source ACL #12](https://github.com/hanqi-zhou/ei-context/issues/12) and [memory provenance #13](https://github.com/hanqi-zhou/ei-context/issues/13) before any cross-provider real-data use. Other performance and decision-quality findings stay tracked.
3. Keep Context [evaluation issue #11](https://github.com/hanqi-zhou/ei-context/issues/11) as cross-project acceptance tracking and **Context-component** metrics; avoid building a second agent runner in this repo. The experiment implementation belongs in [EI Learning harness #3](https://github.com/hanqi-zhou/ei-learning/issues/3).
4. Once Learning has an offline scoring harness, implement an optional Context adapter, pin Context release SHA and prove scope/trajectory separation.
5. Add new reusable Context APIs only if an experiment demonstrates the need; document contract version and backward compatibility.

The EI Learning repository is private; its design note `docs/PROJECT_BOUNDARIES.md` provides the extended experimental contract. No real employer data belongs in public fixtures or documentation.
