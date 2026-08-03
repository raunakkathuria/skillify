"""Recommend which skills stay in the native listing and which go behind search.

This is the half of the MCP story that actually saves context. An MCP server on
its own only *adds* a discovery path: if every skill stays in `~/.claude/skills/`,
Claude Code still enumerates and truncates them, and `search_skills` is a second
listing stacked on top.

Claude Code 2.1.x ships a `skillOverrides` setting keyed by skill name:

    "name-only"           list the skill, drop its description
    "user-invocable-only" hide from the model, keep /name for the human
    "off"                 hide from both

That is manual tiering — the platform supports the decision but won't make it.
Skillify already computes a relationship graph, so it can: broadly-connected
skills stay always-on, and the long tail is demoted to `user-invocable-only`,
where `search_skills` restores model access on demand.

`user-invocable-only` rather than `off` because it costs the user nothing — the
slash command still works.
"""

import math

from .graph_builder import build_graph
from .reporter import connection_counts

# Fraction of the library that stays in the native listing. A skill connected to
# many others shares its vocabulary with many tasks, which is the only
# broad-relevance signal available from metadata alone.
KEEP_RATIO = 0.2
MIN_KEEP = 3

DEMOTED_TIER = "user-invocable-only"

# Below this, the whole listing fits comfortably and tiering costs more attention
# than it saves. Anthropic puts tool-selection degradation at 30-50 options.
TIERING_WORTHWHILE_AT = 30


def recommend_tiers(skills: list[dict]) -> dict:
    """Split skills into always-on and search-only tiers.

    Args:
        skills: Skill metadata dicts from a scan.

    Returns:
        Dict with keys:
        - always_on: skills that stay in the native listing, most connected first
        - demoted: skills to put behind search
        - overrides: ready-to-paste skillOverrides mapping (name -> tier)
        - duplicate_names: names shared by more than one skill
        Each tiered entry carries 'name', 'id', 'connections' and 'reason'.
    """
    if not skills:
        return {"always_on": [], "demoted": [], "overrides": {}, "duplicate_names": []}

    counts = connection_counts(build_graph(skills))

    ranked = sorted(
        skills,
        key=lambda s: (-counts.get(s["id"], 0), s.get("name", "").lower()),
    )
    keep = min(len(ranked), max(MIN_KEEP, math.ceil(len(ranked) * KEEP_RATIO)))

    always_on = [_entry(s, counts, kept=True) for s in ranked[:keep]]
    demoted = [_entry(s, counts, kept=False) for s in ranked[keep:]]

    # skillOverrides is keyed by skill name, so skills sharing a name cannot be
    # addressed separately — the caller needs to know before pasting.
    seen: set[str] = set()
    duplicates: set[str] = set()
    for skill in skills:
        name = skill.get("name", "")
        if name in seen:
            duplicates.add(name)
        seen.add(name)

    return {
        "always_on": always_on,
        "demoted": demoted,
        "overrides": {entry["name"]: DEMOTED_TIER for entry in demoted},
        "duplicate_names": sorted(duplicates),
    }


def _entry(skill: dict, counts: dict[str, int], kept: bool) -> dict:
    """Build one tier entry with a human-readable reason."""
    connections = counts.get(skill["id"], 0)
    label = f"{connections} connection" + ("" if connections == 1 else "s")

    if kept:
        reason = (
            f"{label} — shares vocabulary with much of the library"
            if connections
            else "few skills to choose from"
        )
    elif connections:
        reason = f"{label} — narrow enough to retrieve on demand"
    else:
        reason = "isolated — nothing else shares its keywords or category"

    return {
        "name": skill.get("name", ""),
        "id": skill["id"],
        "connections": connections,
        "reason": reason,
    }
