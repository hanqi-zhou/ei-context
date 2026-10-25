"""Public errors; messages deliberately omit source contents and private identifiers."""


class ContextError(Exception):
    """Base library error."""


class InvalidScope(ContextError):
    """Caller identity or namespace constraints are missing or malformed."""


class AccessDenied(ContextError):
    """Operation is forbidden, or its target is not visible to this actor."""


class RevisionConflict(ContextError):
    """Optimistic concurrency check failed."""


class BudgetExceeded(ContextError):
    """Requested budget cannot hold even the context framing."""


class ProviderUnavailable(ContextError):
    """A source failed or timed out."""


class InvalidMemory(ContextError):
    """Memory lacks confirmation, provenance, or required validation."""


class StoreUnavailable(ContextError):
    """Storage is closed, busy, or has an unsupported schema."""
