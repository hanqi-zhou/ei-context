"""Offline DEMO-42: two separate Python processes, one SQLite file, zero transcript transfer.

Run: python examples/offline_resume.py
Use --db PATH to keep a reusable synthetic DB; default cleans up a temporary DB.
"""

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ei_context import (
    AccessScope,
    ApprovalEvidence,
    ContextEngine,
    ContextEvent,
    ContextRequest,
    Evidence,
    MemoryCandidate,
    MemoryKind,
    MemoryManager,
    SourceRef,
    SQLiteMemoryStore,
    WorkstreamRef,
)
from ei_context.providers import FixtureProvider, InMemoryProvider
from ei_context.providers.memory import MemoryProvider

NOW = datetime(2026, 1, 2, tzinfo=UTC)
SCOPE = AccessScope(tenant_id="demo", actor_id="alice")
WORK = WorkstreamRef(external_id="DEMO-42")


def build_engine(path: str) -> ContextEngine:
    store = SQLiteMemoryStore(path, clock=lambda: NOW)
    tests = InMemoryProvider(
        "fixture-tests",
        [
            Evidence(
                id="ledger-failure",
                text=(
                    "LegacyRoute rejected: unsigned balance incompatible. "
                    "Rounding reconciliation test remains open."
                ),
                source=SourceRef(
                    provider="fixture-tests",
                    source_id="ledger-test",
                    version="1",
                    retrieved_at=NOW,
                    modified_at=NOW,
                    uri="https://example.invalid/tests/ledger",
                ),
                tenant_id="demo",
                access_principals={"actor:alice"},
                trust_label="system_verified",
                workstream=WORK,
            )
        ],
    )
    return ContextEngine(
        [FixtureProvider(), tests, MemoryProvider(store)],
        clock=lambda: NOW,
        memory_manager=MemoryManager(store),
    )


async def write_session(path: str) -> None:
    engine = build_engine(path)
    doc_ref = SourceRef(
        provider="fixture-docs",
        source_id="ledger-doc",
        version="1",
        retrieved_at=NOW,
        uri="https://example.invalid/ledger/v1",
    )
    failure_ref = SourceRef(
        provider="fixture-tests",
        source_id="ledger-test",
        version="1",
        retrieved_at=NOW,
        uri="https://example.invalid/tests/ledger",
    )
    # The decision refers to old docs intentionally: session 2 must warn about v2.
    candidates = [
        MemoryCandidate(
            kind=MemoryKind.DECISION,
            content="Choose NewRoute for DEMO-42 ledger calculation.",
            source_refs=(doc_ref,),
            workstream=WORK,
        ),
        MemoryCandidate(
            kind=MemoryKind.ATTEMPT,
            content="LegacyRoute rejected because unsigned balance is incompatible.",
            source_refs=(failure_ref,),
            workstream=WORK,
        ),
        MemoryCandidate(
            kind=MemoryKind.OPEN_QUESTION,
            content="Open question: resolve rounding reconciliation test failure.",
            source_refs=(failure_ref,),
            workstream=WORK,
        ),
    ]
    events = [
        ContextEvent(
            id=f"event:{i}",
            kind="user_confirmed_decision" if c.kind == MemoryKind.DECISION else "tool_result",
            tenant_id="demo",
            actor_id="alice",
            occurred_at=NOW,
            workstream=WORK,
            source_refs=c.source_refs,
            proposal=c,
        )
        for i, c in enumerate(candidates)
    ]
    proposed = await engine.distill(events, scope=SCOPE)
    assert engine.memory_manager is not None
    assert (
        not await engine.memory_manager.store.list(scope=SCOPE)
        or len(await engine.memory_manager.store.list(scope=SCOPE)) == 3
    )
    approval = ApprovalEvidence(
        actor_id="alice",
        method="user_confirmed",
        reference="demo:explicit-approval",
        approved_at=NOW,
    )
    for candidate in proposed:
        await engine.commit_memory(candidate, scope=SCOPE, approval=approval)
    await engine.close()
    print("Session A: committed decision, rejected attempt and open question; engine/store closed.")


async def resume_session(path: str) -> None:
    engine = build_engine(
        path
    )  # New objects and process; no prior transcript or candidate passed in.
    request = ContextRequest(
        query="Continue DEMO-42 ledger and explain why LegacyRoute was rejected",
        scope=SCOPE,
        workstream=WORK,
        token_budget=16000,
    )
    bundle = await engine.prepare(request)
    kinds = {s.memory_kind for s in bundle.selected}
    assert {MemoryKind.DECISION, MemoryKind.ATTEMPT, MemoryKind.OPEN_QUESTION} <= kinds
    assert "Choose NewRoute" in bundle.rendered_context
    assert "unsigned balance" in bundle.rendered_context
    assert "rounding reconciliation" in bundle.rendered_context
    assert all(s.citation and s.source.source_id for s in bundle.selected)
    assert any("version differs" in w for w in bundle.warnings)
    assert bundle.estimated_tokens <= request.token_budget
    for outsider in [
        AccessScope(tenant_id="demo", actor_id="bob"),
        AccessScope(tenant_id="other", actor_id="alice"),
    ]:
        hidden = await engine.prepare(request.model_copy(update={"scope": outsider}))
        assert hidden.selected == ()
        assert engine.memory_manager is not None
        assert json.loads(await engine.memory_manager.store.export(scope=outsider))["records"] == []
    await engine.close()
    print("Session B: recovered NewRoute, rejection rationale, sources and open question.")
    print("Access checks: unrelated actor and tenant receive no private evidence or memory.")
    print(bundle.rendered_context)
    print("Warnings:", json.dumps(bundle.warnings))
    print("OFFLINE CONTINUITY PASS")


def forbid_network(event: str, args: object) -> None:
    if event in {"socket.connect", "socket.getaddrinfo"}:
        raise RuntimeError("offline demo forbids outbound network")


def run_processes(path: str) -> None:
    script = str(Path(__file__).resolve())
    for session in ("write", "resume"):
        subprocess.run([sys.executable, script, "--session", session, "--db", path], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db")
    parser.add_argument("--session", choices=["write", "resume"])
    args = parser.parse_args()
    sys.addaudithook(forbid_network)
    if args.session:
        if not args.db:
            parser.error("--session requires --db")
        asyncio.run(write_session(args.db) if args.session == "write" else resume_session(args.db))
    elif args.db:
        run_processes(args.db)
    else:
        with tempfile.TemporaryDirectory(prefix="ei-context-demo-") as directory:
            run_processes(str(Path(directory) / "memory.sqlite"))


if __name__ == "__main__":
    main()
