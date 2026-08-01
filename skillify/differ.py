"""Diff module for comparing skill scans against existing indexes.

Computes added, removed, and modified skills between a new scan and
an existing skills-index.json file.
"""

import json
import os
from typing import Any


def compute_diff(
    new_skills: list[dict], existing_index_path: str
) -> dict[str, Any]:
    """Compare new scan results against an existing skills index.

    Args:
        new_skills: List of skill metadata dicts from a fresh scan.
        existing_index_path: Path to the existing skills-index.json file.

    Returns:
        Dict with keys:
        - added: list of new skill dicts not in the existing index
        - removed: list of skill dicts in existing index but not in new scan
        - modified: list of dicts with 'skill', 'changes' keys for changed skills
        - unchanged: list of skill dicts that haven't changed
        - is_stale: bool, True if there are any changes
        - summary: human-readable summary string
    """
    # Load existing index
    existing_skills = _load_existing_index(existing_index_path)

    # Index by ID for comparison
    existing_by_id = {s["id"]: s for s in existing_skills}
    new_by_id = {s.get("id", ""): s for s in new_skills}

    added: list[dict] = []
    removed: list[dict] = []
    modified: list[dict] = []
    unchanged: list[dict] = []

    # Find added and modified
    for skill_id, skill in new_by_id.items():
        if skill_id not in existing_by_id:
            added.append(skill)
        else:
            changes = _detect_changes(existing_by_id[skill_id], skill)
            if changes:
                modified.append({"skill": skill, "changes": changes})
            else:
                unchanged.append(skill)

    # Find removed
    for skill_id, skill in existing_by_id.items():
        if skill_id not in new_by_id:
            removed.append(skill)

    is_stale = bool(added or removed or modified)

    summary = _build_summary(added, removed, modified, unchanged)

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "unchanged": unchanged,
        "is_stale": is_stale,
        "summary": summary,
    }


def _load_existing_index(index_path: str) -> list[dict]:
    """Load skills from an existing index file.

    Args:
        index_path: Path to skills-index.json.

    Returns:
        List of skill dicts from the index, or empty list if file doesn't exist.
    """
    if not os.path.exists(index_path):
        return []

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("skills", [])
    except (json.JSONDecodeError, OSError):
        return []


def _detect_changes(old: dict, new: dict) -> list[str]:
    """Detect which fields changed between old and new skill versions.

    Compares: name, description, keywords, category, version, path.

    Args:
        old: Existing skill dict from the index.
        new: New skill dict from the scan.

    Returns:
        List of change description strings. Empty list means no changes.
    """
    changes: list[str] = []

    # Fields to compare
    compare_fields = [
        ("name", "name"),
        ("description", "description"),
        ("category", "category"),
        ("version", "version"),
        ("path", "path"),
    ]

    for field, label in compare_fields:
        old_val = old.get(field, "")
        new_val = new.get(field, "")
        if old_val != new_val:
            changes.append(f"{label}: '{old_val}' → '{new_val}'")

    # Keywords comparison (order-independent)
    old_keywords = set(old.get("keywords", []))
    new_keywords = set(k.lower() if isinstance(k, str) else k for k in new.get("keywords", []))

    # Normalize old keywords for comparison
    old_keywords_lower = set(k.lower() if isinstance(k, str) else k for k in old_keywords)

    added_kw = new_keywords - old_keywords_lower
    removed_kw = old_keywords_lower - new_keywords

    if added_kw or removed_kw:
        parts = []
        if added_kw:
            parts.append(f"+{', '.join(sorted(added_kw))}")
        if removed_kw:
            parts.append(f"-{', '.join(sorted(removed_kw))}")
        changes.append(f"keywords: {'; '.join(parts)}")

    return changes


def _build_summary(
    added: list[dict],
    removed: list[dict],
    modified: list[dict],
    unchanged: list[dict],
) -> str:
    """Build a human-readable summary of changes.

    Args:
        added: List of added skills.
        removed: List of removed skills.
        modified: List of modified skill entries.
        unchanged: List of unchanged skills.

    Returns:
        Multi-line summary string.
    """
    total = len(added) + len(removed) + len(modified) + len(unchanged)
    lines: list[str] = []

    if not added and not removed and not modified:
        lines.append(f"Index is up to date ({total} skills, no changes)")
        return "\n".join(lines)

    lines.append(f"Changes detected ({total} skills total):")

    if added:
        lines.append(f"  + {len(added)} added")
        for skill in added:
            lines.append(f"    + {skill.get('name', skill.get('id', '?'))}")

    if removed:
        lines.append(f"  - {len(removed)} removed")
        for skill in removed:
            lines.append(f"    - {skill.get('name', skill.get('id', '?'))}")

    if modified:
        lines.append(f"  ~ {len(modified)} modified")
        for entry in modified:
            skill = entry["skill"]
            changes = entry["changes"]
            lines.append(f"    ~ {skill.get('name', skill.get('id', '?'))}")
            for change in changes:
                lines.append(f"      {change}")

    if unchanged:
        lines.append(f"  = {len(unchanged)} unchanged")

    return "\n".join(lines)


def diff_to_json(diff_result: dict) -> dict:
    """Convert diff result to a JSON-serializable CI-friendly format.

    Args:
        diff_result: Output from compute_diff().

    Returns:
        Dict suitable for JSON serialization with CI-relevant fields.
    """
    return {
        "is_stale": diff_result["is_stale"],
        "total_skills": (
            len(diff_result["added"])
            + len(diff_result["removed"])
            + len(diff_result["modified"])
            + len(diff_result["unchanged"])
        ),
        "changes": {
            "added": len(diff_result["added"]),
            "removed": len(diff_result["removed"]),
            "modified": len(diff_result["modified"]),
            "unchanged": len(diff_result["unchanged"]),
        },
        "added_skills": [s.get("name", s.get("id", "")) for s in diff_result["added"]],
        "removed_skills": [s.get("name", s.get("id", "")) for s in diff_result["removed"]],
        "modified_skills": [
            e["skill"].get("name", e["skill"].get("id", ""))
            for e in diff_result["modified"]
        ],
    }
