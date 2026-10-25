"""Reproducible synthetic relevance/latency measurements; no baseline improvement claim."""

import asyncio
import json
import platform
import statistics
import time
from datetime import UTC, datetime

from ei_context import AccessScope, ContextEngine, ContextRequest, Evidence, SourceRef
from ei_context.providers import InMemoryProvider


async def evaluate() -> dict[str, object]:
    now = datetime(2026, 1, 2, tzinfo=UTC)
    scope = AccessScope(tenant_id="demo", actor_id="alice")
    topics = {
        "route": "NewRoute ledger calculation stable IDs",
        "legacy": "LegacyRoute incompatible unsigned balance rejected",
        "retry": "Retry policy transient failures bounded exponential backoff",
        "auth": "Authentication ledger token audience validation",
        "schema": "Schema evolution ledger version compatibility",
        "question": "Open question ledger rounding reconciliation test",
    }
    docs = [
        Evidence(
            id=k,
            text=v,
            source=SourceRef(
                provider="eval", source_id=k, version="1", retrieved_at=now, modified_at=now
            ),
            tenant_id="demo",
            access_principals={"actor:alice"},
            trust_label="system_verified",
        )
        for k, v in topics.items()
    ]
    docs += [
        Evidence(
            id=f"noise-{i}",
            text=f"Unrelated gardening specimen {i}",
            source=SourceRef(
                provider="eval", source_id=f"noise-{i}", version="1", retrieved_at=now
            ),
            tenant_id="demo",
            access_principals={"actor:alice"},
        )
        for i in range(30)
    ]
    engine = ContextEngine([InMemoryProvider("eval", docs)], clock=lambda: now)
    cases = [
        ("NewRoute stable IDs", {"route"}),
        ("LegacyRoute incompatible", {"legacy"}),
        ("retry transient backoff", {"retry"}),
        ("authentication audience", {"auth"}),
        ("schema evolution compatibility", {"schema"}),
        ("rounding reconciliation", {"question"}),
    ]
    precision, recall, latency, citations, budget = [], [], [], [], []
    for _ in range(20):
        for query, expected in cases:
            started = time.perf_counter()
            bundle = await engine.prepare(
                ContextRequest(query=query, scope=scope, max_items=2, token_budget=4000)
            )
            latency.append((time.perf_counter() - started) * 1000)
            ids = {s.evidence_id for s in bundle.selected}
            precision.append(len(ids & expected) / max(1, len(ids)))
            recall.append(len(ids & expected) / len(expected))
            citations.append(all(s.source.source_id and s.citation for s in bundle.selected))
            budget.append(bundle.estimated_tokens <= 4000 and len(bundle.selected) <= 2)
    bob = await engine.prepare(
        ContextRequest(query="ledger", scope=AccessScope(tenant_id="demo", actor_id="bob"))
    )
    return {
        "python": platform.python_version(),
        "dataset": "36 synthetic docs, 6 labelled queries x 20 repeats",
        "precision_at_2": statistics.mean(precision),
        "recall_at_2": statistics.mean(recall),
        "citation_coverage": statistics.mean(citations),
        "budget_adherence": statistics.mean(budget),
        "latency_ms_p50": statistics.median(latency),
        "latency_ms_p95": sorted(latency)[int(len(latency) * 0.95) - 1],
        "actor_leakage_count": len(bob.selected),
        "unsupported_memory_rate": None,
        "limitations": (
            "Small lexical fixtures; no real data, embeddings, human judgement or baseline. "
            "Unsupported-memory rate not measured here; lifecycle suite covers memory."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(evaluate()), indent=2))
