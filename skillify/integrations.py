"""Platform integration templates for AI tools.

Generates configuration files that teach AI assistants to use the skillify index
for on-demand skill discovery.

The templates below are the weaker integration: they ask the agent to read a file
and trust that it does. `install_mcp_server` is the stronger one — it registers
skillify as an MCP server, so discovery becomes a tool call in the agent loop.
"""

import json
import os
from pathlib import Path

TEMPLATES: dict[str, dict] = {
    "claude": {
        "path": ".claude/skills/skillify/SKILL.md",
        "description": "Claude Code / Kiro skill",
        "content": """---
name: Skill Loader
description: Load skills on demand from the skillify index
---

# Skill Loader

Before attempting any task, check if a relevant skill exists.

## Workflow

1. Read `{index_path}` to see available skills
2. Search for keywords matching the current task
3. If a match is found, read the skill file at the path specified
4. Follow the skill's instructions for that task

## Rules

- Never load all skills at once — use the index for discovery
- Only load a skill when its keywords match the current task
- After completing the task, you can discard the skill from context
- If no skill matches, proceed without one

## Index Location

`{index_path}`
""",
    },
    "codex": {
        "path": "AGENTS.md",
        "description": "Codex / OpenAI AGENTS.md",
        "append": True,
        "content": """
## Skills (via Skillify)

This project uses [skillify](https://github.com/raunakkathuria/skillify) for on-demand skill loading.

**Before starting any task:**
1. Read `{index_path}` for available skills
2. Search by keyword for the current task
3. If matched, read the full skill at the specified path
4. Follow its instructions

Index location: `{index_path}`
""",
    },
    "cursor": {
        "path": ".cursor/rules/skillify.mdc",
        "description": "Cursor rules file",
        "content": """---
alwaysApply: true
---

# Skill Discovery (Skillify)

Before starting any task, check if a relevant skill exists:

1. Read `{index_path}`
2. Match the task against skill names, descriptions, and keywords
3. If matched, read the full skill at the specified path
4. Follow its instructions

Do not load all skills at once. Use the index to find only what's needed.
""",
    },
    "opencode": {
        "path": "AGENTS.md",
        "description": "OpenCode / Gemini CLI / generic AGENTS.md",
        "append": True,
        "content": """
## On-Demand Skills (Skillify)

Skills index: `{index_path}`

**Workflow:**
1. Before each task, search the index for matching keywords
2. Load only the matched skill file (path field in the index)
3. Follow the skill instructions
4. Do not load all skills — use the index for discovery
""",
    },
    "kiro": {
        "path": ".kiro/skills/skillify/SKILL.md",
        "description": "Kiro IDE/CLI skill",
        "content": """---
name: Skill Loader
description: Load skills on demand from the skillify index
---

# Skill Loader

Before attempting any task, check if a relevant skill exists.

## Workflow

1. Read `{index_path}` to see available skills
2. Search for keywords matching the current task
3. If a match is found, read the skill file at the path specified
4. Follow the skill's instructions for that task

## Rules

- Never load all skills at once — use the index for discovery
- Only load a skill when its keywords match the current task
- After completing the task, you can discard the skill from context

## Index Location

`{index_path}`
""",
    },
}

SUPPORTED_PLATFORMS = list(TEMPLATES.keys())


def install_integration(
    platform: str,
    index_path: str = "skillify-out/skills-index.json",
    project_dir: str = ".",
) -> str:
    """Install the skillify integration for a given AI platform.

    Creates the appropriate configuration file that teaches the AI assistant
    to consult the skillify index before starting tasks.

    Args:
        platform: Target platform (claude, codex, cursor, opencode, kiro).
        index_path: Path to the skills-index.json relative to project root.
        project_dir: Project root directory.

    Returns:
        The path of the created/updated file.

    Raises:
        ValueError: If platform is not supported.
    """
    if platform not in TEMPLATES:
        raise ValueError(
            f"Unknown platform: {platform!r}. "
            f"Supported: {', '.join(SUPPORTED_PLATFORMS)}"
        )

    template = TEMPLATES[platform]
    file_path = os.path.join(project_dir, template["path"])
    content = template["content"].format(index_path=index_path)

    # Create parent directories
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    if template.get("append") and os.path.exists(file_path):
        # Check if already installed
        with open(file_path, "r", encoding="utf-8") as f:
            existing = f.read()
        if "Skillify" in existing or "skillify" in existing:
            return file_path  # Already installed
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(content)
    else:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content.lstrip("\n"))

    return file_path


def install_mcp_server(root: str, project_dir: str = ".", server_name: str = "skillify") -> str:
    """Register skillify as an MCP server in the project's .mcp.json.

    Merges into any existing config rather than overwriting it.

    Args:
        root: Skills directory the server should scan.
        project_dir: Project root containing (or to contain) .mcp.json.
        server_name: Key to register under.

    Returns:
        The path of the written file.
    """
    os.makedirs(project_dir, exist_ok=True)
    config_path = os.path.join(project_dir, ".mcp.json")

    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            # Refuse to clobber a file we cannot parse.
            raise ValueError(f"{config_path} exists but is not valid JSON — fix or move it first")

    servers = config.setdefault("mcpServers", {})
    servers[server_name] = {
        "command": "skillify",
        "args": ["mcp", os.path.abspath(root)],
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return config_path


def uninstall_integration(platform: str, project_dir: str = ".") -> bool:
    """Remove the skillify integration for a given platform.

    Args:
        platform: Target platform.
        project_dir: Project root directory.

    Returns:
        True if a file was removed, False if nothing was found.
    """
    if platform not in TEMPLATES:
        return False

    template = TEMPLATES[platform]
    file_path = os.path.join(project_dir, template["path"])

    if not os.path.exists(file_path):
        return False

    if template.get("append"):
        # For appended files, remove the skillify section
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        lines = content.split("\n")
        new_lines = []
        skip = False
        for line in lines:
            if "Skillify" in line and line.startswith("##"):
                skip = True
                continue
            if skip and line.startswith("## ") and "Skillify" not in line:
                skip = False
            if not skip:
                new_lines.append(line)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines))
        return True
    else:
        os.remove(file_path)
        return True
