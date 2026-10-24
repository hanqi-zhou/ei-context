# ADR 0001 — EI Context as a standalone library

**Date:** 2026-10-24
**Status:** Accepted for initial implementation
**Context:** Other EI Stack modules are complete but on another machine and their source/contracts are not currently available. Need to progress context engineering without duplicating a teammate's workspace or EI Server agent loop.

## Decision
1. Create an independent installable `ei-context` Python distribution in its own repository.
2. Make it source- and agent-framework agnostic; no required imports from other EI packages.
3. Implement evidence retrieval coordination, provenance, scoped persistent work memory, ranking, context assembly and memory lifecycle.
4. Use EI Server later as optional *caller* to trigger lifecycle operations. EI Server continues to own agent runs, LLM/tool loops, checkpoints, execution retries and scheduling.
5. Connect engineering-specific discovery tools through `ContextProvider` adapters; do not duplicate their implementations.
6. Build offline SQLite + synthetic fixtures first; a separate context service, PostgreSQL, hosted embeddings, graphs and model-assisted extraction are optional later decisions.

## Alternatives considered
- **Make EI Core larger**: least initial packaging overhead, but creates mixed engineering/domain and cross-agent memory responsibilities, heavier dependencies, harder independent use.
- **Put context inside EI Server**: integrates naturally with the loop but prevents standalone Python/MCP use and couples to a particular runtime.
- **Build a context microservice now**: allows remote reuse, but adds auth, operations, deployment and latency before demand is validated.
- **Create another integrated developer workspace**: overlaps teammate's focus and does not solve cross-agent knowledge reuse directly.

## Consequences
- Requires careful provider, identity, evidence and memory contracts.
- EI Context can be tested and released independently of EI Stack.
- EI Server lifecycle hooks remain explicit integration points, not a new scheduler.
- Production authorisation remains a host/source-backed responsibility plus mandatory context-level checks.
- Must maintain compatibility and avoid cyclic dependencies when EI source becomes available.

## Revisit when
- Multiple teams need remote multi-user context service with independent auth/scale;
- actual EI Core and EI Server code is available;
- benchmark evidence supports vector/graph infrastructure or new lifecycle hooks;
- scoped memory sharing requires a formal organisation policy.
