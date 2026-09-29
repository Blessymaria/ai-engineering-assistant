"""Load a repository from a Git URL or a local path."""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.ingest.paths import iter_files

URL_RE = re.compile(r"^(https?://|git@)[\w.@:/~-]+?(\.git)?/?$")


class LoadError(ValueError):
    """The repository could not be loaded."""


@dataclass
class Repo:
    root: Path
    commit: str | None
    files: list[str]


def _git(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        raise LoadError(result.stderr.strip() or f"git {args[0]} failed")
    return result.stdout.strip()


def _repo_name(url: str) -> str:
    name = url.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    return re.sub(r"\.git$", "", name) or "repo"


def clone(url: str, workspace: Path) -> Path:
    """Shallow-clone url into workspace, reusing an existing clone."""
    if not URL_RE.match(url):
        raise LoadError(f"not a supported Git URL: {url}")
    target = workspace / _repo_name(url)
    if (target / ".git").is_dir():
        return target
    workspace.mkdir(parents=True, exist_ok=True)
    # Full history (git_log/git_blame need it); submodules are not fetched and no repository code is run.
    _git(["clone", "--no-tags", "--", url, str(target)])
    return target


def commit_of(root: Path) -> str | None:
    try:
        return _git(["rev-parse", "HEAD"], cwd=root)
    except (LoadError, OSError):
        return None


def load_repo(source: str, workspace: Path) -> Repo:
    """Load a repository from a local directory or a Git URL."""
    local = Path(source).expanduser()
    if local.is_dir():
        root = local.resolve()
    else:
        root = clone(source, workspace).resolve()
    return Repo(root=root, commit=commit_of(root), files=iter_files(root))
