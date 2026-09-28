"""Split Markdown and reStructuredText into heading sections and find the code symbols they mention."""

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
DOTTED_RE = re.compile(r"\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+\b")
RST_UNDERLINE_RE = re.compile(r"^([=\-~^\"'`#*+:._])\1{2,}$")
IDENT_RE =re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")


@dataclass
class Section:
    id: str
    title: str
    path: str
    start: int
    end: int
    text: str


def _markdown_heads(lines: list[str]) -> list[tuple[int, str]]:
    heads = []
    in_fence = False
    for i, line in enumerate(lines, start=1):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        match = None if in_fence else HEADING_RE.match(line)
        if match:
            heads.append((i, match.group(2)))
    return heads


def _rst_heads(lines: list[str]) -> list[tuple[int, str]]:
    """reStructuredText: a title line followed by an underline at least as long."""
    heads = []
    for i in range(len(lines) - 1):
        title, under = lines[i].strip(), lines[i + 1].rstrip()
        if (title and not RST_UNDERLINE_RE.match(title) and RST_UNDERLINE_RE.match(under)
                and len(under) >= len(title) and not lines[i].startswith((" ", ".."))):
            heads.append((i + 1, title))
    return heads


def split_sections(path: str, text: str) -> list[Section]:
    """One section per heading; text before the first heading uses the file name."""
    lines = text.splitlines()
    heads = _rst_heads(lines) if path.lower().endswith(".rst") else _markdown_heads(lines)
    if not heads or heads[0][0] > 1:
        heads.insert(0, (1, path.rsplit("/", 1)[-1]))
    sections = []
    for n, (start, title) in enumerate(heads):
        end = heads[n + 1][0] - 1 if n + 1 < len(heads) else max(len(lines), start)
        body = "\n".join(lines[start - 1:end])
        if body.strip():
            sections.append(Section(f"doc:{path}#L{start}", title, path, start, end, body))
    return sections


def mentioned_names(text: str) -> set[str]:
    """Code-formatted names (`create_order`, `app.db.Base`) and dotted names."""
    names = set()
    for span in CODE_SPAN_RE.findall(text):
        name = span.strip().removesuffix("()")
        if IDENT_RE.match(name):
            names.add(name)
    names.update(DOTTED_RE.findall(CODE_SPAN_RE.sub(" ", text)))
    return names


class SymbolMatcher:
    """Match a mentioned name to exactly one code symbol, or to none."""

    def __init__(self, symbol_ids: list[str]):
        self.ids = set(symbol_ids)
        self.by_suffix: dict[str, set[str]] = {}
        for sid in symbol_ids:
            parts = sid.split(".")
            for i in range(1, len(parts)):
                self.by_suffix.setdefault(".".join(parts[i:]), set()).add(sid)

    def match(self, name: str) -> str | None:
        if name in self.ids:
            return name
        candidates = self.by_suffix.get(name, set())
        return next(iter(candidates)) if len(candidates) == 1 else None
