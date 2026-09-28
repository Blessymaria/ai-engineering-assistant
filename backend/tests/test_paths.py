import os
from pathlib import Path

import pytest

from app.ingest import paths
from app.ingest.loader import LoadError, clone, load_repo
from app.ingest.paths import PathError, RepoTooLarge, check_readable, iter_files, resolve_inside


def write(root: Path, rel: str, content: str | bytes = "x = 1\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content)


def test_resolve_inside_allows_repo_paths(tmp_path):
    write(tmp_path, "app/main.py")
    assert resolve_inside(tmp_path, "app/main.py") == (tmp_path / "app/main.py").resolve()
    assert resolve_inside(tmp_path, "app/../app/main.py") == (tmp_path / "app/main.py").resolve()


@pytest.mark.parametrize("bad", ["../secret.txt", "app/../../secret.txt", "/etc/passwd", "C:/Windows/win.ini"])
def test_resolve_inside_rejects_escapes(tmp_path, bad):
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(PathError):
        resolve_inside(repo, bad)


def test_resolve_inside_rejects_skipped_dirs(tmp_path):
    write(tmp_path, ".git/config")
    with pytest.raises(PathError):
        resolve_inside(tmp_path, ".git/config")


def test_check_readable_rejects_large_and_binary(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "MAX_FILE_BYTES", 10)
    write(tmp_path, "big.py", "x = 1234567890\n")
    write(tmp_path, "img.png", b"\x89PNG\0\0")
    with pytest.raises(PathError, match="over"):
        check_readable(tmp_path, "big.py")
    with pytest.raises(PathError, match="binary"):
        check_readable(tmp_path, "img.png")


def test_iter_files_skips_vendored_and_venv(tmp_path):
    write(tmp_path, "app/main.py")
    write(tmp_path, "README.md", "# Hi\n")
    write(tmp_path, "node_modules/lib/index.js")
    write(tmp_path, "app/__pycache__/main.cpython-313.pyc", b"\0\0")
    write(tmp_path, "myenv/pyvenv.cfg", "home = x\n")
    write(tmp_path, "myenv/Lib/site.py")
    write(tmp_path, "logo.png", b"\x89PNG\0")
    assert iter_files(tmp_path) == ["README.md", "app/main.py"]


def test_iter_files_rejects_large_repos(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "MAX_FILES", 3)
    for i in range(4):
        write(tmp_path, f"m{i}.py")
    with pytest.raises(RepoTooLarge):
        iter_files(tmp_path)


def test_iter_files_skips_symlink_outside_root(tmp_path):
    repo = tmp_path / "repo"
    write(repo, "main.py")
    write(tmp_path, "secret.txt", "password\n")
    try:
        os.symlink(tmp_path / "secret.txt", repo / "link.txt")
    except OSError:
        pytest.skip("creating symlinks needs extra rights on this machine")
    assert iter_files(repo) == ["main.py"]
    with pytest.raises(PathError):
        resolve_inside(repo, "link.txt")


def test_load_repo_from_local_path(tmp_path):
    write(tmp_path, "pkg/mod.py")
    repo = load_repo(str(tmp_path), tmp_path / "workspace")
    assert repo.root == tmp_path.resolve()
    assert repo.files == ["pkg/mod.py"]


@pytest.mark.parametrize("bad", ["file:///etc", "ftp://x/y", "--upload-pack=evil", "not a url"])
def test_clone_rejects_unsupported_urls(tmp_path, bad):
    with pytest.raises(LoadError):
        clone(bad, tmp_path)
