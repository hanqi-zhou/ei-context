"""Local SQLite store. ACLs and source restrictions are SQL predicates, never post-redaction."""

import hashlib
import json
import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ei_context.errors import AccessDenied, InvalidMemory, RevisionConflict, StoreUnavailable
from ei_context.models import (
    AccessScope,
    ApprovalEvidence,
    MemoryCandidate,
    MemoryRecord,
    MemoryState,
    MemoryUpdate,
    Visibility,
    WorkstreamRef,
    utc_now,
)
from ei_context.policy import AccessPolicy
from ei_context.providers.fixtures import terms


class SQLiteMemoryStore:
    """Async API for bounded synchronous local transactions; no background tasks or caches.

    A connection belongs to its creating thread. Lock waits are limited to 100ms;
    hosts with high concurrency should implement the MemoryStore protocol remotely.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        policy: AccessPolicy | None = None,
        clock: Callable[[], datetime] = utc_now,
        use_fts: bool = True,
    ) -> None:
        self.policy = policy or AccessPolicy()
        self._clock = clock
        self._closed = False
        self._db = sqlite3.connect(str(path), timeout=0.1, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA secure_delete=ON")
        self._db.execute("PRAGMA temp_store=MEMORY")
        try:
            self._migrate()
            self.fts_available = use_fts and self._probe_fts()
        except Exception:
            self._db.close()
            raise

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return now.astimezone(UTC)

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._check_open()
        try:
            self._db.execute("BEGIN IMMEDIATE")
            yield
            self._db.execute("COMMIT")
        except sqlite3.Error:
            if self._db.in_transaction:
                self._db.execute("ROLLBACK")
            raise StoreUnavailable("local memory transaction failed") from None
        except BaseException:
            if self._db.in_transaction:
                self._db.execute("ROLLBACK")
            raise

    def _check_open(self) -> None:
        if self._closed:
            raise StoreUnavailable("memory store is closed")

    def _migrate(self) -> None:
        with self._transaction():
            version = self._db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise StoreUnavailable("unsupported memory schema version")
            if version == 1:
                return
            statements = [
                """CREATE TABLE memories (
                    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, actor_id TEXT NOT NULL,
                    namespace TEXT NOT NULL, visibility TEXT NOT NULL, team_principal TEXT,
                    workstream_id TEXT, workstream_system TEXT, status TEXT NOT NULL,
                    revision INTEGER NOT NULL, valid_until TEXT, fingerprint TEXT NOT NULL,
                    body TEXT NOT NULL)""",
                """CREATE INDEX memory_acl ON memories
                    (tenant_id,namespace,visibility,actor_id,team_principal,status)""",
                """CREATE TABLE revisions (
                    memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                    revision INTEGER NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY(memory_id,revision))""",
                """CREATE TABLE source_index (
                    memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                    revision INTEGER NOT NULL, source_id TEXT NOT NULL,
                    PRIMARY KEY(memory_id,revision,source_id))""",
                "CREATE INDEX source_lookup ON source_index(source_id,memory_id,revision)",
                "CREATE INDEX duplicate_lookup ON memories(tenant_id,actor_id,fingerprint,status)",
                "PRAGMA user_version=1",
            ]
            for statement in statements:
                self._db.execute(statement)

    def _probe_fts(self) -> bool:
        try:
            self._db.execute("CREATE VIRTUAL TABLE temp.fts_probe USING fts5(content)")
            self._db.execute("DROP TABLE temp.fts_probe")
            return True
        except sqlite3.OperationalError:
            return False

    def _acl(self, scope: AccessScope, *, revision: str = "m.revision") -> tuple[str, list[str]]:
        scope = self.policy.validate_scope(scope)
        namespaces = sorted(scope.allowed_namespaces)
        grants = sorted(self.policy.grants(scope))
        sql = f"""m.tenant_id=? AND m.namespace IN ({",".join("?" for _ in namespaces)})
            AND ((m.visibility='private' AND m.actor_id=?) OR
            (m.visibility='team' AND m.team_principal IN ({",".join("?" for _ in grants)})))"""
        args = [scope.tenant_id, *namespaces, scope.actor_id, *grants]
        if scope.allowed_source_ids is not None:
            allowed = sorted(scope.allowed_source_ids)
            # Empty allowlist denies every record with supporting references.
            clause = f"s.source_id NOT IN ({','.join('?' for _ in allowed)})" if allowed else "1=1"
            sql += f""" AND NOT EXISTS (SELECT 1 FROM source_index s
                WHERE s.memory_id=m.id AND s.revision={revision} AND {clause})"""
            args.extend(allowed)
        return sql, args

    def _get(self, memory_id: str, scope: AccessScope) -> MemoryRecord | None:
        self._check_open()
        acl, args = self._acl(scope)
        row = self._db.execute(
            f"SELECT m.body FROM memories m WHERE {acl} AND m.id=?", [*args, memory_id]
        ).fetchone()
        return MemoryRecord.model_validate_json(row[0]) if row else None

    def _owned(
        self, memory_id: str, scope: AccessScope, revision: int | None = None
    ) -> MemoryRecord:
        record = self._get(memory_id, scope)
        if record is None:
            raise AccessDenied("memory is unavailable for mutation")
        self.policy.require_owner(record, scope)
        if revision is not None and record.revision != revision:
            raise RevisionConflict("memory revision changed")
        return record

    def _approval(
        self, candidate: MemoryCandidate, scope: AccessScope, approval: ApprovalEvidence
    ) -> None:
        self.policy.require_write(candidate, scope)
        if approval.actor_id != scope.actor_id:
            raise AccessDenied("approval actor does not match authenticated actor")
        if candidate.sensitivity == "sensitive" and not approval.allow_sensitive:
            raise AccessDenied("sensitive memory requires explicit approval")
        if candidate.visibility != Visibility.PRIVATE and not approval.allow_publication:
            raise AccessDenied("shared memory requires explicit publication approval")
        if candidate.valid_until is not None and candidate.valid_until <= self._now():
            raise InvalidMemory("new memory cannot already be expired")
        if approval.approved_at > self._now():
            raise InvalidMemory("approval cannot be in the future")

    @staticmethod
    def _fingerprint(candidate: MemoryCandidate) -> str:
        data = candidate.model_dump(mode="json", exclude={"source_event", "uncertainty", "status"})
        data["source_refs"] = sorted(
            (r.provider, r.source_id, r.version or "") for r in candidate.source_refs
        )
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def _save(self, record: MemoryRecord, fingerprint: str | None = None) -> None:
        body = record.model_dump_json()
        if fingerprint is not None:
            self._db.execute(
                """INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record.id,
                    record.tenant_id,
                    record.actor_id,
                    record.namespace,
                    record.visibility.value,
                    record.team_principal,
                    record.workstream.external_id if record.workstream else None,
                    record.workstream.system if record.workstream else None,
                    record.status.value,
                    record.revision,
                    record.valid_until.astimezone(UTC).isoformat() if record.valid_until else None,
                    fingerprint,
                    body,
                ),
            )
        else:
            self._db.execute(
                "UPDATE memories SET status=?,revision=?,valid_until=?,body=?,fingerprint=? "
                "WHERE id=?",
                (
                    record.status.value,
                    record.revision,
                    record.valid_until.astimezone(UTC).isoformat() if record.valid_until else None,
                    body,
                    self._fingerprint(self._as_candidate(record)),
                    record.id,
                ),
            )
        self._db.execute("INSERT INTO revisions VALUES (?,?,?)", (record.id, record.revision, body))
        self._db.executemany(
            "INSERT OR IGNORE INTO source_index VALUES (?,?,?)",
            [(record.id, record.revision, r.source_id) for r in record.source_refs],
        )

    @staticmethod
    def _as_candidate(record: MemoryRecord) -> MemoryCandidate:
        return MemoryCandidate(
            **record.model_dump(
                include=set(MemoryCandidate.model_fields) - {"status", "uncertainty"}
            )
        )

    async def create(
        self, candidate: MemoryCandidate, *, scope: AccessScope, approval: ApprovalEvidence
    ) -> MemoryRecord:
        scope = self.policy.validate_scope(scope)
        candidate = MemoryCandidate.model_validate(candidate)
        approval = ApprovalEvidence.model_validate(approval)
        self._approval(candidate, scope, approval)
        fingerprint = self._fingerprint(candidate)
        with self._transaction():
            acl, args = self._acl(scope)
            row = self._db.execute(
                f"""SELECT m.body FROM memories m WHERE {acl} AND m.actor_id=?
                    AND fingerprint=? AND status='active' AND
                    (valid_until IS NULL OR valid_until>?) ORDER BY m.id LIMIT 1""",
                [*args, scope.actor_id, fingerprint, self._now().isoformat()],
            ).fetchone()
            if row:
                return MemoryRecord.model_validate_json(row[0])
            now = self._now()
            record = MemoryRecord(
                **candidate.model_dump(exclude={"status", "uncertainty"}),
                id=str(uuid4()),
                tenant_id=scope.tenant_id,
                actor_id=scope.actor_id,
                created_at=now,
                updated_at=now,
                approval=approval,
            )
            self._save(record, fingerprint)
            return record

    async def get(self, memory_id: str, *, scope: AccessScope) -> MemoryRecord | None:
        return self._get(memory_id, scope)

    async def list(
        self, *, scope: AccessScope, include_inactive: bool = False
    ) -> tuple[MemoryRecord, ...]:
        self._check_open()
        acl, args = self._acl(scope)
        if not include_inactive:
            acl += " AND m.status='active' AND (m.valid_until IS NULL OR m.valid_until>?)"
            args.append(self._now().isoformat())
        rows = self._db.execute(
            f"SELECT m.body FROM memories m WHERE {acl} ORDER BY m.id", args
        ).fetchall()
        return tuple(MemoryRecord.model_validate_json(row[0]) for row in rows)

    async def export(self, *, scope: AccessScope) -> str:
        return json.dumps(
            {
                "schema_version": "1",
                "records": [
                    r.model_dump(mode="json")
                    for r in await self.list(scope=scope, include_inactive=True)
                ],
            },
            sort_keys=True,
        )

    async def history(self, memory_id: str, *, scope: AccessScope) -> tuple[MemoryRecord, ...]:
        if self._get(memory_id, scope) is None:
            return ()
        acl, args = self._acl(scope, revision="r.revision")
        rows = self._db.execute(
            f"""SELECT r.body FROM revisions r JOIN memories m ON m.id=r.memory_id
                WHERE {acl} AND m.id=? ORDER BY r.revision""",
            [*args, memory_id],
        ).fetchall()
        return tuple(MemoryRecord.model_validate_json(row[0]) for row in rows)

    async def search(
        self, query: str, *, scope: AccessScope, workstream: WorkstreamRef | None, limit: int
    ) -> Sequence[MemoryRecord]:
        if not 0 < limit <= 1000:
            raise ValueError("limit must be in 1..1000")
        # Only authorised active bodies are loaded, BEFORE FTS/lexical processing.
        records = await self.list(scope=scope)
        query_terms = terms(query)
        matching_ids: set[str] | None = None
        if self.fts_available and query_terms:
            # Transient index avoids a global cross-tenant FTS corpus or rank statistics.
            try:
                self._db.execute(
                    "CREATE VIRTUAL TABLE temp.scoped_fts USING fts5(id UNINDEXED, content)"
                )
                self._db.executemany(
                    "INSERT INTO temp.scoped_fts VALUES (?,?)", [(r.id, r.content) for r in records]
                )
                match = " OR ".join('"' + t.replace('"', '""') + '"' for t in sorted(query_terms))
                matching_ids = {
                    row[0]
                    for row in self._db.execute(
                        "SELECT id FROM temp.scoped_fts WHERE scoped_fts MATCH ?", (match,)
                    )
                }
            finally:
                self._db.execute("DROP TABLE IF EXISTS temp.scoped_fts")
        ranked = []
        for record in records:
            overlap = len(query_terms & terms(record.content))
            same_workstream = workstream is not None and record.workstream == workstream
            if (
                record.id in matching_ids if matching_ids is not None else overlap > 0
            ) or same_workstream:
                ranked.append((record, overlap + (3 if same_workstream else 0)))
        return tuple(r for r, _ in sorted(ranked, key=lambda item: (-item[1], item[0].id))[:limit])

    async def update(
        self,
        memory_id: str,
        update: MemoryUpdate,
        *,
        expected_revision: int,
        scope: AccessScope,
        approval: ApprovalEvidence,
    ) -> MemoryRecord:
        update = MemoryUpdate.model_validate(update)
        approval = ApprovalEvidence.model_validate(approval)
        with self._transaction():
            record = self._owned(memory_id, scope, expected_revision)
            if record.status != MemoryState.ACTIVE:
                raise InvalidMemory("inactive memory requires a new record")
            candidate = MemoryCandidate(
                **{**self._as_candidate(record).model_dump(), **update.model_dump()}
            )
            self._approval(candidate, scope, approval)
            revised = MemoryRecord.model_validate(
                {
                    **record.model_dump(),
                    **update.model_dump(),
                    "revision": record.revision + 1,
                    "updated_at": self._now(),
                    "approval": approval,
                }
            )
            self._save(revised)
            return revised

    async def invalidate(
        self, memory_id: str, *, scope: AccessScope, expected_revision: int, reason: str
    ) -> MemoryRecord:
        if not reason.strip():
            raise InvalidMemory("invalidation requires a reason")
        with self._transaction():
            record = self._owned(memory_id, scope, expected_revision)
            revised = MemoryRecord.model_validate(
                {
                    **record.model_dump(),
                    "status": MemoryState.INVALIDATED,
                    "invalidation_reason": reason,
                    "revision": record.revision + 1,
                    "updated_at": self._now(),
                }
            )
            self._save(revised)
            return revised

    async def supersede(
        self, memory_id: str, replacement_id: str, *, expected_revision: int, scope: AccessScope
    ) -> MemoryRecord:
        with self._transaction():
            record = self._owned(memory_id, scope, expected_revision)
            replacement = self._owned(replacement_id, scope)
            if (
                record.id == replacement.id
                or record.status != MemoryState.ACTIVE
                or replacement.status != MemoryState.ACTIVE
                or record.kind != replacement.kind
                or record.workstream != replacement.workstream
                or record.visibility != replacement.visibility
                or record.namespace != replacement.namespace
                or record.team_principal != replacement.team_principal
                or (replacement.valid_until is not None and replacement.valid_until <= self._now())
            ):
                raise InvalidMemory(
                    "supersession requires a distinct current record with matching scope and kind"
                )
            revised = MemoryRecord.model_validate(
                {
                    **record.model_dump(),
                    "status": MemoryState.SUPERSEDED,
                    "superseded_by": replacement_id,
                    "revision": record.revision + 1,
                    "updated_at": self._now(),
                }
            )
            self._save(revised)
            return revised

    async def delete(self, memory_id: str, *, scope: AccessScope) -> None:
        with self._transaction():
            self._owned(memory_id, scope)
            self._db.execute("DELETE FROM memories WHERE id=?", (memory_id,))

    async def close(self) -> None:
        if not self._closed:
            self._db.close()
            self._closed = True
