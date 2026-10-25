"""Deduplicate equal source/version/content snapshots without losing provenance."""

import hashlib
import json
from collections.abc import Sequence

from ei_context.models import Evidence


def deduplicate(evidence: Sequence[Evidence]) -> list[Evidence]:
    unique: dict[tuple[str, str, str | None, str, str], Evidence] = {}
    for item in sorted(evidence, key=lambda e: (e.source.provider, e.source.source_id, e.id)):
        key = (
            item.source.provider,
            item.source.source_id,
            item.source.version,
            hashlib.sha256(item.text.encode()).hexdigest(),
            json.dumps(
                item.model_dump(
                    mode="json",
                    include={
                        "namespace",
                        "workstream",
                        "memory_kind",
                        "memory_status",
                        "trust_label",
                        "valid_until",
                    },
                ),
                sort_keys=True,
            ),
        )
        if key not in unique:
            unique[key] = item
        else:
            original = unique[key]
            refs = {r.model_dump_json(): r for r in (*original.source_refs, *item.source_refs)}
            unique[key] = original.model_copy(
                update={"source_refs": tuple(refs[k] for k in sorted(refs))}
            )
    return list(unique.values())
