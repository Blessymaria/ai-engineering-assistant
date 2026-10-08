"""Checks that a generated tool answers the right question, beyond "it ran and read data through ctx".

A general check of what an arbitrary tool computes is not possible, so these cover the two mistakes the
evaluation found, in a form that does not depend on any particular question:

- history_errors: a tool reports commits for a function, but the commits did not change that function's
  lines (the evaluation's tools reported the file's newest commit). Checked against `git log -L` on the
  function's own lines, for any function named in the test input.
- path_input_errors: the gap names a function, but the tool requires a file path, which the agent then
  guesses from the question's wording (the evaluation's agent passed "articles").
"""

import json
import re

from app.agent.actions import CapabilityGap
from app.runner.context import ToolContext
from app.tools.repo import ToolError

HEX_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
PATH_PARAM_RE = re.compile(r"path|file", re.I)


def _named_functions(ctx: ToolContext, values: list[str]) -> list[dict]:
    names = {v for v in values if isinstance(v, str)}
    return [n for n in ctx.list_nodes("function") if n.get("name") in names and n.get("path") and n.get("end")]


def history_errors(ctx: ToolContext, example: dict, result: object, ctx_calls: list[dict]) -> list[str]:
    """Commits in the output must have changed the lines of the function named in the input."""
    if not any(str(c.get("method", "")).startswith("git_") for c in ctx_calls):
        return []
    functions = _named_functions(ctx, list(example.values()))
    if not functions:
        return []  # not about one function (e.g. a whole-file history): nothing to compare with
    try:
        known = ctx.known_commits()
    except ToolError:
        return []  # not a git repository
    reported = {h for h in HEX_RE.findall(json.dumps(result)) if any(full.startswith(h) for full in known)}
    if not reported:
        return []
    touched: set[str] = set()
    for fn in functions:
        try:
            history = ctx.git_log_lines(fn["path"], fn["line"], fn["end"], limit=50)
        except ToolError:
            continue
        touched |= {c["commit"] for c in history}
    wrong = sorted(h for h in reported if not any(t.startswith(h) or h.startswith(t) for t in touched))
    if not wrong:
        return []
    fn = functions[0]
    return [f"the output reports commit(s) {', '.join(wrong)}, which did not change the lines of "
            f"{fn['name']} ({fn['path']}:{fn['line']}-{fn['end']}); they changed other code in the file. "
            f"Use ctx.git_log_lines(path, line, end) on the function's own lines instead of ctx.git_log(path)."]


def path_input_errors(ctx: ToolContext, gap: CapabilityGap | None, parameters: dict) -> list[str]:
    """A gap about a named function must not get a tool that needs the caller to know the file path."""
    if gap is None:
        return []
    hint = f"{gap.example_input} {gap.missing_capability}"
    if "/" in hint or ".py" in hint:
        return []  # the agent already has a path
    words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", hint))
    if not _named_functions(ctx, list(words)):
        return []
    path_params = [p for p in parameters.get("required", []) if PATH_PARAM_RE.search(p)]
    if not path_params:
        return []
    return [f"the agent knows the function's name but not its file, so the tool must not require "
            f"{', '.join(path_params)}: take the function name and find its path and lines with ctx.list_nodes."]
