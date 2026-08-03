"""Skillify CLI — Scan AI skills and generate structured indexes with visual graphs."""

import json
import os
import sys

import click

from .differ import compute_diff, diff_to_json
from .github_scanner import is_github_ref, scan_github_repo
from .graph_builder import build_graph, write_graph
from .indexer import generate_index, search_index
from .reporter import generate_report
from .scanner import scan_directory
from .svg_visualizer import generate_svg
from .terminal_viz import render_tree, render_graph
from .visualizer import generate_html


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Skillify — Scan AI skills and generate structured indexes with visual graphs."""
    pass


@cli.command()
@click.argument("path")
@click.option("-o", "--output", default="skillify-out", help="Output directory")
@click.option(
    "--patterns", default="SKILL.md,*.md", help="File patterns to scan (comma-separated)"
)
@click.option("--diff", "show_diff", is_flag=True, help="Show what changed since last scan")
@click.option(
    "--check",
    is_flag=True,
    help="Check if index is up to date (exit 1 if stale). For CI gates.",
)
@click.option(
    "--json-output", "json_output", is_flag=True, help="Output machine-readable JSON summary"
)
@click.option("--no-html", is_flag=True, help="Skip HTML visualization output")
@click.option("--no-svg", is_flag=True, help="Skip SVG visualization output")
@click.option("--tree", is_flag=True, help="Show category tree with connections in terminal")
@click.option("--graph", "show_graph", is_flag=True, help="Show connections graph in terminal")
def scan(path, output, patterns, show_diff, check, json_output, no_html, no_svg, tree, show_graph):
    """Scan a directory or GitHub repo for AI skills.

    PATH can be a local directory or GitHub reference (github:user/repo, user/repo, or full URL).

    \b
    Examples:
      skillify scan ./skills/
      skillify scan ./skills/ --diff
      skillify scan ./skills/ --check
      skillify scan github:user/repo --json-output
      skillify scan ./skills/ --no-html --no-svg
    """
    pattern_list = [p.strip() for p in patterns.split(",")]
    quiet = json_output  # Suppress human output when JSON mode is on

    if not quiet:
        click.echo(f"🔍 Scanning: {path}")
        click.echo(f"📁 Output: {output}/")
        click.echo()

    # Scan
    if is_github_ref(path):
        if not quiet:
            click.echo("📡 Cloning GitHub repository...")
        skills = scan_github_repo(path, pattern_list)
    else:
        skills = scan_directory(path, pattern_list)

    if not skills:
        if json_output:
            click.echo(json.dumps({"error": "no_skills_found", "total_skills": 0}))
        else:
            click.echo("⚠️  No skills found. Check your path and patterns.")
        sys.exit(1)

    if not quiet:
        click.echo(f"✅ Found {len(skills)} skills")
        click.echo()

    # Diff against existing index
    existing_index_path = os.path.join(output, "skills-index.json")
    diff_result = None

    if show_diff or check or json_output:
        diff_result = compute_diff(skills, existing_index_path)

    # --check mode: report staleness and exit
    if check:
        if json_output:
            result = diff_to_json(diff_result)
            result["check"] = "stale" if diff_result["is_stale"] else "current"
            click.echo(json.dumps(result, indent=2))
        else:
            if diff_result["is_stale"]:
                click.echo("❌ Index is STALE — changes detected:")
                click.echo(diff_result["summary"])
            else:
                click.echo("✅ Index is up to date.")
        sys.exit(1 if diff_result["is_stale"] else 0)

    # --diff mode: show changes then continue with generation
    if show_diff and not quiet:
        click.echo("📊 Diff:")
        click.echo(diff_result["summary"])
        click.echo()

    # Generate outputs
    if not quiet:
        click.echo("📋 Generating index...")
    generate_index(skills, output, root="" if is_github_ref(path) else path)

    if not quiet:
        click.echo("🔗 Building knowledge graph...")
    graph_data = build_graph(skills)
    write_graph(graph_data, output)

    if not no_html:
        if not quiet:
            click.echo("🎨 Generating interactive visualization...")
        generate_html(graph_data, output)

    if not no_svg:
        if not quiet:
            click.echo("🖼️  Generating SVG graph...")
        generate_svg(graph_data, output)

    if not quiet:
        click.echo("📊 Writing report...")
    generate_report(skills, graph_data, output)

    # Terminal visualization
    if tree:
        render_tree(skills, graph_data)
    if show_graph:
        render_graph(skills, graph_data)

    # JSON output mode
    if json_output:
        result = {
            "total_skills": len(skills),
            "categories": list(set(s.get("category", "uncategorized") for s in skills)),
            "output_dir": output,
            "files": _list_output_files(output, no_html, no_svg),
        }
        if diff_result:
            result["diff"] = diff_to_json(diff_result)
        click.echo(json.dumps(result, indent=2))
        sys.exit(0)

    # Human-readable summary
    click.echo()
    click.echo(f"✨ Done! Output written to {output}/")
    click.echo()
    click.echo(f"  {output}/")
    if not no_html:
        click.echo(f"  ├── graph.html          ← open in browser")
    if not no_svg:
        click.echo(f"  ├── graph.svg           ← embed in README or docs")
    click.echo(f"  ├── graph.json          ← query without re-reading files")
    click.echo(f"  ├── skills-index.json   ← structured index for AI agents")
    click.echo(f"  ├── SKILLS_INDEX.md     ← human-readable table of contents")
    click.echo(f"  └── SKILLIFY_REPORT.md  ← insights and connections")


@cli.command()
@click.argument("query")
@click.option(
    "--index", default="skillify-out/skills-index.json", help="Path to skills index"
)
@click.option("--limit", default=10, help="Max results")
@click.option("--json-output", "json_output", is_flag=True, help="Output as JSON")
def search(query, index, limit, json_output):
    """Search the skills index by keyword."""
    if not os.path.exists(index):
        if json_output:
            click.echo(json.dumps({"error": "index_not_found", "path": index}))
        else:
            click.echo(f"❌ Index not found at {index}. Run `skillify scan` first.")
        sys.exit(1)

    results = search_index(index, query, limit)

    if json_output:
        output = {
            "query": query,
            "total_results": len(results),
            "results": results,
        }
        click.echo(json.dumps(output, indent=2))
        return

    if not results:
        click.echo(f'No skills found matching "{query}"')
        return

    click.echo(f'Found {len(results)} skills matching "{query}":')
    click.echo()
    for i, skill in enumerate(results, 1):
        click.echo(f'  {i}. {skill["name"]}')
        click.echo(f'     {skill.get("description", "No description")}')
        click.echo(f'     Path: {skill["path"]}')
        if skill.get("keywords"):
            click.echo(f'     Keywords: {", ".join(skill["keywords"][:5])}')
        click.echo()


@cli.command()
@click.argument("root", type=click.Path(exists=True, file_okay=False))
def mcp(root):
    """Run as an MCP server, exposing search_skills and load_skill.

    Discovery happens in the agent loop as a tool call, instead of relying on the
    agent to read skills-index.json on its own. Speaks JSON-RPC on stdin/stdout,
    so it is launched by the agent runtime, not run by hand.

    \b
    Examples:
      claude mcp add skillify -- skillify mcp ~/skills-library/
      skillify install mcp --root ~/skills-library/
    """
    from .mcp_server import serve

    # No click.echo in this command: stdout carries the protocol.
    serve(root)


def _list_output_files(output_dir: str, no_html: bool, no_svg: bool) -> list[str]:
    """List the files that were generated.

    Args:
        output_dir: Output directory path.
        no_html: Whether HTML was skipped.
        no_svg: Whether SVG was skipped.

    Returns:
        List of generated file paths relative to output_dir.
    """
    files = []
    if not no_html:
        files.append("graph.html")
    if not no_svg:
        files.append("graph.svg")
    files.extend(["graph.json", "skills-index.json", "SKILLS_INDEX.md", "SKILLIFY_REPORT.md"])
    return files


@cli.command()
@click.argument(
    "platform", type=click.Choice(["mcp", "claude", "codex", "cursor", "opencode", "kiro"])
)
@click.option(
    "--index", default="skillify-out/skills-index.json", help="Path to skills index"
)
@click.option("--root", default=None, help="Skills directory to serve (mcp only)")
@click.option("--project", default=".", help="Project root directory")
def install(platform, index, root, project):
    """Install skillify integration for an AI tool.

    \b
    Supported platforms:
      mcp      - Registers the MCP server in .mcp.json (recommended)
      claude   - Creates .claude/skills/skillify/SKILL.md
      codex    - Appends to AGENTS.md
      cursor   - Creates .cursor/rules/skillify.mdc
      opencode - Appends to AGENTS.md
      kiro     - Creates .kiro/skills/skillify/SKILL.md

    Everything except `mcp` writes an instruction file asking the agent to read
    the index. `mcp` puts discovery in the agent loop as a tool call.

    \b
    Examples:
      skillify install mcp --root ./skills
      skillify install cursor --index my-output/skills-index.json
    """
    from .integrations import install_integration, install_mcp_server, TEMPLATES

    if platform == "mcp":
        _install_mcp(index, root, project, install_mcp_server)
        return

    try:
        file_path = install_integration(platform, index_path=index, project_dir=project)
        desc = TEMPLATES[platform]["description"]
        click.echo(f"✅ Installed {desc}")
        click.echo(f"   → {file_path}")
        click.echo()
        click.echo(f"   Your AI assistant will now consult {index} before starting tasks.")
    except Exception as e:
        click.echo(f"❌ Failed: {e}")
        sys.exit(1)


def _install_mcp(index, root, project, install_mcp_server):
    """Register the MCP server, then recommend how to tier the library."""
    from .tiering import (
        DEMOTED_TIER,
        TIERING_WORTHWHILE_AT,
        in_native_listing,
        recommend_tiers,
    )

    root = root or _root_from_index(index)
    if not root:
        click.echo("❌ Need a skills directory. Pass --root ./skills")
        click.echo("   (or run `skillify scan ./skills` first so the root is recorded)")
        sys.exit(1)

    if not os.path.isdir(root):
        click.echo(f"❌ Not a directory: {root}")
        sys.exit(1)

    try:
        config_path = install_mcp_server(root, project_dir=project)
    except Exception as e:
        click.echo(f"❌ Failed: {e}")
        sys.exit(1)

    click.echo(f"✅ Registered MCP server → {config_path}")
    click.echo(f"   Serving skills from {os.path.abspath(root)}")
    click.echo()

    skills = scan_directory(root)
    if not skills:
        click.echo(f"⚠️  No skills found in {root}.")
        return

    # skillOverrides is keyed by the names Claude Code discovers. A library kept
    # outside its skill directories is not in the listing at all, so there is
    # nothing to demote and an overrides block would apply to nothing.
    if not in_native_listing(root, project):
        click.echo(f"   {len(skills)} skills, and none of them are in Claude Code's")
        click.echo("   native listing — this library sits outside .claude/skills/ and")
        click.echo("   ~/.claude/skills/. That is the setup you want: they cost nothing")
        click.echo("   until search_skills finds them, so there is nothing to demote.")
        return

    if len(skills) < TIERING_WORTHWHILE_AT:
        click.echo(f"   {len(skills)} skills — the native listing handles this fine, so")
        click.echo("   there is nothing worth demoting yet. search_skills is available")
        click.echo(f"   either way; revisit tiering past ~{TIERING_WORTHWHILE_AT} skills.")
        return

    tiers = recommend_tiers(skills)

    click.echo("⚠️  Registering the server does not shrink your context on its own.")
    click.echo("   Claude Code still lists every skill it discovers, so right now")
    click.echo("   search_skills is a second discovery path on top of the listing.")
    click.echo("   Demote the long tail to get the benefit:")
    click.echo()

    click.echo(f"   Keep always-on ({len(tiers['always_on'])}):")
    for entry in tiers["always_on"]:
        click.echo(f"     • {entry['name']} — {entry['reason']}")
    click.echo()

    click.echo(f"   Move behind search ({len(tiers['demoted'])}):")
    for entry in tiers["demoted"]:
        click.echo(f"     • {entry['name']} — {entry['reason']}")
    click.echo()

    if not tiers["demoted"]:
        click.echo("   Library is small enough that tiering would not buy you anything.")
        return

    click.echo(f'   "{DEMOTED_TIER}" hides a skill from the model\'s listing but keeps')
    click.echo("   /name working for you — and search_skills still finds it.")
    click.echo()
    click.echo("   Add to .claude/settings.json (merges across settings scopes):")
    click.echo()
    for line in json.dumps({"skillOverrides": tiers["overrides"]}, indent=2).splitlines():
        click.echo(f"   {line}")

    if tiers["duplicate_names"]:
        click.echo()
        click.echo("⚠️  skillOverrides is keyed by skill name, and these are duplicated —")
        click.echo("   an entry will apply to every skill sharing the name:")
        for name in tiers["duplicate_names"]:
            click.echo(f"     • {name}")

    click.echo()
    click.echo("   Nothing was written to settings.json — this changes what the model")
    click.echo("   can see, so it is yours to apply.")


def _root_from_index(index_path: str) -> str:
    """Read the scanned root recorded in a skills index, if available."""
    if not os.path.exists(index_path):
        return ""
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f).get("root", "")
    except (json.JSONDecodeError, OSError):
        return ""


@cli.command()
@click.argument("platform", type=click.Choice(["claude", "codex", "cursor", "opencode", "kiro"]))
@click.option("--project", default=".", help="Project root directory")
def uninstall(platform, project):
    """Remove skillify integration for an AI tool."""
    from .integrations import uninstall_integration

    removed = uninstall_integration(platform, project_dir=project)
    if removed:
        click.echo(f"✅ Removed skillify integration for {platform}")
    else:
        click.echo(f"ℹ️  No skillify integration found for {platform}")


if __name__ == "__main__":
    cli()
