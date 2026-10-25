"""Bounded retrieval coordination, never an agent/model/tool loop."""

import asyncio
import math
from collections.abc import Callable, Sequence
from datetime import datetime

from pydantic import ValidationError

from ei_context.errors import InvalidMemory
from ei_context.lifecycle.events import ContextEvent
from ei_context.memory.manager import MemoryManager
from ei_context.models import (
    AccessScope,
    ApprovalEvidence,
    ContextBundle,
    ContextRequest,
    Evidence,
    MemoryCandidate,
    MemoryKind,
    MemoryRecord,
    MemoryState,
    utc_now,
)
from ei_context.policy import AccessPolicy
from ei_context.protocols import ContextProvider, Ranker, TokenCounter
from ei_context.retrieval.assembler import ApproximateTokenCounter, assemble
from ei_context.retrieval.dedup import deduplicate
from ei_context.retrieval.ranking import LexicalRanker


class ContextEngine:
    """Stateless, deterministic assembly for frozen inputs, policies and clocks.

    Providers must enforce native ACLs before semantic processing. The engine adds
    defence-in-depth checks before deduplication, ranking or optional remote calls.
    No bundle cache is retained: refresh always rechecks current grants and sources.
    """

    def __init__(
        self,
        providers: Sequence[ContextProvider],
        *,
        policy: AccessPolicy | None = None,
        token_counter: TokenCounter | None = None,
        ranker: Ranker | None = None,
        clock: Callable[[], datetime] = utc_now,
        max_concurrency: int = 4,
        provider_timeout: float = 2.0,
        provider_limit: int = 100,
        memory_manager: MemoryManager | None = None,
    ) -> None:
        if not 1 <= max_concurrency <= 32 or not 0 < provider_timeout <= 60:
            raise ValueError("invalid concurrency or timeout")
        if not 0 < provider_limit <= 1000 or len(providers) > 32:
            raise ValueError("invalid provider count or candidate limit")
        ids = [p.provider_id for p in providers]
        if len(set(ids)) != len(ids):
            raise ValueError("provider IDs must be unique")
        self.providers = tuple(providers)
        self.memory_manager = memory_manager
        self.policy = policy or AccessPolicy()
        self.counter = token_counter or ApproximateTokenCounter()
        self.ranker = ranker or LexicalRanker(clock=clock)
        self._clock = clock
        self._max_concurrency = max_concurrency
        self._timeout = provider_timeout
        self._provider_limit = provider_limit

    async def prepare(self, request: ContextRequest) -> ContextBundle:
        request = ContextRequest.model_validate(request)
        self.policy.validate_scope(request.scope)
        gate = asyncio.Semaphore(self._max_concurrency)
        enabled = [
            p
            for p in self.providers
            if request.provider_ids is None or p.provider_id in request.provider_ids
        ]
        warnings: list[str] = []
        if request.provider_ids is not None and set(request.provider_ids) - {
            p.provider_id for p in enabled
        }:
            warnings.append("requested provider is not registered")

        async def query_provider(provider: ContextProvider) -> tuple[list[Evidence], list[str]]:
            async with gate:
                try:
                    results = await asyncio.wait_for(
                        provider.search(
                            request.query,
                            scope=request.scope,
                            workstream=request.workstream,
                            limit=self._provider_limit,
                        ),
                        timeout=self._timeout,
                    )
                    local_warnings = []
                    if len(results) > self._provider_limit:
                        local_warnings.append(
                            f"provider {provider.provider_id}: result limit enforced"
                        )
                    safe = []
                    for raw in results[: self._provider_limit]:
                        try:
                            item = Evidence.model_validate(raw)
                            # Do not send unauthorised text even to a pluggable ranker.
                            if not self.policy.evidence_allowed(item, request.scope):
                                local_warnings.append(
                                    f"provider {provider.provider_id}: inaccessible result rejected"
                                )
                                continue
                            ids = {r.source_id for r in (item.source, *item.source_refs)}
                            if ids & request.excluded_source_ids:
                                continue
                            safe.append(item.model_copy(deep=True))
                        except (ValidationError, TypeError):
                            local_warnings.append(
                                f"provider {provider.provider_id}: malformed result rejected"
                            )
                    return safe, local_warnings
                except TimeoutError:
                    return [], [f"provider {provider.provider_id}: timeout; partial results"]
                except Exception:
                    # No exception details: upstream messages may contain private source text.
                    return [], [f"provider {provider.provider_id}: unavailable; partial results"]

        results = await asyncio.gather(*(query_provider(provider) for provider in enabled))
        evidence: list[Evidence] = []
        for items, diagnostics in results:
            evidence.extend(items)
            warnings.extend(diagnostics)
        total = len(evidence)
        unique = deduplicate(evidence)
        caveats = self._caveats(unique)
        # Freeze authoritative snapshots before invoking a replaceable ranker.
        originals = {e.id: e.model_copy(deep=True) for e in unique}
        if len(originals) != len(unique):
            raise ValueError("providers returned colliding evidence IDs")
        ranked = self.ranker.rank(
            request.query, [e.model_copy(deep=True) for e in unique], workstream=request.workstream
        )
        checked = []
        seen: set[str] = set()
        for item, score, reason in ranked:
            if item.id not in originals or item.id in seen or item != originals[item.id]:
                raise ValueError("ranker must return only unchanged authorised evidence")
            if not math.isfinite(score):
                raise ValueError("ranker scores must be finite")
            seen.add(item.id)
            notes = caveats.get(item.id, ())
            # Explicit stale/mismatched provenance loses priority to current source evidence.
            penalty = (
                5.0
                if any(
                    "expired" in n or "differs" in n or "older" in n or "inactive" in n
                    for n in notes
                )
                else 0.0
            )
            checked.append(
                (
                    originals[item.id],
                    score - penalty,
                    reason + ("; caveats=" + "; ".join(notes) if notes else ""),
                )
            )
        checked.sort(key=lambda row: (-row[1], row[0].source.provider, row[0].id))
        for notes in caveats.values():
            warnings.extend(notes)
        return assemble(
            request,
            checked,
            counter=self.counter,
            warnings=warnings,
            caveats=caveats,
            total_candidates=total,
        )

    def _caveats(self, evidence: Sequence[Evidence]) -> dict[str, tuple[str, ...]]:
        now = self._clock()
        sources: dict[tuple[str, str], list[Evidence]] = {}
        for e in evidence:
            if e.memory_kind is None:
                sources.setdefault((e.source.provider, e.source.source_id), []).append(e)
        result: dict[str, tuple[str, ...]] = {}
        for e in evidence:
            notes: list[str] = []
            if e.trust_label == "unverified":
                notes.append("unverified source statement")
            if e.source.version is None:
                notes.append("source version unknown")
            if any(
                expiry is not None and expiry <= now
                for expiry in (e.valid_until, e.source.valid_until)
            ):
                notes.append("expired evidence; historical context only")
            if e.memory_status is not None and e.memory_status != MemoryState.ACTIVE:
                notes.append("inactive memory; historical context only")
            if e.memory_kind is not None:
                for ref in e.source_refs:
                    current = sources.get((ref.provider, ref.source_id), [])
                    if not current:
                        notes.append(
                            "supporting evidence missing from this retrieval; "
                            "not independently verified"
                        )
                    elif ref.version is None:
                        notes.append("memory supporting version unknown; review provenance")
                    elif not any(s.source.version == ref.version for s in current):
                        notes.append(
                            "supporting source version differs; "
                            "review memory against current evidence"
                        )
                    matching = [s for s in current if s.source.version == ref.version]
                    if matching and any(
                        old.source.modified_at is not None
                        and other.source.modified_at is not None
                        and other.source.modified_at > old.source.modified_at
                        and other.source.version != old.source.version
                        for old in matching
                        for other in current
                    ):
                        notes.append(
                            "supporting source version differs from latest snapshot; review memory"
                        )
                    if ref.valid_until is not None and ref.valid_until <= now:
                        notes.append("supporting evidence expired; review memory")
            else:
                versions = sources[(e.source.provider, e.source.source_id)]
                if any(other.source.version != e.source.version for other in versions):
                    if e.source.modified_at is not None and any(
                        other.source.modified_at is not None
                        and other.source.modified_at > e.source.modified_at
                        for other in versions
                    ):
                        notes.append("older source snapshot; prefer current evidence")
                    else:
                        notes.append("multiple source versions; verify authoritative version")
            if (
                e.memory_kind == MemoryKind.DECISION
                and e.memory_status == MemoryState.ACTIVE
                and any(
                    other.id != e.id
                    and other.memory_kind == MemoryKind.DECISION
                    and other.memory_status == MemoryState.ACTIVE
                    and other.workstream == e.workstream
                    and other.text != e.text
                    for other in evidence
                )
            ):
                notes.append("multiple active decision statements; review potential conflict")
            result[e.id] = tuple(sorted(set(notes)))
        return result

    async def refresh(
        self, request: ContextRequest, previous_bundle: ContextBundle | None = None
    ) -> ContextBundle:
        """Recompute with current permissions; previous bundles confer no access or cache rights."""
        return await self.prepare(request)

    async def observe(self, event: ContextEvent, *, scope: AccessScope) -> list[MemoryCandidate]:
        """Propose only; never persist on a tool result or model guess."""
        if self.memory_manager is None:
            raise InvalidMemory("a memory manager is required for lifecycle operations")
        return await self.memory_manager.propose_from_event(event, scope=scope)

    async def distill(
        self, events: Sequence[ContextEvent], *, scope: AccessScope
    ) -> list[MemoryCandidate]:
        if self.memory_manager is None:
            raise InvalidMemory("a memory manager is required for lifecycle operations")
        return await self.memory_manager.distill(events, scope=scope)

    async def commit_memory(
        self, candidate: MemoryCandidate, *, scope: AccessScope, approval: ApprovalEvidence
    ) -> MemoryRecord:
        if self.memory_manager is None:
            raise InvalidMemory("a memory manager is required for lifecycle operations")
        return await self.memory_manager.commit(candidate, scope=scope, approval=approval)

    async def close(self) -> None:
        """Close the explicitly attached memory manager's store; providers remain host-owned."""
        if self.memory_manager is not None:
            await self.memory_manager.store.close()
