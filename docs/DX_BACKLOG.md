# Developer Experience Opportunity Backlog

Purpose: preserve the broader set of real developer/agent pain points identified during EI planning. **Not all are EI Context features** and priority is hypothesis, not commitment. Do not expand MVP indiscriminately.

| Priority | Pain point | Opportunity | Likely owner |
|---|---|---|---|
| P0 | Cross-session context loss | Durable decisions, outcomes, open questions, evidence-backed retrieval | EI Context |
| P0 | Fragmented internal API and technical knowledge | Unified evidence contracts, existing source adapters, context-appropriate retrieval | EI Core + EI Context |
| P0 | Irrelevant or overwhelming context | Ranking, deduplication, context budgets, relevance and traceability | EI Context |
| P1 | Repeating earlier mistakes | Recover failed attempts, rationale, test failures, decisions | EI Context |
| P1 | Cross-agent context inconsistency | Shared context API/memory with explicit integrations and scopes | EI Context |
| P1 | Cross-repository task context | Workstream-centric context links across source IDs and repos | EI Context; task model external |
| P1 | PR review missing original rationale | Link reviewed changes with requirements, decisions and technical evidence | EI Core/Context; UI external |
| P1 | Downstream change-impact discovery | Source-backed service/dependency relationships and impact queries | EI Core + Context |
| P2 | Parallel agent work visibility | Agent events/status and handoffs exposed to workspace | EI Server + teammate workspace |
| P2 | Outdated technical docs | Detect drift against verified current source, suggest updates | EI Core + Context |
| Separate | Tool/window switching | Consolidated workspace for tasks/PRs/IDE/chat | Teammate's workspace |

## Interpretation

### Distinct from teammate's project
Teammate owns developer-facing *workflow consolidation*: tasks, dashboards, PR visibility, grouped chats, IDE interactions, agent status navigation.

EI Context owns *knowledge and continuity*: what sources matter, what happened before, what evidence supports a decision, what should be remembered, what has changed or become stale.

Cooperation is via portable structured ContextBundles, memory APIs and provenance links, NOT duplication of the workspace.

### Candidate research experiments
1. **Session reset**: new session can reconstruct a prior decision and unresolved issue.
2. **Stale source**: changing a technical source forces a warning/review rather than repeating an obsolete fact.
3. **Review context**: source/decision evidence improves reviewers' ability to spot a regression.
4. **Parallel work**: can conflicting agent findings be surfaced without introducing a second workflow UI?
5. **Cross-repository**: can a workstream search assemble evidence across repos without indexing private data globally?
6. **Noise and cost**: rank retrieved evidence under a strict context budget; quantify irrelevant-result reduction.

## Backlog hygiene

- Capture each issue with an actual developer story, current workaround, measurable friction and testable hypothesis before implementation.
- Validate with real (appropriately approved) developers and anonymised benchmarks, not popularity alone.
- Preserve separate product ownership and architecture boundaries.
- Keep next-release work narrowed to P0, with P1 as justified extensions.
