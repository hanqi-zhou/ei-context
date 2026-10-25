"""EI Context: scoped evidence retrieval and persistent work memory."""

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
    SourceRef,
    Visibility,
    WorkstreamRef,
)
from ei_context.policy import AccessPolicy

__version__ = "0.1.0"
__all__ = [
    "AccessPolicy",
    "AccessScope",
    "ApprovalEvidence",
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
    "Visibility",
    "WorkstreamRef",
]
