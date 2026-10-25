"""Versioned serialisable contracts. Unknown validity/version is explicitly None."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=512, pattern=r"^\S+$")]
Text = Annotated[str, Field(min_length=1, max_length=100_000)]


class Model(BaseModel):
    """Reject unknown fields and accidental assignment; revalidate at trust boundaries."""

    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


class MemoryState(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"


class MemoryKind(StrEnum):
    DECISION = "decision"
    FINDING = "finding"
    ATTEMPT = "attempted_approach"
    OPEN_QUESTION = "open_question"
    TASK_SUMMARY = "task_summary"


class Visibility(StrEnum):
    PRIVATE = "private"
    TEAM = "team"
    ORG = "org"


class AccessScope(Model):
    """Authenticated host identity; principals are hints, never verified grants."""

    tenant_id: Identifier
    actor_id: Identifier
    principals: frozenset[Identifier] = frozenset()
    allowed_source_ids: frozenset[Identifier] | None = None
    allowed_namespaces: frozenset[Identifier] = frozenset({"work"})

    @field_validator("allowed_namespaces")
    @classmethod
    def namespaces_required(cls, value: frozenset[str]) -> frozenset[str]:
        if not value:
            raise ValueError("at least one namespace is required")
        return value


class WorkstreamRef(Model):
    external_id: Identifier
    system: Identifier | None = None


class SourceRef(Model):
    provider: Identifier
    source_id: Identifier
    uri: str | None = None
    version: str | None = None
    retrieved_at: AwareDatetime
    modified_at: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None


class Evidence(Model):
    id: Identifier
    text: Text
    source: SourceRef
    tenant_id: Identifier
    access_principals: frozenset[Identifier]
    namespace: Identifier = "work"
    trust_label: Literal["unverified", "user_confirmed", "system_verified"] = "unverified"
    workstream: WorkstreamRef | None = None
    source_refs: tuple[SourceRef, ...] = ()
    memory_kind: MemoryKind | None = None
    memory_status: MemoryState | None = None
    valid_until: AwareDatetime | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ContextRequest(Model):
    query: Annotated[str, Field(min_length=1, max_length=10_000)]
    scope: AccessScope
    workstream: WorkstreamRef | None = None
    token_budget: int = Field(default=4000, gt=0, le=1_000_000)
    max_items: int = Field(default=20, gt=0, le=1000)
    provider_ids: tuple[Identifier, ...] | None = None
    excluded_source_ids: frozenset[Identifier] = frozenset()

    @field_validator("query")
    @classmethod
    def nonblank_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query cannot be blank")
        return value


class SelectedContext(Model):
    evidence_id: str
    excerpt: str
    source: SourceRef
    source_refs: tuple[SourceRef, ...] = ()
    reason: str
    estimated_tokens: int
    citation: str
    caveats: tuple[str, ...] = ()
    memory_kind: MemoryKind | None = None
    memory_status: MemoryState | None = None


class ContextBundle(Model):
    schema_version: Literal["1"] = "1"
    rendered_context: str
    selected: tuple[SelectedContext, ...]
    estimated_tokens: int
    warnings: tuple[str, ...] = ()
    omitted_count: int = 0


class MemoryCandidate(Model):
    """A proposal is never an authoritative record until explicitly approved."""

    kind: MemoryKind
    content: Text
    source_refs: tuple[SourceRef, ...] = Field(min_length=1)
    workstream: WorkstreamRef | None = None
    namespace: Identifier = "work"
    visibility: Visibility = Visibility.PRIVATE
    team_principal: Identifier | None = None
    valid_until: AwareDatetime | None = None
    source_event: Identifier | None = None
    uncertainty: str | None = None
    sensitivity: Literal["normal", "sensitive"] = "normal"
    status: Literal["pending"] = "pending"

    @model_validator(mode="after")
    def team_requires_principal(self) -> "MemoryCandidate":
        if (self.visibility == Visibility.TEAM) != (self.team_principal is not None):
            raise ValueError("team visibility requires exactly one team principal")
        return self


class ApprovalEvidence(Model):
    """Attested by the trusted host, not proof of external technical correctness."""

    actor_id: Identifier
    method: Literal["user_confirmed", "system_verified"]
    reference: Identifier
    approved_at: AwareDatetime
    allow_publication: bool = False


class MemoryRecord(Model):
    schema_version: Literal["1"] = "1"
    id: Identifier
    tenant_id: Identifier
    actor_id: Identifier
    namespace: Identifier = "work"
    visibility: Visibility = Visibility.PRIVATE
    team_principal: Identifier | None = None
    workstream: WorkstreamRef | None = None
    kind: MemoryKind
    content: Text
    source_refs: tuple[SourceRef, ...] = Field(min_length=1)
    status: MemoryState = MemoryState.ACTIVE
    revision: int = Field(default=1, gt=0)
    created_at: AwareDatetime
    updated_at: AwareDatetime
    valid_until: AwareDatetime | None = None
    approval: ApprovalEvidence
    sensitivity: Literal["normal", "sensitive"] = "normal"
    superseded_by: str | None = None
    invalidation_reason: str | None = None
    source_event: str | None = None


class MemoryUpdate(Model):
    """A correction preserves ownership and visibility; content and provenance travel together."""

    content: Text
    source_refs: tuple[SourceRef, ...] = Field(min_length=1)
    valid_until: AwareDatetime | None = None


# An injectable clock uses this callable shape; timezone awareness is validated at use sites.
def utc_now() -> datetime:
    from datetime import UTC

    return datetime.now(UTC)
