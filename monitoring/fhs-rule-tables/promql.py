"""A parser for the subset of PromQL the rule files use.

Nothing here knows about the FHS rules; it turns an expression string into a
small AST (:func:`parse_promql`), lets callers walk it (:func:`walk`,
:func:`unwrap`) and turn a node back into text (:func:`unparse`). Every other
module in this folder works on those nodes rather than on raw strings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


AGG_FUNCS = {"sum", "min", "max", "avg", "count", "group", "stddev", "stdvar"}

# Binary operators, loosest binding first.
PRECEDENCE = [
    ("or",),
    ("and", "unless"),
    ("==", "!=", "<", "<=", ">", ">="),
    ("+", "-"),
    ("*", "/", "%"),
    ("^",),
]
COMPARISON_OPS = {"==", "!=", "<", "<=", ">", ">="}

_TOKEN_RE = re.compile(
    r"""
      (?P<ws>\s+)
    | (?P<comment>\#[^\n]*)
    | (?P<number>\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)
    | (?P<ident>[a-zA-Z_:][a-zA-Z0-9_:]*)
    | (?P<string>"[^"]*"|'[^']*')
    | (?P<range>\[[^\]]*\])
    | (?P<op><=|>=|==|!=|=~|!~|<|>|=|\+|-|\*|/|%|\^)
    | (?P<lbrace>\{)
    | (?P<rbrace>\})
    | (?P<lparen>\()
    | (?P<rparen>\))
    | (?P<comma>,)
    """,
    re.VERBOSE,
)

_MATCHER_RE = re.compile(r"""(\w+)\s*(=~|!~|!=|=)\s*('[^']*'|"[^"]*")""")


class ParseError(Exception):
    pass


@dataclass(frozen=True)
class Matcher:
    label: str
    op: str
    value: str


@dataclass
class Num:
    text: str


@dataclass
class Selector:
    """An instant vector selector, e.g. ``foo{bar='baz'}`` or ``{bar='baz'}``."""

    name: str | None
    matchers: tuple[Matcher, ...] = ()


@dataclass
class RangeSelector:
    inner: Selector
    window: str


@dataclass
class Call:
    func: str
    args: list


@dataclass
class Agg:
    func: str
    grouping: str | None  # "by" / "without" / None
    labels: tuple[str, ...]
    args: list


@dataclass
class Paren:
    inner: object


@dataclass
class Bin:
    op: str
    lhs: object
    rhs: object
    is_bool: bool = False
    matching: str | None = None  # raw text of on(...)/ignoring(...)
    group: str | None = None  # raw text of group_left(...)/group_right(...)


@dataclass
class Unary:
    op: str
    operand: object


@dataclass
class _Token:
    kind: str
    text: str


def _tokenize(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    pos = 0
    while pos < len(text):
        match = _TOKEN_RE.match(text, pos)
        if match is None:
            raise ParseError(f"unexpected character {text[pos]!r} at offset {pos}")
        pos = match.end()
        kind = match.lastgroup
        if kind in ("ws", "comment"):
            continue
        tokens.append(_Token(kind, match.group()))
    return tokens


class _Parser:
    def __init__(self, tokens: list[_Token]):
        self.tokens = tokens
        self.pos = 0

    # -- token helpers -------------------------------------------------
    def peek(self, offset: int = 0) -> _Token | None:
        index = self.pos + offset
        return self.tokens[index] if index < len(self.tokens) else None

    def next(self) -> _Token:
        token = self.peek()
        if token is None:
            raise ParseError("unexpected end of expression")
        self.pos += 1
        return token

    def accept(self, kind: str, text: str | None = None) -> _Token | None:
        token = self.peek()
        if token and token.kind == kind and (text is None or token.text == text):
            self.pos += 1
            return token
        return None

    def expect(self, kind: str, text: str | None = None) -> _Token:
        token = self.accept(kind, text)
        if token is None:
            found = self.peek()
            raise ParseError(f"expected {text or kind}, found {found.text if found else 'EOF'}")
        return token

    # -- grammar -------------------------------------------------------
    def parse(self):
        node = self.parse_binary(0)
        if self.peek() is not None:
            raise ParseError(f"trailing input at {self.peek().text!r}")
        return node

    def parse_binary(self, level: int):
        if level >= len(PRECEDENCE):
            return self.parse_unary()
        node = self.parse_binary(level + 1)
        while True:
            token = self.peek()
            if token is None:
                break
            if token.kind == "op" and token.text in PRECEDENCE[level]:
                op = self.next().text
            elif token.kind == "ident" and token.text in PRECEDENCE[level]:
                op = self.next().text
            else:
                break
            is_bool = self.accept("ident", "bool") is not None
            matching = self._parse_modifier(("on", "ignoring"))
            group = self._parse_modifier(("group_left", "group_right"))
            rhs = self.parse_binary(level + 1)
            node = Bin(op, node, rhs, is_bool=is_bool, matching=matching, group=group)
        return node

    def _parse_modifier(self, keywords: tuple[str, ...]) -> str | None:
        token = self.peek()
        if token is None or token.kind != "ident" or token.text not in keywords:
            return None
        name = self.next().text
        labels = self._parse_label_list() if self.peek() and self.peek().kind == "lparen" else ()
        return f"{name}({', '.join(labels)})"

    def _parse_label_list(self) -> tuple[str, ...]:
        self.expect("lparen")
        labels: list[str] = []
        while not self.accept("rparen"):
            token = self.next()
            if token.kind == "ident":
                labels.append(token.text)
            elif token.kind != "comma":
                raise ParseError(f"unexpected {token.text!r} in label list")
        return tuple(labels)

    def parse_unary(self):
        token = self.peek()
        if token is None:
            raise ParseError("unexpected end of expression")
        if token.kind == "op" and token.text in ("-", "+"):
            self.next()
            return Unary(token.text, self.parse_unary())
        if token.kind == "number":
            self.next()
            return Num(token.text)
        if token.kind == "lparen":
            self.next()
            inner = self.parse_binary(0)
            self.expect("rparen")
            return self._maybe_range(Paren(inner))
        if token.kind == "lbrace":
            return self._maybe_range(self.parse_selector(None))
        if token.kind == "ident":
            return self.parse_ident()
        raise ParseError(f"unexpected token {token.text!r}")

    def parse_ident(self):
        name = self.next().text
        following = self.peek()
        if following and following.kind == "lparen":
            if name in AGG_FUNCS:
                return self._parse_agg(name, grouping=None, labels=())
            return self._maybe_range(Call(name, self._parse_args()))
        if following and following.kind == "ident" and following.text in ("by", "without") and name in AGG_FUNCS:
            grouping = self.next().text
            labels = self._parse_label_list()
            return self._parse_agg(name, grouping, labels)
        if following and following.kind == "lbrace":
            return self._maybe_range(self.parse_selector(name))
        return self._maybe_range(Selector(name))

    def _parse_agg(self, func: str, grouping: str | None, labels: tuple[str, ...]):
        args = self._parse_args()
        token = self.peek()
        if grouping is None and token and token.kind == "ident" and token.text in ("by", "without"):
            grouping = self.next().text
            labels = self._parse_label_list()
        return Agg(func, grouping, labels, args)

    def _parse_args(self) -> list:
        self.expect("lparen")
        args: list = []
        if self.accept("rparen"):
            return args
        while True:
            args.append(self.parse_binary(0))
            if self.accept("comma"):
                continue
            self.expect("rparen")
            return args

    def parse_selector(self, name: str | None) -> Selector:
        self.expect("lbrace")
        raw = ""
        depth = 1
        while depth:
            token = self.next()
            if token.kind == "lbrace":
                depth += 1
            elif token.kind == "rbrace":
                depth -= 1
                if depth == 0:
                    break
            raw += token.text + " "
        matchers = tuple(
            Matcher(label, op, value[1:-1]) for label, op, value in _MATCHER_RE.findall(raw)
        )
        return Selector(name, matchers)

    def _maybe_range(self, node):
        token = self.peek()
        if token and token.kind == "range":
            self.next()
            return RangeSelector(node, token.text[1:-1])
        return node


def parse_promql(expr: str):
    """Parse a PromQL expression into an AST."""
    return _Parser(_tokenize(expr)).parse()


def walk(node):
    """Yield every node in the tree, parents before children."""
    yield node
    for child in _children(node):
        yield from walk(child)


def _children(node) -> list:
    if isinstance(node, (Bin,)):
        return [node.lhs, node.rhs]
    if isinstance(node, (Paren,)):
        return [node.inner]
    if isinstance(node, Unary):
        return [node.operand]
    if isinstance(node, (Call, Agg)):
        return list(node.args)
    if isinstance(node, RangeSelector):
        return [node.inner]
    return []


def unwrap(node):
    """Strip redundant parentheses."""
    while isinstance(node, Paren):
        node = node.inner
    return node


def unparse(node) -> str:
    """Render a node back to compact PromQL (used for unrecognised shapes)."""
    if isinstance(node, Num):
        return node.text
    if isinstance(node, Selector):
        matchers = ", ".join(f"{m.label}{m.op}'{m.value}'" for m in node.matchers)
        body = "{" + matchers + "}" if matchers else ""
        return f"{node.name or ''}{body}"
    if isinstance(node, RangeSelector):
        return f"{unparse(node.inner)}[{node.window}]"
    if isinstance(node, Call):
        return f"{node.func}({', '.join(unparse(a) for a in node.args)})"
    if isinstance(node, Agg):
        grouping = f" {node.grouping} ({', '.join(node.labels)})" if node.grouping else ""
        return f"{node.func}{grouping}({', '.join(unparse(a) for a in node.args)})"
    if isinstance(node, Paren):
        return f"({unparse(node.inner)})"
    if isinstance(node, Unary):
        return f"{node.op}{unparse(node.operand)}"
    if isinstance(node, Bin):
        parts = [unparse(node.lhs), node.op]
        if node.is_bool:
            parts.append("bool")
        if node.matching:
            parts.append(node.matching)
        if node.group:
            parts.append(node.group)
        parts.append(unparse(node.rhs))
        return " ".join(parts)
    raise TypeError(f"cannot unparse {node!r}")
