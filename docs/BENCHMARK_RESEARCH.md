# Research-backed evaluation of EI Context (2026-10-25)

**Status:** research protocol and recommendations, NOT measured EI Context task-improvement results.  
**Related:** [Task evaluation #11](https://github.com/hanqi-zhou/ei-context/issues/11), [DESIGN](DESIGN.md), [Existing offline evaluation](EVALUATION.md).

## Executive recommendation

For EI Context's actual product claim — *agents reuse relevant past engineering experience to finish later tasks correctly, faster and at lower total cost* — **start with SWE-ContextBench Lite**, complemented by a small custom cross-session continuity set, and use **ContextBench** to diagnose retrieval quality. Add **LongMemEval / MemoryAgentBench / MemoryArena** for memory semantics and multi-session action. SWE-bench Verified, SWE-bench Pro V2 and Terminal-Bench are valuable downstream transfer tests, but ordinary one-shot benchmark tasks do not measure cross-session memory improvements by themselves.

Do **not** take the current 36-document / 6-query 100% lexical recall result as evidence of agent efficiency. It is a functionality smoke test.

## Verified public benchmarks, relevant scopes and limits

| Benchmark | Official reference | What it tests | EI Context suitability |
|---|---|---|---|
| **SWE-ContextBench** (2026; paper v3) | Paper https://arxiv.org/abs/2602.08316 ; code https://github.com/jiayuanz3/SWEContextBench ; data https://huggingface.co/datasets/jiayuanz3/SWEContextBench | Reuse of prior agent experience between related GitHub issue tasks; success, tool calls, latency, tokens, costs. Paper reports 1,100 base / 376 related tasks in 51 repos/9 languages; **Lite 300 base + 99 related Python tasks**. | **First choice:** directly tests cross-task context reuse and efficiency. Use Lite for pilot; attach EI memory to base trajectories and retrieve for related task. |
| **ContextBench** (2026) | https://contextbench.github.io/ ; paper https://arxiv.org/abs/2602.05892 | 1,136 coding issue tasks, 66 repos/8 languages with human-annotated relevant code context, trajectory-level retrieval recall, precision, F1, agent outcomes and costs. | **First-choice retrieval diagnostic:** do we find the right code regions or waste tokens on noise? Does retrieval get used? Does not itself impose cross-session memories. |
| **MemoryArena** (ICML 2026) | https://memoryarena.github.io/ ; paper https://proceedings.mlr.press/v306/he26am.html | Interdependent sequential tasks where earlier environment actions and feedback must be remembered for later action. Domains include web navigation, planning, progressive search and formal reasoning. | **First-choice multi-session action diagnostic**, but non-coding; useful to validate genuine memory-assisted agency beyond QA. |
| **LongMemEval** (ICLR 2025) | https://proceedings.iclr.cc/paper_files/paper/2025/hash/d813d324dbf0598bbdc9c8e79740ed01-Abstract-Conference.html ; code https://github.com/xiaowu0162/LongMemEval | 500 questions targeting extraction, multi-session reasoning, temporal reasoning, updates and abstention. | Memory correctness regression suite; *not* proof of code-task outcomes. |
| **MemoryAgentBench** (2025/2026) | https://arxiv.org/abs/2507.05257 ; code https://github.com/HUST-AI-HYZ/MemoryAgentBench | Incremental multi-turn memory: accurate retrieval, test-time learning, long-range understanding, selective forgetting. | Memory extraction/retrieval/updating/forgetting quality; not direct code completion. |
| **LoCoMo** (2024) | https://github.com/snap-research/locomo | Long conversational histories, retrieval and reasoning across up to dozens of sessions. | Historical conversation-memory baseline; can be 'gamed' through simple QA patterns, so complement with action tasks. |
| **SWE-bench Verified** | https://www.swebench.com/verified.html | 500 expert-validated issue-resolution tasks; git base commit, patch, execution tests. | Good coding-control harness; needs *added* prior-session histories and related tasks to assess EI Context. |
| **SWE-bench Pro V2** (2026-09-22) | https://labs.scale.com/leaderboard/swe_bench_pro_public_v2 ; https://github.com/scaleapi/SWE-bench_Pro-os | 642 harder public issue tasks, 11 repos, stricter test validity and clean re-grading. | Robust later transfer test; heavier; baseline is not inherently memory-sensitive. |
| **Terminal-Bench 2.0** | https://www.tbench.ai/ | Isolated command-line environment tasks, test-scored execution and agent-model pair comparisons. | Useful for execution efficiency and long workflows; not inherently a multi-session memory evaluation. |
| **SWE-Lancer** | https://openai.com/index/swe-lancer/ | >1,400 real freelancing engineering/managerial tasks, scored by implementation tests or original managers' decisions. | Economic-task relevance, but engineering decisions not specifically prior-memory; adapt carefully. |

**Versioning caveat:** SWE-ContextBench's GitHub README and latest paper/dataset summary expose differing task counts (README retains an older number). Pin a specific GitHub commit, dataset revision, and paper version. Do not silently mix instances/splits or reference numbers across revisions.

## Why SWE-ContextBench is an unusually good fit

The v3 paper explicitly tests No-Context, Free Context, Oracle Context, Free Summary, and Oracle Summary strategies. The 99-task Lite experiment reports task-resolution rates:
- **No Context:** 26.26%;
- **Free Context:** 26.26%;
- **Oracle Context:** 27.27%;
- **Free Summary:** 22.22%;
- **Oracle Summary:** 34.34%.

These are *published paper results for its particular agent setup*, not EI Context results, and do not imply that EI Context will improve outcomes. The negative results for free retrieval matter: irrelevant/misselected context can **harm success or cost**. The benchmark also reports time, tool calls, tokens, API cost and regression tests, making it better matched to our claim than simple recall.

Source: https://arxiv.org/html/2602.08316v3 (Sections 3.2/3.3).

## Experimental hypotheses (preregister before running)

- **H1 / primary:** EI Context increases task-level hidden-test resolution compared with identical agent/model tools running without memory.
- **H2:** EI Context outperforms an equal-budget manually prepared prior-session handoff on the *same tasks*.
- **H3:** EI Context reduces repeated failed approaches/tool calls and total model tokens per resolved task.
- **H4 / no-harm:** irrelevant or stale memories do not significantly worsen task outcomes; access-control and source-provenance constraints hold.
- **H5 / storage:** retrieval quality and p95 context latency remain acceptable with growing scoped memory stores and concurrent users.

Report negative/null findings.

## Conditions and ablations

Use fixed agent runner and identical model, model version, sampling/effort, budget, executable tools, source snapshots and base commit for ALL conditions. Memory writing/loading is the independent variable.

A. **No memory:** fresh Session B with task spec/repo and current accessible documentation only.

B. **Manual summary, budget-matched:** concise human or controlled model summary of Session A. Same maximum context tokens as EI retrieval arm; include prep cost.

C. **EI Context — oracle populated:** pre-approved structured memory from Session A (separates retrieval/context assembly from extraction). Host injects `ContextBundle` into the same runtime.

D. **EI Context — end to end:** capture Session A events, stage candidate memories, require appropriate approvals, persist in SQLite, then retrieve in a new process and execute Session B. Count extraction and approval costs.

E. **Oracle prior memory** *(diagnostic ceiling)*: gold relevant previous facts and references, still no future answer or hidden test leakage.

Optional baseline **BM25/raw transcript retrieval** to determine whether EI's curated memory beats a trivial search solution.

**Critical controls:** No future task fixes, ground-truth patch, hidden test content, leaked git history, or solution-bearing hints enter the earlier memory pool. Memory acquisition must only use evidence available before the Session B boundary. Re-grade final patches on pristine isolated environments. Track any change in historical docs vs current docs. Human summaries should not be disproportionately polished relative to machine memories.

## Evaluation stages (cost-aware)

1. **Offline unit and memory suites:** LongMemEval-style synthetic/selected cases for version changes, temporal updates, abstention, contradictions, privacy and provider-id collisions; deterministic scorer, no model required.
2. **Pilot:** SWE-ContextBench Lite, start 5–10 preselected related tasks, with their corresponding experience cases; compare A/B/C/E on a *single pinned coding agent/model*. Three repeated trials per condition where budget allows. Document selected tasks, not hand-picked successes.
3. **Primary evaluation:** stratified fixed subset of 30–50 related tasks from Lite; track statistical uncertainty; optionally all 99. Include hard/noisy examples and negative-transfer scenarios. Three repeats per cell; isolate base commits and process/session state.
4. **Deeper retrieval diagnostic:** sample ContextBench (e.g. 30–100 tasks) with gold code regions, evaluate ranked context recall, precision, F1, context token waste and final task outcomes. Ensure original code is accessible identically to all arms.
5. **Generality:** limited MemoryArena or LongMemEval/MemoryAgentBench subset; later SWE-bench Pro V2/Terminal-Bench where a real historical-context setup exists.
6. **Approved private shadow evaluation (later):** realistic enterprise tasks with correct permissions, not in public repository. No internal data through external model providers without approval.

## Metrics and instrumentation

### Primary
**Task resolution rate** = fully accepted patches / attempted tasks, verified by hidden FAIL_TO_PASS and PASS_TO_PASS tests in a clean environment; task-specific acceptance and independent regression suite. Prefer pass@1 with 3+ repeated independent attempts; partial test score is secondary.

### Secondary effectiveness
- Prior approach repeats (# of reinventions of known-bad approach).
- Action/tool count, tests executed, patches applied, wrong files edited.
- Proper use of evidence; unsupported claims; stale incorrect decisions.
- Memory accuracy: decision extraction recall/precision, temporal update correctness, citation validity, abstention when unavailable.
- Security failures and cross-tenant/membership/source visibility violations (must remain zero in negative tests).

### Efficiency
- Wall-clock end-to-end time and *time to accepted solution*; p50/p95 and timeouts/censored trials.
- Provider query cost/latency, memory extraction/ingestion time and cost, context assembly time.
- Input, output, cached-input, cache-write tokens; count search and context-prep model calls. Context reading is not free.
- $ total per task, **$ per successful task**, tokens per success. Report successes and failures separately to avoid survivorship bias.
- Context tokens returned, distinct relevant evidence, wasted/duplicate tokens, retrieved vs used context.

**Do not use raw wall-time alone** to decide value; improve task resolution at bounded cost/time first. Measure interactions per correct solution and negative transfers.

### Aggregation
Use paired comparisons at the **task level** to remove difficulty confounding. Randomise arm order across runs, seeds and tasks. Cluster bootstrap confidence intervals over task IDs (not repeated runs treated as independent). Provide absolute percentage-point gains, relative change with denominators, and transparent raw JSONL. Pin prompt templates, dataset revision, exact agent harness, base commits, model and tool versions.

## Data schema (recommendation)

```json
{
  "task_id": "swe-context-lite-example",
  "dataset_revision": "<pinned-revision>",
  "prior_task_ids": ["related-base-1"],
  "base_commit": "<git-sha>",
  "condition": "no_memory|manual|ei_oracle_ingest|ei_e2e|oracle",
  "model_id": "<exact-version>",
  "agent_harness": "<commit>",
  "trial": 1,
  "seed": 123,
  "resolved": false,
  "fail_to_pass": 0.0,
  "pass_to_pass": 1.0,
  "wall_seconds": 0.0,
  "input_tokens": 0,
  "cached_tokens": 0,
  "output_tokens": 0,
  "context_tokens": 0,
  "model_cost_usd": 0.0,
  "context_cost_usd": 0.0,
  "tool_calls": 0,
  "memory_evidence_ids": [],
  "retrieval_recall_at_k": null,
  "retrieval_precision_at_k": null,
  "source_version_warnings": [],
  "security_violations": 0,
  "patch_sha256": null
}
```

No sensitive prompt/source text in default metrics. Persist richer trajectories only in explicit restricted test artifacts, never real private sessions in public CI logs.

## Implementation boundary

`ei_context` exports memory/retrieval APIs. The evaluation runner may call external coding agents in a separate `experiments/` directory or companion repo. **It must not add an agent loop, task dashboard, or UI to the installable library.**

Suggested:
- `experiments/datasets/swe_contextbench_adapter.py` — pinned benchmark cases and related prior-task mapping;
- `experiments/agents/runner_protocol.py` — abstract runner, optional mini-SWE-agent/approved-model adapters;
- `experiments/arms.py` — baseline/handoff/EI/ceiling strategies;
- `experiments/score.py` — isolated patch testing + outcome/efficiency stats;
- `experiments/analyse.py` — paired effects, plots/summary, CIs;
- `experiments/smoke/` — offline fake runner for CI.

## Immediate Worker deliverable

Before spending on LLM inference, implement a **read-only benchmark adapter** for SWE-ContextBench Lite and a 5-task pilot plan, verifying dataset schema, license, images and availability, with a no-network smoke harness. Demonstrate that A/B/C arms receive identically sourced task information and clean isolated checkouts; only context differs. Once approved model credentials/budget are available, run the paired agent evaluation and publish measured results with limitations. The evaluation harness is not part of the EI Context runtime.

## Further research/links

- ContextBench process-level evaluation: https://contextbench.github.io/ and https://arxiv.org/abs/2602.05892
- MemoryArena: https://proceedings.mlr.press/v306/he26am.html
- LongMemEval (ICLR 2025): https://github.com/xiaowu0162/LongMemEval
- MemoryAgentBench: https://github.com/HUST-AI-HYZ/MemoryAgentBench
- SWE-bench Pro V2 benchmark validity controls: https://labs.scale.com/leaderboard/swe_bench_pro_public_v2
- AI coding agent cost measurement methodology: https://artificialanalysis.ai/methodology/coding-agents-benchmarking
- Microsoft Research study of token consumption / variability: https://www.microsoft.com/en-us/research/publication/how-do-ai-agents-spend-your-money-analyzing-and-predicting-token-consumption-in-agentic-coding-tasks/
