"""Tests for the MCP stdio server: protocol framing, tools, and path safety."""

import io
import json

import pytest

from skillify.mcp_server import (
    DEFAULT_PROTOCOL_VERSION,
    MAX_SKILL_BYTES,
    SkillServer,
    ToolError,
    serve,
)

from conftest import write_skill


def run_server(root, messages):
    """Feed JSON-RPC messages through the server loop and parse the output lines.

    Args:
        root: Skills directory to serve.
        messages: Iterable of dicts to send, one per line.

    Returns:
        List of parsed response dicts, in order.
    """
    stdin = io.StringIO("".join(json.dumps(m) + "\n" for m in messages))
    stdout = io.StringIO()
    serve(str(root), stdin=stdin, stdout=stdout)

    # Every line must be pure JSON — stray output on stdout breaks the transport.
    return [json.loads(line) for line in stdout.getvalue().splitlines()]


def call(root, tool, arguments):
    """Call one tool and return the parsed payload plus the isError flag."""
    responses = run_server(
        root,
        [{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
          "params": {"name": tool, "arguments": arguments}}],
    )
    result = responses[0]["result"]
    return result, result["content"][0]["text"]


# -- protocol ------------------------------------------------------------


def test_notifications_get_no_response(library):
    """Responding to a notification is a protocol error."""
    responses = run_server(
        library,
        [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "ping"},
        ],
    )

    assert [r["id"] for r in responses] == [1, 2]


def test_initialize_echoes_known_protocol_version(library):
    """A client asking for a version we speak should get it back."""
    responses = run_server(
        library,
        [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2024-11-05", "capabilities": {}}}],
    )

    assert responses[0]["result"]["protocolVersion"] == "2024-11-05"
    assert responses[0]["result"]["capabilities"] == {"tools": {}}


def test_initialize_falls_back_for_unknown_version(library):
    """An unrecognised version must not be echoed back blindly."""
    responses = run_server(
        library,
        [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "1999-01-01", "capabilities": {}}}],
    )

    assert responses[0]["result"]["protocolVersion"] == DEFAULT_PROTOCOL_VERSION


def test_unknown_method_returns_method_not_found(library):
    """Unknown methods are a JSON-RPC error, not a crash."""
    responses = run_server(library, [{"jsonrpc": "2.0", "id": 1, "method": "nope"}])

    assert responses[0]["error"]["code"] == -32601


def test_malformed_line_returns_parse_error_and_keeps_serving(library):
    """One bad line must not take the server down."""
    stdin = io.StringIO('not json\n{"jsonrpc":"2.0","id":2,"method":"ping"}\n')
    stdout = io.StringIO()
    serve(str(library), stdin=stdin, stdout=stdout)

    responses = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert responses[0]["error"]["code"] == -32700
    assert responses[1]["id"] == 2


def test_tools_list_advertises_both_tools(library):
    """The two tools are the whole public surface."""
    responses = run_server(library, [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}])
    tools = responses[0]["result"]["tools"]

    assert {t["name"] for t in tools} == {"search_skills", "load_skill"}
    # The description is what tells the model a library exists at all.
    assert "3" in next(t for t in tools if t["name"] == "search_skills")["description"]


# -- tools ---------------------------------------------------------------


def test_search_returns_ids_but_no_paths(library):
    """Paths are relative to a root the model does not know; ids are the API."""
    _, text = call(library, "search_skills", {"query": "review a pull request"})
    payload = json.loads(text)

    assert payload["results"][0]["skill_id"] == "code-review"
    assert "path" not in payload["results"][0]


def test_load_returns_content_and_directory(library):
    """The directory lets the agent resolve files the skill refers to relatively."""
    _, text = call(library, "load_skill", {"skill_id": "database-migration"})
    payload = json.loads(text)

    assert "rollback" in payload["content"]
    assert payload["directory"].endswith("db-migration")
    assert not payload["truncated"]


def test_oversized_skill_is_truncated_and_says_so(library):
    """Silent mid-instruction truncation would produce a confusing agent failure."""
    padding = "\n".join(f"filler line {i}" for i in range(20_000))
    (library / "db-migration" / "SKILL.md").write_text(
        "---\nname: Database Migration\ndescription: Huge\n---\n\n" + padding
    )

    _, text = call(library, "load_skill", {"skill_id": "database-migration"})
    payload = json.loads(text)

    assert payload["truncated"] is True
    assert len(payload["content"]) == MAX_SKILL_BYTES


def test_load_unknown_id_is_a_tool_error(library):
    """Tool failures come back as results so the model can recover."""
    result, text = call(library, "load_skill", {"skill_id": "does-not-exist"})

    assert result["isError"] is True
    assert "search_skills" in text


def test_unknown_tool_is_a_tool_error(library):
    """An unknown tool name should not read as a protocol failure."""
    result, _ = call(library, "nonsense", {})

    assert result["isError"] is True


def test_empty_query_is_a_tool_error(library):
    """Better an explicit message than silently returning the whole library."""
    result, _ = call(library, "search_skills", {"query": "   "})

    assert result["isError"] is True


def test_search_limit_is_clamped(library):
    """A client-supplied limit must not be trusted verbatim."""
    _, text = call(library, "search_skills", {"query": "infrastructure", "limit": 9999})

    assert len(json.loads(text)["results"]) <= 50


# -- path safety ---------------------------------------------------------


def test_path_outside_root_is_refused(library, tmp_path):
    """skill_id comes from a model that may be relaying untrusted text."""
    secret = tmp_path.parent / "outside-secret.md"
    secret.write_text("should not be readable")

    server = SkillServer(str(library))
    server.by_id["escape"] = {"id": "escape", "path": f"../{secret.name}", "name": "Escape"}

    with pytest.raises(ToolError, match="outside the skills root"):
        server.load("escape")


def test_deleted_skill_file_is_reported(library):
    """The library can change under a long-running server."""
    server = SkillServer(str(library))
    (library / "code-review" / "SKILL.md").unlink()

    with pytest.raises(ToolError, match="gone"):
        server.load("code-review")


def test_server_rejects_a_non_directory(tmp_path):
    """Fail at startup rather than serving an empty library."""
    target = tmp_path / "file.md"
    target.write_text("x")

    with pytest.raises(NotADirectoryError):
        SkillServer(str(target))


# -- the load-bearing claim ---------------------------------------------


def test_demoted_skills_remain_searchable_and_loadable(library):
    """The whole architecture rests on this.

    A skill demoted with `skillOverrides: user-invocable-only` is hidden from
    Claude Code's native listing. Skillify scans the filesystem directly, so it
    must still find and load that skill — otherwise demoting the long tail loses
    it rather than relocating it.
    """
    write_skill(
        library / "obscure",
        "Obscure Runbook",
        "Recover the sharded ledger after a partial replica failure",
        keywords=["ledger", "replica", "recovery"],
        category="operations",
    )
    (library / ".claude").mkdir()
    (library / ".claude" / "settings.json").write_text(
        json.dumps({"skillOverrides": {"Obscure Runbook": "user-invocable-only"}})
    )

    _, text = call(library, "search_skills", {"query": "recover a failed ledger replica"})
    payload = json.loads(text)
    assert payload["results"][0]["skill_id"] == "obscure-runbook"

    _, text = call(library, "load_skill", {"skill_id": "obscure-runbook"})
    assert "sharded ledger" in json.loads(text)["content"]
