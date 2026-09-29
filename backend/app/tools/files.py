"""read_file and list_files."""

from app.ingest.paths import PathError, resolve_inside
from app.tools.repo import LoadedRepo, ToolError, normalise_path

MAX_LINES = 200
MAX_ENTRIES = 200
MAX_DEPTH = 5


def read_file(repo: LoadedRepo, path: str, start: int = 1, end: int | None = None) -> dict:
    """Numbered source lines start..end (inclusive), at most MAX_LINES."""
    path = normalise_path(path)
    lines = repo.text(path).splitlines()
    total = len(lines)
    if start < 1:
        start = 1
    if start > max(total, 1):
        raise ToolError(f"{path} has {total} lines; start {start} is past the end")
    end = total if end is None else end
    if end < start:
        raise ToolError(f"end ({end}) is before start ({start})")
    end = min(end, total, start + MAX_LINES - 1)
    content = "\n".join(f"{n:>4}| {lines[n - 1]}" for n in range(start, end + 1))
    result = {"path": path, "start": start, "end": end, "total_lines": total, "content": content}
    if end < total:
        result["note"] = f"showing lines {start}-{end} of {total}"
    return result


def list_files(repo: LoadedRepo, path: str = ".", depth: int = 2) -> dict:
    """Folder tree under path; folders deeper than `depth` are shown with file counts."""
    path = normalise_path(path)
    depth = max(1, min(depth, MAX_DEPTH))
    if path != ".":
        try:
            target = resolve_inside(repo.root, path)
        except PathError as err:
            raise ToolError(str(err)) from err
        if not target.is_dir():
            raise ToolError(f"not a directory: {path}")
    prefix = "" if path == "." else path + "/"

    dirs: dict[str, int] = {}
    files: list[str] = []
    for f in repo.files:
        if not f.startswith(prefix):
            continue
        parts = f[len(prefix):].split("/")
        for i in range(1, min(len(parts), depth + 1)):
            key = prefix + "/".join(parts[:i])
            dirs[key] = dirs.get(key, 0) + 1
        if len(parts) <= depth:
            files.append(f)

    entries = [{"path": d + "/", "type": "dir", "files": n} for d, n in dirs.items()]
    entries += [{"path": f, "type": "file"} for f in files]
    entries.sort(key=lambda e: e["path"])
    result = {"path": path, "depth": depth, "entries": entries[:MAX_ENTRIES]}
    if len(entries) > MAX_ENTRIES:
        result["note"] = f"showing {MAX_ENTRIES} of {len(entries)} entries; list a subfolder or lower depth"
    return result
