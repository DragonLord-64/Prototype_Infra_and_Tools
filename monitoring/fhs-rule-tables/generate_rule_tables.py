#!/usr/bin/env python3
"""Generate plain-English tables for the FHS Prometheus rules.

Reads the threshold and aggregation rule files and writes three tables:

  1. every threshold rule and the condition that sets it to 1;
  2. every aggregation rule, its child metrics, and what makes it fail;
  3. the intermediate calculations the checks compare against.

The ``source``/``data_type`` labels the aggregation rules select on are set by
the collectors, not by the rule files, so every ``*_collector.py`` module is
parsed (with ``ast``, never imported) to recover them. Nothing about the rules
or the metrics is hard-coded here.

Run it with no arguments from anywhere inside a checkout of the exporter:

    python3 tools/generate_rule_tables.py -o docs/src/rules.md

Point it at another checkout with ``--repo``. Needs Python 3.11+ and PyYAML.
"""

from __future__ import annotations

import argparse
import ast
import csv
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


##############################################################################
# A parser for the subset of PromQL the rule files use
##############################################################################

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

##############################################################################
# Recovering the source/data_type labels from the collectors
##############################################################################

COLLECTOR_GLOB = "*_collector.py"
COMMON_MODULE = "common.py"
ADD_METRIC_FUNCS = {"_add_metric_to_result", "_add_info_metric_to_result"}


@dataclass(frozen=True)
class MetricLabels:
    """Labels the exporter puts on a scraped metric."""

    source: str
    data_type: str | None = None
    source_is_prefix: bool = False  # e.g. FPGA0/FPGA1 share one collector
    documentation: str | None = None

    def source_matches(self, value: str) -> bool:
        return value.startswith(self.source) if self.source_is_prefix else value == self.source


def _string_of(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _enum_values(tree: ast.AST, class_name: str) -> dict[str, str]:
    """Return {member: value} for an Enum class, searched at any nesting level."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            values = {}
            for statement in node.body:
                if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
                    target = statement.targets[0]
                    value = _string_of(statement.value)
                    if isinstance(target, ast.Name) and value is not None:
                        values[target.id] = value
            return values
    return {}


def _resolve_enum(node, enums: dict[str, dict[str, str]]) -> str | None:
    """Resolve ``MetricUnit.TEMPERATURE.value`` style references to their string."""
    if isinstance(node, ast.Attribute) and node.attr == "value":
        inner = node.value
        if isinstance(inner, ast.Attribute) and isinstance(inner.value, ast.Name):
            return enums.get(inner.value.id, {}).get(inner.attr)
        # self.SourceName.CPU.value
        if isinstance(inner, ast.Attribute) and isinstance(inner.value, ast.Attribute):
            return enums.get(inner.value.attr, {}).get(inner.attr)
    return _string_of(node)


def _metric_names(tree: ast.AST, enums: dict[str, dict[str, str]]) -> dict[str, tuple[str, str | None]]:
    """Map local variable -> (exported series name, documentation string)."""
    names: dict[str, tuple[str, str | None]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        target = node.targets[0]
        call = node.value
        if not (isinstance(target, ast.Name) and isinstance(call, ast.Call)):
            continue
        func = call.func
        func_name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if func_name not in ("GaugeMetricFamily", "InfoMetricFamily", "CounterMetricFamily"):
            continue
        keywords = {kw.arg: kw.value for kw in call.keywords}
        base = _string_of(keywords.get("name"))
        if base is None:
            continue
        unit = _resolve_enum(keywords["unit"], enums) if "unit" in keywords else None
        if unit:
            base = f"{base}_{unit}"
        if func_name == "InfoMetricFamily":
            # prometheus_client exports info metrics with an _info suffix.
            base = f"{base}_info"
        names[target.id] = (base, _string_of(keywords.get("documentation")))
    return names


def _source_of_module(tree: ast.AST, enums: dict[str, dict[str, str]]) -> tuple[str, bool] | None:
    """Find ``self._source_name = ...``; f-strings yield a prefix (FPGA0/FPGA1)."""
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        target = node.targets[0]
        if not (isinstance(target, ast.Attribute) and target.attr == "_source_name"):
            continue
        literal = _string_of(node.value)
        if literal is not None:
            return literal, False
        if isinstance(node.value, ast.JoinedStr):
            head = node.value.values[0]
            prefix = _string_of(head)
            if prefix:
                return prefix, True
    return None


def _tuple_entries(node) -> list[tuple[ast.AST, ast.AST]]:
    """Pull (data_type, metric_var) pairs out of a list of 3-tuples."""
    entries = []
    if isinstance(node, (ast.List, ast.Tuple)):
        for element in node.elts:
            if isinstance(element, (ast.Tuple, ast.List)) and len(element.elts) == 3:
                entries.append((element.elts[1], element.elts[2]))
    return entries


def scan_collectors(source_dir: Path) -> dict[str, MetricLabels]:
    """Return {series name: MetricLabels} for every metric the exporter emits."""
    common = ast.parse((source_dir / COMMON_MODULE).read_text())
    enums = {
        name: _enum_values(common, name)
        for name in ("MetricUnit", "MetricDataType", "StatusCode")
    }

    labels: dict[str, MetricLabels] = {}
    for path in sorted(source_dir.glob(COLLECTOR_GLOB)):
        tree = ast.parse(path.read_text())
        module_enums = dict(enums)
        module_enums["SourceName"] = _enum_values(tree, "SourceName")
        metrics = _metric_names(tree, module_enums)
        module_source = _source_of_module(tree, module_enums)

        def record(data_type_node, metric_node, source: str, is_prefix: bool) -> None:
            if not isinstance(metric_node, ast.Name):
                return
            entry = metrics.get(metric_node.id)
            if entry is None:
                return
            series, documentation = entry
            data_type = _resolve_enum(data_type_node, module_enums)
            labels[series] = MetricLabels(source, data_type, is_prefix, documentation)

        for node in ast.walk(tree):
            # Form 1: metrics_to_add = {SourceName.X.value: [(field, data_type, metric)]}
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    source = _resolve_enum(key, module_enums)
                    if source is None:
                        continue
                    for data_type_node, metric_node in _tuple_entries(value):
                        record(data_type_node, metric_node, source, False)
            # Form 2: a plain list of (field, data_type, metric) for a single-source collector
            elif isinstance(node, ast.List) and module_source:
                for data_type_node, metric_node in _tuple_entries(node):
                    record(data_type_node, metric_node, *module_source)
            # Form 3: a direct _add_metric_to_result(labels=[...], metric=...) call
            elif isinstance(node, ast.Call):
                func = node.func
                if not (isinstance(func, ast.Attribute) and func.attr in ADD_METRIC_FUNCS):
                    continue
                keywords = {kw.arg: kw.value for kw in node.keywords}
                label_arg = keywords.get("labels")
                metric_node = keywords.get("metric")
                if not (isinstance(label_arg, ast.List) and len(label_arg.elts) == 2):
                    continue
                if not (isinstance(metric_node, ast.Name) and module_source):
                    continue
                record(label_arg.elts[1], metric_node, *module_source)

    return labels

##############################################################################
# The rule model: labels, references and selector matching
##############################################################################

@dataclass
class Rule:
    record: str
    group: str
    interval: str | None
    expr: str
    node: object
    labels: dict[str, str]
    kind: str  # "threshold", "derived" or "aggregation"

    refs: tuple[str, ...] = ()  # metrics/records named directly in the expression
    sources: tuple[str, ...] = ()
    data_types: tuple[str, ...] = ()
    devices: tuple[str, ...] = ()

    @property
    def record_tag(self) -> str | None:
        return self.labels.get("record_tag")


def load_rules(path: Path, kind_default: str) -> list[Rule]:
    document = yaml.safe_load(path.read_text())
    rules: list[Rule] = []
    for group in document.get("groups", []):
        for rule in group.get("rules", []):
            if "record" not in rule:
                continue
            labels = dict(rule.get("labels") or {})
            kind = kind_default
            if kind_default == "threshold" and "record_tag" not in labels:
                # Intermediate maths (utilisation, core counts) rather than a check.
                kind = "derived"
            node = parse_promql(rule["expr"])
            rules.append(
                Rule(
                    record=rule["record"],
                    group=group.get("name", ""),
                    interval=group.get("interval"),
                    expr=rule["expr"].strip(),
                    node=node,
                    labels=labels,
                    kind=kind,
                    refs=tuple(_referenced_names(node)),
                )
            )
    return rules


def _referenced_names(node) -> list[str]:
    names: list[str] = []
    for item in walk(node):
        if isinstance(item, Selector) and item.name and item.name not in names:
            names.append(item.name)
    return names


def _device_matchers(node) -> list[str]:
    devices: list[str] = []
    for item in walk(node):
        if isinstance(item, Selector):
            for matcher in item.matchers:
                if matcher.label == "device" and matcher.value not in devices:
                    devices.append(matcher.value)
    return devices


class RuleSet:
    """Every rule from both files, with the labels of its output series resolved."""

    def __init__(self, rules: list[Rule], metric_labels: dict[str, MetricLabels]):
        self.rules = rules
        self.by_record = {rule.record: rule for rule in rules}
        self.metric_labels = metric_labels
        self._known_sources = self._collect_selector_sources()
        for rule in rules:
            self._resolve_labels(rule)

    def _collect_selector_sources(self) -> set[str]:
        sources = set()
        for rule in self.rules:
            for item in walk(rule.node):
                if isinstance(item, Selector):
                    for matcher in item.matchers:
                        if matcher.label == "source" and matcher.op == "=":
                            sources.add(matcher.value)
        return sources

    def _expand_source(self, labels: MetricLabels) -> list[str]:
        """One collector serves FPGA0 and FPGA1; expand the prefix it exports."""
        if not labels.source_is_prefix:
            return [labels.source]
        matched = sorted(s for s in self._known_sources if s.startswith(labels.source))
        return matched or [f"{labels.source}*"]

    def leaf_metrics(self, rule: Rule, seen: set[str] | None = None) -> list[str]:
        """Scraped metrics a rule depends on, following references to other rules."""
        seen = seen if seen is not None else set()
        leaves: list[str] = []
        for name in rule.refs:
            if name in seen:
                continue
            seen.add(name)
            referenced = self.by_record.get(name)
            if referenced is not None:
                leaves.extend(self.leaf_metrics(referenced, seen))
            elif name not in leaves:
                leaves.append(name)
        return leaves

    def _resolve_labels(self, rule: Rule) -> None:
        sources: list[str] = []
        data_types: list[str] = []
        for metric in self.leaf_metrics(rule):
            labels = self.metric_labels.get(metric)
            if labels is None:
                continue
            for source in self._expand_source(labels):
                if source not in sources:
                    sources.append(source)
            if labels.data_type and labels.data_type not in data_types:
                data_types.append(labels.data_type)
        # A source set in the rule file wins over whatever the exporter attaches.
        if "source" in rule.labels:
            sources = [rule.labels["source"]]
        rule.sources = tuple(sources)
        rule.data_types = tuple(data_types)

        devices = list(_device_matchers(rule.node))
        for name in rule.refs:
            referenced = self.by_record.get(name)
            if referenced is not None:
                devices.extend(d for d in _device_matchers(referenced.node) if d not in devices)
        rule.devices = tuple(devices)

    def documentation(self, rule: Rule) -> str | None:
        """The documented meaning of a rule's input, when its inputs agree."""
        docs = {
            self.metric_labels[metric].documentation
            for metric in self.leaf_metrics(rule)
            if metric in self.metric_labels and self.metric_labels[metric].documentation
        }
        return docs.pop() if len(docs) == 1 else None

    def resolve_selector(self, selector: Selector) -> list[str]:
        """Records whose output series match a label-only selector."""
        return [
            rule.record
            for rule in self.rules
            if rule.kind != "derived"
            and rule.record != selector.name
            and all(self._matches(rule, matcher) for matcher in selector.matchers)
        ]

    def _matches(self, rule: Rule, matcher: Matcher) -> bool:
        if matcher.label == "device":
            return any(_patterns_overlap(matcher.value, device) for device in rule.devices)
        if matcher.label == "source":
            values = rule.sources
        elif matcher.label == "data_type":
            values = rule.data_types
        elif matcher.label in rule.labels:
            values = (rule.labels[matcher.label],)
        else:
            # Labels such as job/instance come from the target, not the rule.
            return True
        return any(_matcher_hit(matcher, value) for value in values)


def _matcher_hit(matcher: Matcher, value: str) -> bool:
    if matcher.op == "=":
        return value == matcher.value
    if matcher.op == "!=":
        return value != matcher.value
    if matcher.op == "=~":
        return re.fullmatch(matcher.value, value) is not None
    if matcher.op == "!~":
        return re.fullmatch(matcher.value, value) is None
    return False


def _patterns_overlap(left: str, right: str) -> bool:
    """Loose comparison of two device matchers, e.g. '.*enp2.*' against 'enp2s0'."""
    left_core = left.strip(".*^$")
    right_core = right.strip(".*^$")
    return left_core in right_core or right_core in left_core

##############################################################################
# Plain-English descriptions
##############################################################################

WINDOW_WORDS = {
    "max_over_time": "max",
    "min_over_time": "min",
    "avg_over_time": "avg",
    "sum_over_time": "sum",
    "changes": "changes",
    "rate": "rate",
    "increase": "increase",
}
OP_WORDS = {
    ">": "above",
    "<": "below",
    ">=": "at or above",
    "<=": "at or below",
    "==": "equal to",
    "!=": "not equal to",
}
COUNT_WORDS = {
    ">": "is more than",
    ">=": "is at least",
    "==": "is exactly",
    "<": "is fewer than",
    "<=": "is at most",
    "!=": "is not",
}
QUANTIFIERS = {
    (">", "0"): "any",
    (">=", "1"): "at least one",
    (">", "1"): "more than one",
    ("==", "1"): "exactly one",
    (">=", "2"): "two or more",
}


NO_CHILDREN = "never becomes 1"


def _no_children(selector: Selector) -> str:
    labels = ", ".join(f"{m.label}{m.op}'{m.value}'" for m in selector.matchers)
    return f"{NO_CHILDREN} — no threshold rule carries {labels}"


class Unrecognised(Exception):
    """The expression does not match any shape this script knows how to word."""


@dataclass(frozen=True)
class Atom:
    """A single ``metric <op> threshold`` comparison."""

    window: str | None
    op: str
    rhs: str
    metrics: tuple[str, ...]


# ---------------------------------------------------------------- helpers
def _contains_comparison(node) -> bool:
    return any(
        isinstance(item, Bin) and item.op in COMPARISON_OPS
        for item in walk(node)
    )


def _rhs_text(node) -> str:
    text = unparse(node)
    while text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    return text


def _window_of(node) -> str | None:
    for item in walk(node):
        if isinstance(item, Call) and item.func in WINDOW_WORDS:
            for arg in item.args:
                if isinstance(arg, RangeSelector):
                    return f"{WINDOW_WORDS[item.func]} over {arg.window}"
            return WINDOW_WORDS[item.func]
    return None


def _metrics_in(node) -> tuple[str, ...]:
    names: list[str] = []
    for item in walk(node):
        if isinstance(item, Selector) and item.name and item.name not in names:
            names.append(item.name)
    return tuple(names)


def _atoms(node) -> list[Atom]:
    atoms = []
    for item in walk(node):
        if not (isinstance(item, Bin) and item.op in COMPARISON_OPS):
            continue
        if _contains_comparison(item.lhs) or _contains_comparison(item.rhs):
            continue
        atoms.append(
            Atom(_window_of(item.lhs), item.op, _rhs_text(item.rhs), _metrics_in(item.lhs))
        )
    return atoms


def _outer_comparison(node):
    for item in walk(node):
        if (
            isinstance(item, Bin)
            and item.op in COMPARISON_OPS
            and _contains_comparison(item.lhs)
        ):
            return item
    return None


def _top_combiner(node) -> str | None:
    """The operator joining the individual checks: '+' (a count) or 'or'."""
    node = unwrap(node)
    while isinstance(node, Agg) and node.args:
        node = unwrap(node.args[0])
    if isinstance(node, Bin) and node.op in ("+", "or"):
        return node.op
    return None


def _window_suffix(windows: set[str | None]) -> str:
    present = sorted(w for w in windows if w)
    if not present:
        return ""
    if len(present) == 2 and {p.split()[0] for p in present} == {"min", "max"}:
        return f" (min/max over {present[0].split(' over ')[-1]})"
    return f" ({present[0]})" if len(present) == 1 else f" ({', '.join(present)})"


def _threshold_clause(atoms: list[Atom]) -> tuple[str, int]:
    """Merge atoms sharing an operator and threshold, e.g. 'below 20 or above 85'."""
    merged: dict[tuple[str, str], list[str]] = {}
    for atom in atoms:
        merged.setdefault((atom.op, atom.rhs), []).extend(
            m for m in atom.metrics if m not in merged.get((atom.op, atom.rhs), [])
        )
    parts = [f"{OP_WORDS[op]} {rhs}" for op, rhs in merged]
    inputs = {metric for metrics in merged.values() for metric in metrics}
    return " or ".join(parts), len(inputs)


# ------------------------------------------------------- threshold rules
def describe_threshold(rule: Rule) -> str:
    """Describe when a threshold rule records a 1."""
    atoms = _atoms(rule.node)
    if not atoms:
        raise Unrecognised(rule.expr)

    clause, input_count = _threshold_clause(atoms)
    suffix = _window_suffix({atom.window for atom in atoms})
    outer = _outer_comparison(rule.node)

    if outer is None:
        if _top_combiner(rule.node) == "+" and len(atoms) > 1:
            return (
                f"counts how many inputs are {clause}{suffix} "
                f"— the value is 0–{len(atoms)}, not 0 or 1"
            )
        subject = "any input is " if input_count > 1 else ""
        return f"{subject}{clause}{suffix}"

    quantifier = QUANTIFIERS.get((outer.op, _rhs_text(outer.rhs)))
    if quantifier is None:
        return f"the number of inputs {clause}{suffix} {COUNT_WORDS[outer.op]} {_rhs_text(outer.rhs)}"
    if quantifier == "any":
        subject = "any input is " if input_count > 1 else ""
        return f"{subject}{clause}{suffix}"
    return f"{quantifier} input is {clause}{suffix}"


def describe_derived(rule: Rule) -> str:
    """One-line summary of an intermediate calculation."""
    return unparse(rule.node)


# ----------------------------------------------------- aggregation rules
class AggregationDescriber:
    """Word an aggregation rule and collect its immediate children."""

    def __init__(self, ruleset: RuleSet):
        self.ruleset = ruleset

    def _gloss(self, record: str) -> str:
        """Name what a child metric watches, so a record name alone is enough."""
        rule = self.ruleset.by_record.get(record)
        if rule is None or rule.kind != "threshold":
            return ""
        documentation = self.ruleset.documentation(rule)
        if documentation:
            return f" ({documentation.lower()})"
        counted = _count_summary(rule)
        return f" ({counted})" if counted else ""

    def describe(self, rule: Rule) -> tuple[str, list[str]]:
        children: list[str] = []
        clause = self._clause(rule.node, children)
        return clause, children

    # -- value phrases --------------------------------------------------
    def _value_phrase(self, node, children: list[str]) -> tuple[str, bool] | None:
        """Return (phrase, is_a_count) for something that has a numeric value."""
        node = unwrap(node)
        if isinstance(node, Agg) and len(node.args) == 1:
            inner = unwrap(node.args[0])
            if isinstance(inner, Selector) and inner.name is None:
                matches = self.ruleset.resolve_selector(inner)
                self._add(children, matches)
                is_count = node.func == "sum"
                if len(matches) == 1:
                    return matches[0] + self._gloss(matches[0]), is_count
                if not matches:
                    return _no_children(inner), False
                phrase = (
                    "the number of tripped child metrics"
                    if is_count
                    else "any of its child metrics"
                )
                return phrase, is_count
        if isinstance(node, Selector) and node.name:
            self._add(children, [node.name])
            return node.name + self._gloss(node.name), False
        return None

    def _add(self, children: list[str], names: list[str]) -> None:
        for name in names:
            if name not in children:
                children.append(name)

    # -- clauses --------------------------------------------------------
    def _clause(self, node, children: list[str]) -> str:
        node = unwrap(node)

        if isinstance(node, Agg) and len(node.args) == 1:
            inner = unwrap(node.args[0])
            if isinstance(inner, Bin):
                return self._clause(inner, children)
            phrase = self._value_phrase(node, children)
            if phrase is not None:
                return _standalone(phrase[0])

        if isinstance(node, Bin):
            if node.op in COMPARISON_OPS:
                return self._comparison(node, children)
            if node.op in ("+", "or"):
                return _join_or(
                    [self._clause(side, children) for side in (node.lhs, node.rhs)]
                )
            if node.op in ("*", "and"):
                return " and ".join(
                    _parenthesise(self._clause(side, children))
                    for side in (node.lhs, node.rhs)
                )

        phrase = self._value_phrase(node, children)
        if phrase is not None:
            return _standalone(phrase[0])
        raise Unrecognised(unparse(node))

    def _comparison(self, node: Bin, children: list[str]) -> str:
        rhs = _rhs_text(node.rhs)
        uniform = _uniform_sum(node.lhs)
        if uniform is not None:
            op, threshold, metrics = uniform
            self._add(children, list(metrics))
            quantifier = QUANTIFIERS.get((node.op, rhs), f"{COUNT_WORDS[node.op]} {rhs} of")
            return (
                f"{quantifier} of its child metrics is {OP_WORDS[op]} {threshold}"
                if quantifier in QUANTIFIERS.values()
                else f"the number of child metrics {OP_WORDS[op]} {threshold} {quantifier}"
            )

        phrase = self._value_phrase(node.lhs, children)
        if phrase is None:
            inner = self._clause(node.lhs, children)
            quantifier = QUANTIFIERS.get((node.op, rhs))
            if quantifier in (None, "any", "at least one"):
                return inner
            return f"{quantifier} of: {inner}"

        text, is_count = phrase
        if text.startswith(NO_CHILDREN):
            return text
        if is_count:
            return f"{text} {COUNT_WORDS[node.op]} {rhs}"
        if (node.op, rhs) == (">", "0"):
            return f"{text} is 1"
        if node.op == "==":
            return f"{text} is {rhs}"
        return f"{text} is {OP_WORDS[node.op]} {rhs}"


ANY_CHILD = "any of its child metrics"


def _join_or(clauses: list[str]) -> str:
    """Join terms, wording the label-matched group as 'other' when a rule also
    names a metric outside its selector (the LAN/NIC temperature checks)."""
    if len(clauses) == 2 and any(c.startswith(ANY_CHILD) for c in clauses):
        if not all(c.startswith(ANY_CHILD) for c in clauses):
            clauses = [
                c.replace(ANY_CHILD, "any other child metric", 1)
                if c.startswith(ANY_CHILD)
                else c
                for c in clauses
            ]
    return " or ".join(clauses)


def _count_summary(rule: Rule) -> str:
    """Describe a rule whose value is a count rather than a 0/1 flag."""
    atoms = _atoms(rule.node)
    if _outer_comparison(rule.node) is not None or _top_combiner(rule.node) != "+":
        return ""
    if len(atoms) < 2:
        return ""
    clause, _ = _threshold_clause(atoms)
    return f"a count of the {len(atoms)} inputs {clause}"


def _standalone(phrase: str) -> str:
    return phrase if phrase.startswith(NO_CHILDREN) else f"{phrase} is 1"


def _uniform_sum(node) -> tuple[str, str, tuple[str, ...]] | None:
    """Match ``(a < bool 1) + (b < bool 1) + ...`` — same test on several metrics."""
    node = unwrap(node)
    if not (isinstance(node, Bin) and node.op == "+"):
        return None
    atoms = _atoms(node)
    if len(atoms) < 2:
        return None
    if len({(atom.op, atom.rhs) for atom in atoms}) != 1:
        return None
    metrics = tuple(metric for atom in atoms for metric in atom.metrics)
    if len(metrics) != len(atoms):
        return None
    return atoms[0].op, atoms[0].rhs, metrics


def _parenthesise(clause: str) -> str:
    return f"({clause})" if " or " in clause else clause

##############################################################################
# Tables and command line
##############################################################################

RULES_DIR = "etc/prometheus_config"
SOURCE_DIR = "src/fhs_prometheus_exporter"

THRESHOLD_HEADERS = [
    "record",
    "source",
    "record_tag",
    "input metrics",
    "measures",
    "set to 1 when",
]
AGGREGATION_HEADERS = ["record", "child metrics", "set to 1 when"]
DERIVED_HEADERS = ["record", "input metrics", "calculation"]


def find_repo(start: Path) -> Path | None:
    """Walk up from a starting point looking for the exporter's rule files."""
    for candidate in (start, *start.parents):
        if (candidate / RULES_DIR / "threshold_rules.yml").is_file():
            return candidate
    return None


def describe_ref(repo: Path) -> str | None:
    """The ref a checkout is actually on, so the output says what it read."""
    for command in (
        ["git", "-C", str(repo), "describe", "--tags", "--exact-match"],
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
    ):
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return None


def build_ruleset(repo: Path) -> RuleSet:
    rules_dir = repo / RULES_DIR
    rules = load_rules(rules_dir / "threshold_rules.yml", "threshold")
    rules += load_rules(rules_dir / "aggregation_rules.yml", "aggregation")
    source_dir = repo / SOURCE_DIR
    metric_labels = scan_collectors(source_dir)
    # Without these labels every label-based selector matches nothing and the
    # health states all read "never becomes 1", so say what was found.
    collectors = sorted(path.name for path in source_dir.glob(COLLECTOR_GLOB))
    print(
        f"read {len(rules)} rules; labelled {len(metric_labels)} metrics from "
        f"{len(collectors)} collectors ({', '.join(collectors) or 'none found'})",
        file=sys.stderr,
    )
    return RuleSet(rules, metric_labels)


# ------------------------------------------------------------------ rows
def threshold_rows(ruleset: RuleSet, problems: list[str]) -> list[list[str]]:
    rows = []
    for rule in ruleset.rules:
        if rule.kind != "threshold":
            continue
        try:
            condition = describe_threshold(rule)
        except Unrecognised:
            problems.append(f"{rule.record}: {rule.expr}")
            condition = ""
        rows.append(
            [
                rule.record,
                ", ".join(rule.sources) or "unknown",
                rule.record_tag or "",
                ", ".join(rule.refs),
                ruleset.documentation(rule) or "",
                condition,
            ]
        )
    return rows


def aggregation_rows(ruleset: RuleSet, problems: list[str]) -> list[list[str]]:
    describer = AggregationDescriber(ruleset)
    rows = []
    for rule in ruleset.rules:
        if rule.kind != "aggregation":
            continue
        try:
            condition, children = describer.describe(rule)
        except Unrecognised:
            problems.append(f"{rule.record}: {rule.expr}")
            condition, children = "", []
        rows.append([rule.record, ", ".join(children) or "none", condition])
    return rows


def derived_rows(ruleset: RuleSet) -> list[list[str]]:
    return [
        [rule.record, ", ".join(rule.refs), rule.expr.replace("\n", " ").strip()]
        for rule in ruleset.rules
        if rule.kind == "derived"
    ]


# --------------------------------------------------------------- output
def _markdown_table(
    headers: list[str],
    rows: list[list[str]],
    name_columns: set[int] = frozenset(),
    code_columns: set[int] = frozenset(),
    names: set[str] = frozenset(),
) -> str:
    """name_columns hold comma-separated identifiers, code_columns whole
    expressions; identifiers in any other column are marked up via `names`."""
    pattern = (
        re.compile(r"(?<![`\w:])(" + "|".join(sorted(map(re.escape, names), key=len, reverse=True)) + r")(?![\w:])")
        if names
        else None
    )

    def cell(index: int, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            return ""
        if index in name_columns and value != "none":
            return ", ".join(f"`{part}`" for part in value.split(", "))
        if index in code_columns:
            return f"`{value}`".replace("|", "\\|")
        value = value.replace("|", "\\|")
        return pattern.sub(r"`\1`", value) if pattern else value

    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows:
        lines.append("| " + " | ".join(cell(i, value) for i, value in enumerate(row)) + " |")
    return "\n".join(lines)


def _intervals(ruleset: RuleSet, kind: str) -> set[str]:
    return {rule.interval for rule in ruleset.rules if rule.kind == kind and rule.interval}


def render_markdown(ruleset: RuleSet, args, problems: list[str], origin: str) -> str:
    thresholds = threshold_rows(ruleset, problems)
    aggregations = aggregation_rows(ruleset, problems)
    names = set(ruleset.by_record)

    parts = [
        "# FHS Prometheus rules",
        "",
        f"Generated by `{Path(__file__).name}` from "
        f"`{RULES_DIR}/threshold_rules.yml` and `{RULES_DIR}/aggregation_rules.yml` "
        f"at {origin}. Do not edit by hand.",
        "",
        "Every rule records `1` when it trips and `0` otherwise, so a rule that is "
        "`1` is the thing that failed.",
        "",
        "## Threshold rules",
        "",
        f"{len(thresholds)} checks against scraped metrics."
        + _interval_note(_intervals(ruleset, "threshold")),
        "",
        _markdown_table(THRESHOLD_HEADERS, thresholds, {0, 3}, names=names),
        "",
        "## Aggregation rules",
        "",
        f"{len(aggregations)} component health states, each built from the threshold "
        "rules listed as its child metrics."
        + _interval_note(_intervals(ruleset, "aggregation")),
        "",
        _markdown_table(AGGREGATION_HEADERS, aggregations, {0, 1}, names=names),
    ]

    if not args.no_derived:
        derived = derived_rows(ruleset)
        parts += [
            "",
            "## Derived metrics",
            "",
            f"{len(derived)} intermediate calculations. They are not checks; the "
            "threshold rules above compare against them.",
            "",
            _markdown_table(DERIVED_HEADERS, derived, {0, 1}, code_columns={2}),
        ]

    if problems:
        parts += [
            "",
            "## Not described",
            "",
            "These expressions did not match a known shape and need a look by hand:",
            "",
            *[f"- `{problem}`" for problem in problems],
        ]
    return "\n".join(parts) + "\n"


def _interval_note(intervals: set[str]) -> str:
    if len(intervals) == 1:
        return f" All of them re-evaluate every {intervals.pop()}."
    return ""


def write_csv(directory: Path, ruleset: RuleSet, problems: list[str], include_derived: bool) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    tables = {
        "threshold_rules.csv": (THRESHOLD_HEADERS, threshold_rows(ruleset, problems)),
        "aggregation_rules.csv": (AGGREGATION_HEADERS, aggregation_rows(ruleset, problems)),
    }
    if include_derived:
        tables["derived_metrics.csv"] = (DERIVED_HEADERS, derived_rows(ruleset))
    for name, (headers, rows) in tables.items():
        with (directory / name).open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo",
        type=Path,
        help="path to an exporter checkout (default: found by walking up from this script, then the working directory)",
    )
    parser.add_argument("--format", choices=("markdown", "csv"), default="markdown")
    parser.add_argument(
        "-o", "--output", type=Path, help="output file (markdown) or directory (csv); default stdout"
    )
    parser.add_argument("--no-derived", action="store_true", help="omit the derived metrics table")
    parser.add_argument(
        "--strict", action="store_true", help="exit non-zero if any expression could not be described"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    problems: list[str] = []

    repo = args.repo or find_repo(Path(__file__).resolve().parent) or find_repo(Path.cwd())
    if repo is None:
        print(
            f"error: no exporter checkout found — expected {RULES_DIR}/threshold_rules.yml "
            "above this script or the working directory; pass --repo",
            file=sys.stderr,
        )
        return 2

    checked_out = describe_ref(repo)
    origin = f"`{checked_out}`" if checked_out else f"`{repo}`"
    print(f"reading {repo}" + (f" (on {checked_out})" if checked_out else ""), file=sys.stderr)
    ruleset = build_ruleset(repo)

    if args.format == "csv":
        destination = args.output or Path.cwd()
        write_csv(destination, ruleset, problems, not args.no_derived)
        print(f"Wrote CSV tables to {destination}", file=sys.stderr)
    else:
        document = render_markdown(ruleset, args, problems, origin)
        if args.output:
            args.output.write_text(document)
            print(f"Wrote {args.output}", file=sys.stderr)
        else:
            sys.stdout.write(document)

    for problem in problems:
        print(f"warning: could not describe {problem}", file=sys.stderr)
    return 1 if problems and args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
