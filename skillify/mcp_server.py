"""MCP stdio server exposing skill discovery as tools the agent can call.

Speaks newline-delimited JSON-RPC 2.0 over stdin/stdout. This is a few hundred
lines against a stable protocol, so it is hand-rolled rather than pulling in the
`mcp` SDK (which brings pydantic, anyio, httpx and starlette with it).

Two rules that decide whether a client connects at all:

1. Nothing but JSON-RPC may reach stdout. All logging goes to stderr.
2. One message per line. Not LSP-style Content-Length framing.

Why tools rather than an instruction file: a `search_skills` tool is present in
the tool schema and callable mid-task, whereas "read skills-index.json first" is
a request the model may skip. Note this does not by itself shrink context — see
`tiering.py` for the half that does.
"""

import json
import os
import sys

from .indexer import search_skills
from .scanner import scan_directory

# Protocol revisions we know how to speak. A client asking for one of these gets
# it echoed back; anything else gets DEFAULT and a note on stderr.
SUPPORTED_PROTOCOL_VERSIONS = frozenset(
    {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
)
DEFAULT_PROTOCOL_VERSION = "2025-06-18"

# A SKILL.md far larger than this is a documentation file, not an instruction.
MAX_SKILL_BYTES = 100_000

SERVER_NAME = "skillify"
SERVER_VERSION = "0.1.0"


class ToolError(Exception):
    """A tool failed in a way the model should see and can recover from."""


def _log(message: str) -> None:
    """Write a diagnostic to stderr. Never stdout — that carries the protocol."""
    print(f"[skillify-mcp] {message}", file=sys.stderr, flush=True)


class SkillServer:
    """Serves skill search and loading over MCP for one skills root."""

    def __init__(self, root: str):
        """Scan `root` and hold the metadata in memory.

        Scanning at startup rather than reading a prebuilt index means there is
        no staleness window in which the server hands out a path to a file that
        has since been renamed, and no "did you run scan first" failure mode.

        Args:
            root: Directory to scan for skills.
        """
        self.root = os.path.realpath(root)
        if not os.path.isdir(self.root):
            raise NotADirectoryError(f"not a directory: {root}")

        self.skills = scan_directory(self.root)
        self.by_id = {skill["id"]: skill for skill in self.skills}
        self.categories = sorted(
            {s.get("category") for s in self.skills if s.get("category")}
        )

    # -- tool definitions ------------------------------------------------

    def tool_definitions(self) -> list[dict]:
        """Describe the tools, including what is actually in this library.

        The descriptions carry most of the weight here: they are the only thing
        telling the model a searchable library exists, so they name the size and
        subject matter rather than describing search in the abstract.
        """
        covering = f" covering {', '.join(self.categories)}" if self.categories else ""
        return [
            {
                "name": "search_skills",
                "description": (
                    f"Search this project's library of {len(self.skills)} reusable "
                    f"skills{covering}. Each skill is a vetted procedure for one kind "
                    "of task. Call this before starting work to check whether a "
                    "relevant skill exists — describe the task in your own words, "
                    "full sentences are fine. Returns skill ids and descriptions; "
                    "pass an id to load_skill to get the full instructions."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What you are trying to do, in your own words.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 10).",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "load_skill",
                "description": (
                    "Load a skill's full instructions by id, as returned by "
                    "search_skills. Also returns the skill's directory, so you can "
                    "read any scripts or reference files it mentions."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "skill_id": {
                            "type": "string",
                            "description": "Skill id from search_skills.",
                        },
                    },
                    "required": ["skill_id"],
                },
            },
        ]

    # -- tools -----------------------------------------------------------

    def search(self, query: str, limit: int = 10) -> dict:
        """Rank skills against a natural-language query.

        Deliberately returns no file paths and no body content: discovery stays
        cheap, and `load_skill` remains the only route to a file, so every read
        goes through the containment check.
        """
        if not isinstance(query, str) or not query.strip():
            raise ToolError("query must be a non-empty string")

        matches = search_skills(self.skills, query, _clamp_limit(limit))
        return {
            "query": query,
            "total_matches": len(matches),
            "results": [
                {
                    "skill_id": m["id"],
                    "name": m.get("name", ""),
                    "description": m.get("description", ""),
                    "category": m.get("category", ""),
                    "keywords": m.get("keywords", []),
                }
                for m in matches
            ],
        }

    def load(self, skill_id: str) -> dict:
        """Return a skill's contents and its directory.

        The directory matters: skills refer to bundled files relatively
        ("run scripts/check.py"), and the agent cannot resolve those from the
        text alone.
        """
        if not isinstance(skill_id, str) or not skill_id.strip():
            raise ToolError("skill_id must be a non-empty string")

        skill = self.by_id.get(skill_id.strip())
        if skill is None:
            raise ToolError(
                f"no skill with id {skill_id!r}. Use search_skills to find valid ids."
            )

        path = self._resolve(skill)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read(MAX_SKILL_BYTES + 1)

        truncated = len(content) > MAX_SKILL_BYTES
        if truncated:
            content = content[:MAX_SKILL_BYTES]

        return {
            "skill_id": skill["id"],
            "name": skill.get("name", ""),
            "directory": os.path.dirname(path),
            "content": content,
            "truncated": truncated,
        }

    def _resolve(self, skill: dict) -> str:
        """Resolve a skill's path, refusing anything outside the root.

        `skill_id` arrives from a model that may be relaying untrusted text, so
        the resolved path is checked even though it came from our own scan.
        """
        path = os.path.realpath(os.path.join(self.root, skill["path"]))
        if path != self.root and not path.startswith(self.root + os.sep):
            raise ToolError("skill path resolves outside the skills root")
        if not os.path.isfile(path):
            raise ToolError(f"skill file is gone: {skill['path']}")
        return path

    # -- JSON-RPC dispatch -----------------------------------------------

    def respond(self, request: dict) -> dict:
        """Build a JSON-RPC response for one request."""
        request_id = request.get("id")
        method = request.get("method")

        try:
            result = self._dispatch(method, request.get("params") or {})
        except _MethodNotFound:
            return _error(request_id, -32601, f"Method not found: {method}")
        except ToolError as exc:
            # Tool failures come back as a result, not a protocol error, so the
            # model reads the message and can retry.
            return _ok(request_id, _tool_result(str(exc), is_error=True))
        except Exception as exc:  # noqa: BLE001 - a crash must not kill the server
            _log(f"unhandled error in {method}: {exc!r}")
            return _error(request_id, -32603, f"Internal error: {exc}")

        return _ok(request_id, result)

    def _dispatch(self, method: str, params: dict):
        """Route a method to its handler."""
        if method == "initialize":
            return self._initialize(params)

        if method == "tools/list":
            return {"tools": self.tool_definitions()}

        if method == "tools/call":
            return self._call_tool(params)

        if method == "ping":
            return {}

        raise _MethodNotFound(method)

    def _initialize(self, params: dict) -> dict:
        """Handle the handshake, agreeing on a protocol version."""
        requested = params.get("protocolVersion")
        client = (params.get("clientInfo") or {}).get("name", "unknown")

        if requested in SUPPORTED_PROTOCOL_VERSIONS:
            version = requested
        else:
            version = DEFAULT_PROTOCOL_VERSION
            _log(f"client {client} requested protocolVersion {requested!r}; using {version}")

        return {
            "protocolVersion": version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }

    def _call_tool(self, params: dict) -> dict:
        """Run a named tool and wrap its output as MCP tool content."""
        name = params.get("name")
        arguments = params.get("arguments") or {}

        if name == "search_skills":
            payload = self.search(arguments.get("query"), arguments.get("limit", 10))
        elif name == "load_skill":
            payload = self.load(arguments.get("skill_id"))
        else:
            raise ToolError(f"unknown tool: {name!r}")

        return _tool_result(json.dumps(payload, indent=2, ensure_ascii=False))


class _MethodNotFound(Exception):
    """The client asked for a JSON-RPC method this server does not implement."""


def _clamp_limit(limit) -> int:
    """Coerce a client-supplied limit into a sane range."""
    try:
        return max(1, min(50, int(limit)))
    except (TypeError, ValueError):
        return 10


def _tool_result(text: str, is_error: bool = False) -> dict:
    """Wrap text as an MCP tools/call result."""
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _ok(request_id, result: dict) -> dict:
    """Build a JSON-RPC success response."""
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id, code: int, message: str) -> dict:
    """Build a JSON-RPC error response."""
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _write(message: dict, out) -> None:
    """Emit one JSON-RPC message as a single line."""
    out.write(json.dumps(message, ensure_ascii=False) + "\n")
    out.flush()


def serve(root: str, stdin=None, stdout=None) -> None:
    """Run the stdio server loop until stdin closes.

    Args:
        root: Directory to scan for skills.
        stdin: Input stream, defaults to sys.stdin. Injectable for tests.
        stdout: Output stream, defaults to sys.stdout. Injectable for tests.
    """
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout

    server = SkillServer(root)
    _log(f"indexed {len(server.skills)} skills from {server.root}")

    for line in stdin:
        line = line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            _log(f"parse error: {exc}")
            _write(_error(None, -32700, "Parse error"), stdout)
            continue

        # No id means it is a notification (e.g. notifications/initialized).
        # Responding to one is a protocol error.
        if not isinstance(message, dict) or "id" not in message:
            _log(f"notification: {message.get('method') if isinstance(message, dict) else '?'}")
            continue

        _write(server.respond(message), stdout)

    _log("stdin closed, exiting")
