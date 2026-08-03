"""Tests for the always-on vs. behind-search recommendation."""

import json

from skillify.integrations import install_mcp_server
from skillify.scanner import scan_directory
from skillify.tiering import DEMOTED_TIER, in_native_listing, recommend_tiers

from conftest import write_skill


def test_every_skill_lands_in_exactly_one_tier(library):
    """A skill missing from both tiers would silently lose its recommendation."""
    skills = scan_directory(library)
    tiers = recommend_tiers(skills)

    tiered = {e["id"] for e in tiers["always_on"]} | {e["id"] for e in tiers["demoted"]}
    assert tiered == {s["id"] for s in skills}
    assert not {e["id"] for e in tiers["always_on"]} & {e["id"] for e in tiers["demoted"]}


def build_wide_library(tmp_path, connected=6):
    """A library with a connected core plus one skill that shares nothing."""
    for i in range(connected):
        write_skill(
            tmp_path / f"infra-{i}",
            f"Infra Task {i}",
            "Routine infrastructure work on the deployment pipeline",
            keywords=["infrastructure", "deployment", "pipeline"],
            category="infrastructure",
        )
    write_skill(
        tmp_path / "lonely",
        "Lonely Skill",
        "Something entirely unrelated to anything else here",
        keywords=["zzz-unique-keyword"],
        category="misc",
    )
    return scan_directory(tmp_path)


def test_isolated_skills_are_demoted(tmp_path):
    """An isolated skill shares vocabulary with nothing, so search is the right home."""
    tiers = recommend_tiers(build_wide_library(tmp_path))

    assert tiers["overrides"]["Lonely Skill"] == DEMOTED_TIER


def test_small_library_keeps_everything_always_on(library):
    """Three skills fit the native listing; demoting any of them buys nothing."""
    tiers = recommend_tiers(scan_directory(library))

    assert tiers["demoted"] == []
    assert tiers["overrides"] == {}


def test_overrides_cover_exactly_the_demoted_skills(tmp_path):
    """The pasted block must match what the recommendation said."""
    tiers = recommend_tiers(build_wide_library(tmp_path))

    assert tiers["demoted"], "fixture should be large enough to demote from"
    assert set(tiers["overrides"]) == {e["name"] for e in tiers["demoted"]}
    assert set(tiers["overrides"].values()) == {DEMOTED_TIER}


def test_duplicate_names_are_flagged(tmp_path):
    """skillOverrides is keyed by name, so duplicates cannot be addressed apart."""
    write_skill(tmp_path / "alpha", "Testing", "Alpha flavour")
    write_skill(tmp_path / "beta", "Testing", "Beta flavour")

    tiers = recommend_tiers(scan_directory(tmp_path))

    assert tiers["duplicate_names"] == ["Testing"]


def test_empty_library_is_handled(tmp_path):
    """No skills is a valid state, not a crash."""
    tiers = recommend_tiers([])

    assert tiers == {"always_on": [], "demoted": [], "overrides": {}, "duplicate_names": []}


def test_library_outside_claude_dirs_is_not_natively_listed(tmp_path):
    """A library Claude Code never scans has nothing in the listing to demote.

    Recommending skillOverrides for it would print a block that applies to
    nothing, with no signal to the user that it is inert.
    """
    assert not in_native_listing(str(tmp_path / "skills-library"), project_dir=str(tmp_path))


def test_project_skills_dir_is_natively_listed(tmp_path):
    """Skills under .claude/skills/ are exactly the ones overrides can address."""
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)

    assert in_native_listing(str(skills_dir), project_dir=str(tmp_path))
    assert in_native_listing(str(skills_dir / "nested"), project_dir=str(tmp_path))


def test_install_merges_into_existing_mcp_config(tmp_path, library):
    """Registration must not clobber other MCP servers already configured."""
    config = tmp_path / ".mcp.json"
    config.write_text(json.dumps({"mcpServers": {"other": {"command": "othertool"}}}))

    install_mcp_server(str(library), project_dir=str(tmp_path))
    written = json.loads(config.read_text())

    assert "other" in written["mcpServers"]
    assert written["mcpServers"]["skillify"]["args"][0] == "mcp"
