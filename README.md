# EI Context

**Standalone, agent-agnostic context-engineering and persistent-work-memory Python library.**

Status: design approved for implementation planning; implementation not yet started.

EI Context helps agents retrieve relevant evidence, recall work across sessions, and build trustworthy, appropriately scoped context bundles. It is **not** an agent runtime, IDE, task dashboard, or replacement for engineering search tools.

## Documents

- [Architecture and product design](docs/DESIGN.md)
- [Build plan and milestones](docs/IMPLEMENTATION_PLAN.md)
- [Python contracts and examples](docs/CONTRACTS.md)
- [Developer-experience opportunity backlog](docs/DX_BACKLOG.md)
- [Worker handoff / build instructions](docs/WORKER_HANDOFF.md)
- [Architecture decision: standalone library](docs/adr/0001-package-boundaries.md)

## Position within EI Stack

- **EI Core**: engineering-specific capabilities (API discovery, code search, dependency or policy checks).
- **EI Context**: source-agnostic retrieval, persistent work memory, provenance, ranking, context assembly, lifecycle policies.
- **EI Server**: agent loop, tool execution, checkpoints, run scheduling, network API, authentication.
- **EI Integration**: user-facing adapters and external-agent access.

EI Context has **no required dependency** on any other EI package. An EI Core adapter may satisfy its provider interface; EI Server may call its library API; IDE or third-party agents may integrate via adapters later. Do not create a second agent loop.

## Initial goals

1. A pip-installable Python library with typed, asynchronous interfaces.
2. An offline, deterministic end-to-end demo with synthetic data.
3. Scoped memory and evidence retrieval across separate sessions.
4. Compact context bundles with provenance, citations and budgets.
5. Explicit memory lifecycle (add, list, search, correct, invalidate, delete).
6. Security: fail-closed access scope, safe log handling, no external model or network requirement.

## Development guidance

Start with [docs/WORKER_HANDOFF.md](docs/WORKER_HANDOFF.md) and implement milestones in [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md). Keep it library-first, API- and provider-driven. Avoid production integrations or any real employer data in this repository until permissions, repository visibility, and data-handling policies are confirmed.

## Legal and confidentiality note

This repository may be public. **Never commit** internal source code, real API specifications, credentials, private conversations, compliance findings, or confidential organisational information. All examples must use synthetic data. Set the repository to private before bringing in employer-specific materials, and follow the employer's policies even then.

## License

No license selected. Do not add an open-source license without explicit owner approval.
