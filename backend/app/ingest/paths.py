"""File access rules for an analysed repository.

Every read of repository content goes through this module so that paths
stay inside the repository root and oversized, binary or vendored files
are never indexed or returned.
"""

import os
from pathlib import Path

MAX_FILE_BYTES = 1_000_000
MAX_FILES = 5_000
SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", ".tox", ".nox",
    "site-packages", "node_modules", "build", "dist", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
}


class PathError(ValueError):
    """A path is outside the repository or not allowed."""


class RepoTooLarge(ValueError):
    """The repository has more files than MAX_FILES."""


def resolve_inside(root: Path, rel_path: str) -> Path:
    """Return the canonical path of rel_path, rejecting anything outside root."""
    root = root.resolve()
    target = (root / rel_path).resolve()
    if target != root and root not in target.parents:
        raise PathError(f"path is outside the repository: {rel_path}")
    rel_parts = target.relative_to(root).parts
    if any(part in SKIP_DIRS for part in rel_parts):
        raise PathError(f"path is in a skipped directory: {rel_path}")
    return target


def is_binary(path: Path) -> bool:
    with path.open("rb") as f:
        return b"\0" in f.read(8192)


def check_readable(root: Path, rel_path: str) -> Path:
    """Resolve rel_path and check it is a regular, small, text file."""
    path = resolve_inside(root, rel_path)
    if not path.is_file():
        raise PathError(f"not a file: {rel_path}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise PathError(f"file is over {MAX_FILE_BYTES} bytes: {rel_path}")
    if is_binary(path):
        raise PathError(f"binary file: {rel_path}")
    return path


def _is_venv(dir_path: Path) -> bool:
    return (dir_path / "pyvenv.cfg").is_file()


def iter_files(root: Path) -> list[str]:
    """List indexable files as POSIX paths relative to root.

    Skips vendored/build directories, virtualenvs, symlinks leaving the root,
    binaries and oversized files. Raises RepoTooLarge past MAX_FILES files.
    """
    root = root.resolve()
    files: list[str] = []
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = sorted(
            d for d in dirnames if d not in SKIP_DIRS and not _is_venv(current / d)
        )
        for name in sorted(filenames):
            seen += 1
            if seen > MAX_FILES:
                raise RepoTooLarge(f"repository has more than {MAX_FILES} files")
            rel = (current / name).relative_to(root).as_posix()
            try:
                check_readable(root, rel)
            except (PathError, OSError):
                continue
            files.append(rel)
    return files
