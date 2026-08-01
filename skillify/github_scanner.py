"""GitHub repository scanner for AI skill folders.

This module handles fetching and scanning GitHub repositories,
cloning them locally, and extracting skill metadata using the
local filesystem scanner.
"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from skillify import scanner


# Pattern to match GitHub references in various formats
_GITHUB_PATTERNS = [
    re.compile(r"^github:(?P<owner>[^/]+)/(?P<repo>[^/\s]+)$"),
    re.compile(r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/\s.]+?)(?:\.git)?$"),
    re.compile(r"^(?P<owner>[a-zA-Z0-9_.-]+)/(?P<repo>[a-zA-Z0-9_.-]+)$"),
]


class GitNotFoundError(Exception):
    """Raised when git is not available on the system."""


class CloneError(Exception):
    """Raised when git clone fails."""


class InvalidGitHubRef(ValueError):
    """Raised when a GitHub reference cannot be parsed."""


def _check_git_available() -> None:
    """Verify that git is available on PATH.

    Raises:
        GitNotFoundError: If git executable is not found.
    """
    try:
        subprocess.run(
            ["git", "--version"],
            capture_output=True,
            check=True,
        )
    except FileNotFoundError:
        raise GitNotFoundError(
            "git is not installed or not available on PATH. "
            "Install git to use GitHub scanning features."
        )
    except subprocess.CalledProcessError as exc:
        raise GitNotFoundError(
            f"git check failed: {exc.stderr.decode().strip()}"
        )


def is_github_ref(path: str) -> bool:
    """Check if a path looks like a GitHub reference.

    Returns True for formats like:
    - 'github:user/repo'
    - 'https://github.com/user/repo'
    - 'user/repo' (two-part slash-separated identifier with no other path separators)

    Args:
        path: The path or reference string to check.

    Returns:
        True if path matches a known GitHub reference format.
    """
    if not path or not isinstance(path, str):
        return False

    # Explicit github: prefix
    if path.startswith("github:"):
        return True

    # GitHub HTTPS URL
    if re.match(r"^https?://github\.com/[^/]+/[^/\s]+", path):
        return True

    # Short form: owner/repo (exactly one slash, no path separators beyond that)
    # Exclude things that look like local paths (starting with /, ./, ../)
    if path.startswith(("/", "./", "../")):
        return False
    if os.path.sep in path and os.path.sep != "/":
        return False
    parts = path.split("/")
    if len(parts) == 2 and all(
        re.match(r"^[a-zA-Z0-9_.-]+$", p) for p in parts
    ):
        return True

    return False


def parse_github_url(url: str) -> tuple[str, str]:
    """Parse a GitHub reference into (owner, repo) tuple.

    Accepts formats:
    - 'github:user/repo'
    - 'https://github.com/user/repo'
    - 'https://github.com/user/repo.git'
    - 'user/repo'

    Args:
        url: The GitHub reference string.

    Returns:
        Tuple of (owner, repo_name).

    Raises:
        InvalidGitHubRef: If the URL cannot be parsed as a GitHub reference.
    """
    if not url or not isinstance(url, str):
        raise InvalidGitHubRef(f"Invalid GitHub reference: {url!r}")

    url = url.strip()

    for pattern in _GITHUB_PATTERNS:
        match = pattern.match(url)
        if match:
            owner = match.group("owner")
            repo = match.group("repo")
            # Strip trailing .git if present
            repo = repo.removesuffix(".git")
            return (owner, repo)

    raise InvalidGitHubRef(
        f"Cannot parse GitHub reference: {url!r}. "
        f"Expected formats: 'github:user/repo', 'https://github.com/user/repo', or 'user/repo'"
    )


def _normalize_to_https(repo_ref: str) -> str:
    """Normalize any GitHub reference to an HTTPS clone URL.

    Args:
        repo_ref: GitHub reference in any supported format.

    Returns:
        HTTPS URL suitable for git clone.
    """
    owner, repo = parse_github_url(repo_ref)
    return f"https://github.com/{owner}/{repo}.git"


def clone_repo(repo_url: str, target_dir: str = None) -> str:
    """Clone a GitHub repository locally.

    Performs a shallow clone (--depth 1) for speed. Accepts multiple
    GitHub reference formats and normalizes to HTTPS.

    Args:
        repo_url: GitHub reference in any supported format
            ('github:user/repo', 'https://github.com/user/repo', 'user/repo').
        target_dir: Optional directory to clone into. If None, a temporary
            directory is created.

    Returns:
        Path to the cloned repository directory.

    Raises:
        GitNotFoundError: If git is not installed.
        CloneError: If the clone operation fails.
        InvalidGitHubRef: If repo_url cannot be parsed.
    """
    _check_git_available()

    https_url = _normalize_to_https(repo_url)
    owner, repo = parse_github_url(repo_url)

    if target_dir is None:
        target_dir = tempfile.mkdtemp(prefix=f"skillify_{owner}_{repo}_")
    else:
        target_dir = str(Path(target_dir).resolve())
        os.makedirs(target_dir, exist_ok=True)

    clone_path = os.path.join(target_dir, repo)

    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", https_url, clone_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        # Clean up partial clone on timeout
        if os.path.exists(clone_path):
            shutil.rmtree(clone_path, ignore_errors=True)
        raise CloneError(
            f"Clone of {https_url} timed out after 120 seconds."
        )
    except OSError as exc:
        raise CloneError(f"Failed to run git clone: {exc}")

    if result.returncode != 0:
        # Clean up on failure
        if os.path.exists(clone_path):
            shutil.rmtree(clone_path, ignore_errors=True)
        stderr = result.stderr.strip()
        raise CloneError(
            f"git clone failed for {https_url} (exit code {result.returncode}): {stderr}"
        )

    return clone_path


def scan_github_repo(
    repo_ref: str, patterns: list[str] = None
) -> list[dict]:
    """Clone and scan a GitHub repository for skill metadata.

    Clones the repository to a temporary directory, scans it using
    the local filesystem scanner, and cleans up afterwards.

    Args:
        repo_ref: GitHub reference in any supported format.
        patterns: Optional list of file glob patterns to match
            (e.g., ['*.md', '*.yaml']). Passed to scanner.scan_directory.

    Returns:
        List of skill metadata dictionaries found in the repository.

    Raises:
        GitNotFoundError: If git is not installed.
        CloneError: If the clone operation fails.
        InvalidGitHubRef: If repo_ref cannot be parsed.
    """
    tmp_base = tempfile.mkdtemp(prefix="skillify_scan_")
    clone_path = None

    try:
        clone_path = clone_repo(repo_ref, target_dir=tmp_base)

        # Call the local scanner on the cloned directory
        kwargs = {}
        if patterns is not None:
            kwargs["patterns"] = patterns

        results = scanner.scan_directory(clone_path, **kwargs)
        return results

    finally:
        # Always clean up the temporary directory
        if os.path.exists(tmp_base):
            shutil.rmtree(tmp_base, ignore_errors=True)
