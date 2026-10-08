"""Backend side of the ToolContext: the only route from a generated tool to repository data.

Only allowlisted methods run; each validates its arguments like the core tools do.
Git access is read-only (log, line-range log and blame) and confined to the repository root.
"""

import re
import subprocess
from datetime import datetime, timezone
from typing import Any

from app.ingest.paths import PathError, check_readable, resolve_inside
from app.tools.registry import CORE_TOOLS, run_tool, validate_args
from app.tools.repo import LoadedRepo, ToolError, normalise_path

NODE_KINDS = ("module", "class", "function", "route")
MAX_GIT_LOG = 50
MAX_BLAME_LINES = 300
SHA_LINE_RE = re.compile(r"^([0-9a-f]{40}) (\d+) (\d+)")
LOG_FORMAT = "%H%x1f%an%x1f%ae%x1f%aI%x1f%s"

EXTRA_SCHEMAS = {
    "list_nodes": {"type": "object", "properties": {"kind": {"type": "string", "enum": list(NODE_KINDS)}},
                   "required": ["kind"]},
    "git_log": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["path"]},
    "git_log_lines": {"type": "object", "properties": {"path": {"type": "string"}, "start": {"type": "integer"},
                                                       "end": {"type": "integer"}, "limit": {"type": "integer"}},
                      "required": ["path", "start", "end"]},
    "git_blame": {"type": "object", "properties": {"path": {"type": "string"}, "start": {"type": "integer"},
                                                   "end": {"type": "integer"}},
                  "required": ["path", "start", "end"]},
}
METHODS = sorted(CORE_TOOLS) + sorted(EXTRA_SCHEMAS)


class ToolContext:
    def __init__(self, repo: LoadedRepo):
        self.repo = repo

    def handle(self, method: str, args: dict) -> Any:
        if method in CORE_TOOLS:
            return run_tool(self.repo, method, args)
        if method not in EXTRA_SCHEMAS:
            raise ToolError(f"ctx has no method {method!r}; available: {METHODS}")
        args = validate_args(EXTRA_SCHEMAS[method], dict(args))
        return getattr(self, method)(**args)

    def list_nodes(self, kind: str) -> list[dict]:
        return [
            {"id": n, "name": d.get("name"), "path": d.get("path"), "line": d.get("start"), "end": d.get("end")}
            for n, d in self.repo.graph.nodes(data=True) if d["kind"] == kind
        ]

    def _git(self, args: list[str]) -> str:
        result = subprocess.run(["git", "-C", str(self.repo.root), *args], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=30)
        if result.returncode != 0:
            raise ToolError(f"git failed: {result.stderr.strip()[:300]}")
        return result.stdout

    def _repo_path(self, path: str) -> str:
        path = normalise_path(path)
        try:
            target = resolve_inside(self.repo.root, path)
        except PathError as err:
            raise ToolError(str(err)) from err
        if not target.exists():
            # git log on a missing path silently returns nothing; make it an error instead
            raise ToolError(f"no such file or folder in the repository: {path}")
        return path

    def git_log(self, path: str, limit: int = 10) -> list[dict]:
        path = self._repo_path(path)
        limit = max(1, min(limit, MAX_GIT_LOG))
        out = self._git(["log", f"-n{limit}", f"--format={LOG_FORMAT}", "--", path])
        return self._commits(out)

    @staticmethod
    def _commits(out: str) -> list[dict]:
        commits = []
        for line in out.splitlines():
            if line.count("\x1f") != 4:
                continue  # blank separator lines
            sha, author, email, date, subject = line.split("\x1f", 4)
            commits.append({"commit": sha[:12], "author": author, "email": email, "date": date, "subject": subject})
        return commits

    def git_log_lines(self, path: str, start: int, end: int, limit: int = 10) -> list[dict]:
        """Commits that changed lines start..end of path, newest first, following those lines as they move
        within the file (`git log -L`): the history of one function, not of the whole file."""
        path = normalise_path(path)
        try:
            target = check_readable(self.repo.root, path)
        except PathError as err:
            raise ToolError(str(err)) from err
        if start < 1 or end < start:
            raise ToolError("need 1 <= start <= end")
        total = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
        if start > total:
            raise ToolError(f"{path} has only {total} lines")
        limit = max(1, min(limit, MAX_GIT_LOG))
        out = self._git(["log", f"-n{limit}", "-s", f"--format={LOG_FORMAT}", "-L", f"{start},{min(end, total)}:{path}"])
        return self._commits(out)

    def git_blame(self, path: str, start: int, end: int) -> list[dict]:
        path = normalise_path(path)
        try:
            check_readable(self.repo.root, path)
        except PathError as err:
            raise ToolError(str(err)) from err
        if start < 1 or end < start:
            raise ToolError("need 1 <= start <= end")
        end = min(end, start + MAX_BLAME_LINES - 1)
        out = self._git(["blame", "--porcelain", "-L", f"{start},{end}", "--", path])
        info: dict[str, dict] = {}
        lines, current = [], None
        for raw in out.splitlines():
            match = SHA_LINE_RE.match(raw)
            if match:
                current = {"commit": match.group(1), "line": int(match.group(3))}
                info.setdefault(current["commit"], {})
            elif raw.startswith("\t") and current:
                meta = info[current["commit"]]
                ts = meta.get("author-time")
                date = datetime.fromtimestamp(int(ts), timezone.utc).isoformat() if ts else None
                lines.append({"line": current["line"], "commit": current["commit"][:12],
                              "author": meta.get("author"), "date": date, "summary": meta.get("summary"),
                              "text": raw[1:][:200]})
                current = None
            elif current and " " in raw:
                key, value = raw.split(" ", 1)
                if key in ("author", "author-mail", "author-time", "summary"):
                    info[current["commit"]][key] = value
        return lines
