"""Deterministic lexical ranking with visible, bounded non-semantic signals."""

from collections.abc import Callable, Sequence
from datetime import datetime

from ei_context.models import Evidence, MemoryKind, WorkstreamRef, utc_now
from ei_context.providers.fixtures import terms


class LexicalRanker:
    def __init__(self, *, clock: Callable[[], datetime] = utc_now) -> None:
        self._clock = clock

    def rank(
        self, query: str, evidence: Sequence[Evidence], *, workstream: WorkstreamRef | None
    ) -> list[tuple[Evidence, float, str]]:
        query_terms = terms(query)
        results = []
        now = self._clock()
        for item in evidence:
            overlap = len(query_terms & terms(item.text)) / max(1, len(query_terms))
            same_workstream = workstream is not None and item.workstream == workstream
            quality = {"unverified": 0.0, "user_confirmed": 0.3, "system_verified": 1.0}[
                item.trust_label
            ]
            important = item.memory_kind in {
                MemoryKind.DECISION,
                MemoryKind.ATTEMPT,
                MemoryKind.OPEN_QUESTION,
            }
            modified = item.source.modified_at
            recency = (
                0.0 if modified is None else max(0.0, 1 - max(0, (now - modified).days) / 365) * 0.5
            )
            score = (
                overlap * 5 + int(same_workstream) * 2 + quality + int(important) * 0.5 + recency
            )
            reason = (
                f"lexical={overlap:.3f}; workstream={same_workstream}; "
                f"trust={item.trust_label}; recency={recency:.3f}"
            )
            results.append((item, score, reason))
        return sorted(results, key=lambda row: (-row[1], row[0].source.provider, row[0].id))
