"""Turn rule expressions into plain-English descriptions."""

from __future__ import annotations

from dataclasses import dataclass

import promql
from rules import Rule, RuleSet

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


NO_CHILDREN = "never becomes 1 — no threshold rule carries these labels"


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
        isinstance(item, promql.Bin) and item.op in promql.COMPARISON_OPS
        for item in promql.walk(node)
    )


def _rhs_text(node) -> str:
    text = promql.unparse(node)
    while text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    return text


def _window_of(node) -> str | None:
    for item in promql.walk(node):
        if isinstance(item, promql.Call) and item.func in WINDOW_WORDS:
            for arg in item.args:
                if isinstance(arg, promql.RangeSelector):
                    return f"{WINDOW_WORDS[item.func]} over {arg.window}"
            return WINDOW_WORDS[item.func]
    return None


def _metrics_in(node) -> tuple[str, ...]:
    names: list[str] = []
    for item in promql.walk(node):
        if isinstance(item, promql.Selector) and item.name and item.name not in names:
            names.append(item.name)
    return tuple(names)


def _atoms(node) -> list[Atom]:
    atoms = []
    for item in promql.walk(node):
        if not (isinstance(item, promql.Bin) and item.op in promql.COMPARISON_OPS):
            continue
        if _contains_comparison(item.lhs) or _contains_comparison(item.rhs):
            continue
        atoms.append(
            Atom(_window_of(item.lhs), item.op, _rhs_text(item.rhs), _metrics_in(item.lhs))
        )
    return atoms


def _outer_comparison(node):
    for item in promql.walk(node):
        if (
            isinstance(item, promql.Bin)
            and item.op in promql.COMPARISON_OPS
            and _contains_comparison(item.lhs)
        ):
            return item
    return None


def _top_combiner(node) -> str | None:
    """The operator joining the individual checks: '+' (a count) or 'or'."""
    node = promql.unwrap(node)
    while isinstance(node, promql.Agg) and node.args:
        node = promql.unwrap(node.args[0])
    if isinstance(node, promql.Bin) and node.op in ("+", "or"):
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
    return promql.unparse(rule.node)


# ----------------------------------------------------- aggregation rules
class AggregationDescriber:
    """Word an aggregation rule and collect its immediate children."""

    def __init__(self, ruleset: RuleSet):
        self.ruleset = ruleset

    def describe(self, rule: Rule) -> tuple[str, list[str]]:
        children: list[str] = []
        clause = self._clause(rule.node, children)
        return clause, children

    # -- value phrases --------------------------------------------------
    def _value_phrase(self, node, children: list[str]) -> tuple[str, bool] | None:
        """Return (phrase, is_a_count) for something that has a numeric value."""
        node = promql.unwrap(node)
        if isinstance(node, promql.Agg) and len(node.args) == 1:
            inner = promql.unwrap(node.args[0])
            if isinstance(inner, promql.Selector) and inner.name is None:
                matches = self.ruleset.resolve_selector(inner)
                self._add(children, matches)
                is_count = node.func == "sum"
                if len(matches) == 1:
                    return matches[0], is_count
                if not matches:
                    return NO_CHILDREN, False
                phrase = (
                    "the number of tripped child metrics"
                    if is_count
                    else "any of its child metrics"
                )
                return phrase, is_count
        if isinstance(node, promql.Selector) and node.name:
            self._add(children, [node.name])
            return node.name, False
        return None

    def _add(self, children: list[str], names: list[str]) -> None:
        for name in names:
            if name not in children:
                children.append(name)

    # -- clauses --------------------------------------------------------
    def _clause(self, node, children: list[str]) -> str:
        node = promql.unwrap(node)

        if isinstance(node, promql.Agg) and len(node.args) == 1:
            inner = promql.unwrap(node.args[0])
            if isinstance(inner, promql.Bin):
                return self._clause(inner, children)
            phrase = self._value_phrase(node, children)
            if phrase is not None:
                return _standalone(phrase[0])

        if isinstance(node, promql.Bin):
            if node.op in promql.COMPARISON_OPS:
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
        raise Unrecognised(promql.unparse(node))

    def _comparison(self, node: promql.Bin, children: list[str]) -> str:
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
        if text == NO_CHILDREN:
            return NO_CHILDREN
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


def _standalone(phrase: str) -> str:
    return phrase if phrase == NO_CHILDREN else f"{phrase} is 1"


def _uniform_sum(node) -> tuple[str, str, tuple[str, ...]] | None:
    """Match ``(a < bool 1) + (b < bool 1) + ...`` — same test on several metrics."""
    node = promql.unwrap(node)
    if not (isinstance(node, promql.Bin) and node.op == "+"):
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
