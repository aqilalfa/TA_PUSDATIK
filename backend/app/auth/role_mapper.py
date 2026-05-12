"""Helpers for mapping external identity groups to local PBAC roles."""

from __future__ import annotations

import json
from typing import Iterable, List, Sequence


DEFAULT_ROLE_MAPPING = {
    "Evaluator_SPBE": ["evaluator_spbe"],
    "Staf_PUSDATIK": ["staf_pusdatik"],
    "Admin_PUSDATIK": ["admin_pusdatik", "staf_pusdatik"],
    "Manager_Evaluasi": ["manager_evaluasi", "staf_pusdatik"],
}


def map_directory_groups_to_roles(
    groups: Sequence[str],
    role_mapping: dict[str, list[str]] | None = None,
) -> list[str]:
    """Map directory groups to normalized application roles."""

    mapping = role_mapping or DEFAULT_ROLE_MAPPING
    normalized_roles: set[str] = set()

    for group in groups:
        normalized_roles.update(mapping.get(group, []))

    return sorted(normalized_roles)


def parse_roles(value: str | None) -> list[str]:
    """Parse a JSON encoded roles field into a stable list."""

    if not value:
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    return [str(role) for role in parsed if str(role).strip()]


def serialize_roles(roles: Iterable[str]) -> str:
    """Serialize a role sequence to the DB JSON string format."""

    normalized = sorted({str(role).strip() for role in roles if str(role).strip()})
    return json.dumps(normalized)
