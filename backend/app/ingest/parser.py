"""Parse Python files with `ast` into symbols, imports and routes.

Nothing from the analysed repository is imported or executed.
"""

import ast
from dataclasses import dataclass, field

ROUTE_METHODS = {"get", "post", "put", "delete", "patch", "head", "options", "websocket"}
ROUTE_GENERIC = {"route", "api_route"}  # Flask / FastAPI: methods given as a keyword


@dataclass
class Symbol:
    id: str
    kind: str  # module | class | function
    name: str
    path: str
    start: int
    end: int
    docstring: str
    parent: str | None
    node: ast.AST | None = field(default=None, repr=False, compare=False)


@dataclass
class Route:
    method: str
    path: str
    handler: str
    file: str
    line: int
    router: str | None = None  # decorator receiver, e.g. "router" in @router.get(...)


@dataclass
class Include:
    """`parent.include_router(child, prefix="/x")` in a module."""
    parent: str
    child: str
    prefix: str


@dataclass
class Module:
    name: str
    path: str
    tree: ast.Module | None
    imports: dict[str, str] = field(default_factory=dict)  # local name -> dotted target
    imported: list[tuple[str, int]] = field(default_factory=list)  # (module, line)
    top_level: dict[str, str] = field(default_factory=dict)  # name -> symbol id
    routers: dict[str, str] = field(default_factory=dict)  # module-level APIRouter name -> own prefix
    includes: list[Include] = field(default_factory=list)
    error: str | None = None


def module_name(path: str) -> str:
    parts = path[: -len(".py")].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if len(parts) > 1 and parts[0] == "src":
        parts = parts[1:]
    return ".".join(parts) or "__init__"


def _package(mod: str, path: str) -> list[str]:
    parts = mod.split(".")
    return parts if path.endswith("__init__.py") else parts[:-1]


def _collect_imports(module: Module) -> None:
    package = _package(module.name, module.path)
    for node in ast.walk(module.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module.imported.append((alias.name, node.lineno))
                if alias.asname:
                    module.imports[alias.asname] = alias.name
                else:
                    head = alias.name.split(".")[0]
                    module.imports.setdefault(head, head)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - (node.level - 1)] if node.level > 1 else package
                source = ".".join([*base, node.module] if node.module else base)
            else:
                source = node.module or ""
            if not source:
                continue
            module.imported.append((source, node.lineno))
            for alias in node.names:
                if alias.name != "*":
                    module.imports[alias.asname or alias.name] = f"{source}.{alias.name}"


def _dotted(expr: ast.expr) -> str | None:
    parts = []
    while isinstance(expr, ast.Attribute):
        parts.append(expr.attr)
        expr = expr.value
    if not isinstance(expr, ast.Name):
        return None
    return ".".join([expr.id, *reversed(parts)])


def _str_kwarg(call: ast.Call, name: str) -> str:
    """A constant string keyword argument; other values are unknown statically."""
    for kw in call.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return ""


def _collect_routers(module: Module) -> None:
    """FastAPI routers and include_router() calls, used to build full route paths."""
    for node in module.tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call) and (_dotted(node.value.func) or "").endswith("APIRouter")):
            module.routers[node.targets[0].id] = _str_kwarg(node.value, "prefix")
    for node in ast.walk(module.tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "include_router" and node.args):
            parent, child = _dotted(node.func.value), _dotted(node.args[0])
            if parent and child:
                module.includes.append(Include(parent, child, _str_kwarg(node, "prefix")))


def _route_of(decorator: ast.expr) -> tuple[str, str] | None:
    if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)):
        return None
    attr = decorator.func.attr
    if attr not in ROUTE_METHODS and attr not in ROUTE_GENERIC:
        return None
    if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
        return None
    path = decorator.args[0].value
    if not isinstance(path, str):
        return None
    if attr in ROUTE_METHODS:
        return attr.upper(), path
    for kw in decorator.keywords:
        if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
            methods = [e.value.upper() for e in kw.value.elts if isinstance(e, ast.Constant)]
            return "|".join(methods) or "GET", path
    return "GET", path


def parse_module(path: str, source: str) -> tuple[Module, list[Symbol], list[Route]]:
    """Parse one Python file. Syntax errors give a module with `error` set."""
    name = module_name(path)
    lines = source.count("\n") + 1
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError) as err:
        module = Module(name=name, path=path, tree=None, error=str(err))
        return module, [Symbol(name, "module", name, path, 1, lines, "", None)], []

    module = Module(name=name, path=path, tree=tree)
    _collect_imports(module)
    _collect_routers(module)
    symbols = [Symbol(name, "module", name, path, 1, lines, ast.get_docstring(tree) or "", None, tree)]
    routes: list[Route] = []

    def visit(body: list[ast.stmt], parent: str, top: bool) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                sid = f"{parent}.{node.name}"
                symbols.append(Symbol(
                    sid, kind, node.name, path, node.lineno, node.end_lineno or node.lineno,
                    ast.get_docstring(node) or "", parent, node,
                ))
                if top:
                    module.top_level[node.name] = sid
                if kind == "function":
                    for dec in node.decorator_list:
                        route = _route_of(dec)
                        if route:
                            router = _dotted(dec.func.value)
                            routes.append(Route(route[0], route[1], sid, path, dec.lineno, router))
                visit(node.body, sid, False)
            elif isinstance(node, (ast.If, ast.Try, ast.With, ast.AsyncWith)):
                # Definitions guarded by `if TYPE_CHECKING:` / `try:` still count.
                for block in ("body", "orelse", "finalbody"):
                    visit(getattr(node, block, []), parent, top)
                for handler in getattr(node, "handlers", []):
                    visit(handler.body, parent, top)

    visit(tree.body, name, True)
    return module, symbols, routes
