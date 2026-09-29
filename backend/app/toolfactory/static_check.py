"""Static safety check for generated tool code, before it is ever run.

This is the first layer; the container (no network, read-only, limits) is the real boundary.
"""

import ast

ALLOWED_IMPORTS = {"re", "json", "collections", "itertools", "math"}
BANNED_NAMES = {
    "eval", "exec", "compile", "open", "__import__", "input", "breakpoint", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "memoryview", "help", "exit", "quit",
    # modules that must never be reachable, even if smuggled in by name
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "importlib", "builtins", "ctypes",
    "urllib", "http", "requests", "pickle", "marshal",
}


def static_check(source: str) -> list[str]:
    """Return a list of problems; empty means the code passed."""
    try:
        tree = ast.parse(source)
    except SyntaxError as err:
        return [f"syntax error at line {err.lineno}: {err.msg}"]

    problems: list[str] = []

    def flag(node: ast.AST, message: str) -> None:
        problems.append(f"line {getattr(node, 'lineno', '?')}: {message}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    flag(node, f"import of {alias.name!r} is not allowed (allowed: {sorted(ALLOWED_IMPORTS)})")
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                flag(node, f"import from {node.module!r} is not allowed (allowed: {sorted(ALLOWED_IMPORTS)})")
        elif isinstance(node, ast.Name):
            if node.id in BANNED_NAMES:
                flag(node, f"use of {node.id!r} is not allowed")
            elif "__" in node.id:
                flag(node, f"double-underscore name {node.id!r} is not allowed")
        elif isinstance(node, ast.Attribute) and "__" in node.attr:
            flag(node, f"double-underscore attribute {node.attr!r} is not allowed")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and "__" in node.name:
            flag(node, f"double-underscore definition {node.name!r} is not allowed")
        elif isinstance(node, ast.arg) and "__" in node.arg:
            flag(node, f"double-underscore argument {node.arg!r} is not allowed")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            flag(node, "global/nonlocal is not allowed")
        elif isinstance(node, (ast.AsyncFunctionDef, ast.Await)):
            flag(node, "async code is not allowed")

    runs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run"]
    if len(runs) != 1 or [a.arg for a in runs[0].args.args] != ["args", "ctx"]:
        problems.append("code must define exactly one top-level `def run(args, ctx)`")
    return problems
