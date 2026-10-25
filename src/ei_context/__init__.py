"""EI Context: scoped evidence retrieval and persistent work memory."""

from ei_context.engine import ContextEngine
from ei_context.lifecycle import ContextEvent
from ei_context.memory import MemoryManager, SQLiteMemoryStore
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
    MemoryUpdate,
    SelectedContext,
    SourceIdentity,
    SourceRef,
    Visibility,
    WorkstreamRef,
)
from ei_context.policy import AccessPolicy

__version__ = "0.2.0"
__all__ = [
    "AccessPolicy",
    "AccessScope",
    "ApprovalEvidence",
    "ContextEngine",
    "ContextEvent",
    "ContextBundle",
    "ContextRequest",
    "Evidence",
    "MemoryManager",
    "SQLiteMemoryStore",
    "MemoryCandidate",
    "MemoryKind",
    "MemoryRecord",
    "MemoryState",
    "MemoryUpdate",
    "SelectedContext",
    "SourceRef",
    "SourceIdentity",
    "Visibility",
    "WorkstreamRef",
]
