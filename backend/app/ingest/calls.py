"""Resolve call sites to graph symbols without type inference.

Each call gets one of:
- resolved:   one target found via imports or same-module definitions
- ambiguous:  several (or only name-matched) candidates, e.g. `self.repo.save()`
A call on a parameter annotated with a repository class (`repo: ArticlesRepository`) resolves to that class's
method when the class has it: the annotation states the type, so this needs no inference. The same holds for
`self.repo.method()` when `__init__` sets `self.repo = Repo(...)` or `self.repo: Repo`.
- unresolved: no target found (injected objects, dynamic dispatch, ...)
Calls into libraries outside the repository resolve to `external` nodes.
"""

import ast
import builtins
from collections import defaultdict
from dataclasses import dataclass

from app.ingest.parser import Module, Symbol

BUILTINS = set(dir(builtins))
MAX_CANDIDATES = 8  # more name matches than this is too generic to be useful


@dataclass
class Call:
    caller: str
    status: str  # resolved | ambiguous | unresolved
    targets: list[str]  # symbol ids, or "ext:<name>" / "unresolved:<text>"
    line: int


def dotted_name(expr: ast.expr) -> str | None:
    parts = []
    while isinstance(expr, ast.Attribute):
        parts.append(expr.attr)
        expr = expr.value
    if not isinstance(expr, ast.Name):
        return None
    parts.append(expr.id)
    return ".".join(reversed(parts))


def iter_calls(body: list[ast.stmt]):
    """Yield calls in body, not descending into nested functions or classes."""
    stack: list[ast.AST] = list(reversed(body))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.Call):
            yield node
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


class Resolver:
    def __init__(self, modules: dict[str, Module], symbols: dict[str, Symbol]):
        self.modules = modules
        self.symbols = symbols
        self.top_packages = {name.split(".")[0] for name in modules}
        self.methods_by_name: dict[str, list[str]] = defaultdict(list)
        for s in symbols.values():
            if s.kind == "function" and s.parent and symbols[s.parent].kind == "class":
                self.methods_by_name[s.name].append(s.id)
        self.bases: dict[str, list[str]] = {}

    def resolve_dotted(self, full: str, depth: int = 0) -> tuple[str, str | None]:
        """Resolve a fully qualified name, following re-exports in repo modules.

        Returns ("resolved", id), ("external", "ext:<name>") or ("unresolved", None).
        """
        if full in self.symbols:
            return "resolved", full
        parts = full.split(".")
        if parts[0] not in self.top_packages:
            return "external", f"ext:{full}"
        if depth < 5:
            for i in range(len(parts) - 1, 0, -1):
                mod = self.modules.get(".".join(parts[:i]))
                if mod is None:
                    continue
                target = mod.imports.get(parts[i])
                if target and target != full:
                    return self.resolve_dotted(".".join([target, *parts[i + 1:]]), depth + 1)
                break
        return "unresolved", None

    def resolve_bases(self, cls: Symbol, module: Module) -> None:
        ids = []
        for base in cls.node.bases:
            name = dotted_name(base)
            if not name:
                continue
            status, target = self._resolve_name(name, module)
            if target and status in ("resolved", "external"):
                ids.append(target)
        self.bases[cls.id] = ids

    def find_method(self, class_id: str, name: str, depth: int = 0) -> str | None:
        method = f"{class_id}.{name}"
        if method in self.symbols:
            return method
        if depth < 5:
            for base in self.bases.get(class_id, []):
                found = self.find_method(base, name, depth + 1)
                if found:
                    return found
        return None

    def overrides(self, class_id: str, name: str) -> list[str]:
        """The method as redefined by subclasses of class_id in the repository (any of them may run instead)."""
        found = []
        for sub, bases in self.bases.items():
            if sub != class_id and self._inherits(sub, class_id) and f"{sub}.{name}" in self.symbols:
                found.append(f"{sub}.{name}")
        return found

    def _inherits(self, class_id: str, ancestor: str, depth: int = 0) -> bool:
        bases = self.bases.get(class_id, [])
        return ancestor in bases or (depth < 5 and any(self._inherits(b, ancestor, depth + 1) for b in bases))

    def _resolve_name(self, dotted: str, module: Module) -> tuple[str, str | None]:
        head, _, rest = dotted.partition(".")
        if head in module.top_level:
            base = module.top_level[head]
        elif head in module.imports:
            base = module.imports[head]
        else:
            return "unresolved", None
        return self.resolve_dotted(f"{base}.{rest}" if rest else base)

    def annotated_params(self, func: ast.AST, module: Module) -> dict[str, str]:
        """Parameter name -> repository class id, for parameters annotated with a class (`x: Foo`, `x: "Foo"`)."""
        params: dict[str, str] = {}
        args = getattr(func, "args", None)
        if args is None:
            return params
        for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
            ann = arg.annotation
            name = ann.value if isinstance(ann, ast.Constant) and isinstance(ann.value, str) else (
                dotted_name(ann) if ann is not None else None)
            if not name:
                continue
            status, target = self._resolve_name(name, module)
            if status == "resolved" and target in self.symbols and self.symbols[target].kind == "class":
                params[arg.arg] = target
        return params

    def instance_attrs(self, cls: Symbol, module: Module) -> dict[str, str]:
        """Attribute -> repository class id, from `self.x = Foo(...)` or `self.x: Foo` in the class's __init__."""
        init = self.symbols.get(f"{cls.id}.__init__")
        attrs: dict[str, str] = {}
        if init is None or init.node is None:
            return attrs
        for stmt in ast.walk(init.node):
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                target, value = stmt.targets[0], stmt.value
                name = dotted_name(value.func) if isinstance(value, ast.Call) else None
            elif isinstance(stmt, ast.AnnAssign):
                target, name = stmt.target, dotted_name(stmt.annotation)
            else:
                continue
            if not (name and isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                    and target.value.id == "self"):
                continue
            status, class_id = self._resolve_name(name, module)
            if status == "resolved" and class_id in self.symbols and self.symbols[class_id].kind == "class":
                attrs[f"self.{target.attr}"] = class_id
        return attrs

    def resolve(self, call: ast.Call, module: Module, cls: Symbol | None,
                params: dict[str, str] | None = None) -> tuple[str, list[str]] | None:
        """Return (status, targets) for a call, or None if not worth recording."""
        dotted = dotted_name(call.func)
        if dotted is None:
            return None  # e.g. f()() or handlers[0]()
        head, _, rest = dotted.partition(".")

        receiver, _, last = dotted.rpartition(".")
        if params and receiver in params and (receiver == head or receiver.startswith("self.")):
            method = self.find_method(params[receiver], last)
            if method:
                overrides = self.overrides(params[receiver], last)
                return ("ambiguous", sorted({method, *overrides})) if overrides else ("resolved", [method])

        if not rest:
            if head in module.top_level or head in module.imports:
                status, target = self._resolve_name(dotted, module)
                return status_targets(status, target, dotted)
            if head in BUILTINS:
                return None
            return "unresolved", [f"unresolved:{dotted}"]

        if head in ("self", "cls") and cls is not None and "." not in rest:
            method = self.find_method(cls.id, rest)
            if method:
                return "resolved", [method]
        elif head in module.top_level or head in module.imports:
            status, target = self._resolve_name(dotted, module)
            if status != "unresolved":
                return status_targets(status, target, dotted)

        candidates = self.methods_by_name.get(dotted.rsplit(".", 1)[-1], [])
        if 0 < len(candidates) <= MAX_CANDIDATES:
            return "ambiguous", sorted(candidates)
        if head in ("self", "cls") or head in module.imports:
            return "unresolved", [f"unresolved:{dotted}"]
        return None  # method on a local value, e.g. items.append(); not a code-graph call


def status_targets(status: str, target: str | None, dotted: str) -> tuple[str, list[str]]:
    if status in ("resolved", "external"):
        return "resolved", [target]
    return "unresolved", [f"unresolved:{dotted}"]


def resolve_calls(resolver: Resolver, symbols: list[Symbol], module: Module) -> list[Call]:
    """Resolve every call made by the module's functions and top-level code."""
    calls: list[Call] = []
    if module.tree is None:
        return calls

    def record(caller: str, body: list[ast.stmt], cls: Symbol | None, params: dict[str, str] | None = None) -> None:
        seen = set()
        for node in iter_calls(body):
            result = resolver.resolve(node, module, cls, params)
            if result is None:
                continue
            key = (result[0], tuple(result[1]))
            if key in seen:
                continue
            seen.add(key)
            calls.append(Call(caller, result[0], result[1], node.lineno))

    record(module.name, module.tree.body, None)
    for s in symbols:
        if s.kind == "function":
            parent = resolver.symbols.get(s.parent)
            cls = parent if parent is not None and parent.kind == "class" else None
            known = resolver.annotated_params(s.node, module)
            if cls is not None:
                known = {**resolver.instance_attrs(cls, module), **known}
            record(s.id, s.node.body, cls, known)
    return calls
