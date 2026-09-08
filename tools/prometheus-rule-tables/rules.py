"""Reading the rule files: the rule model, labels and selector matching.

:func:`build_ruleset` is the entry point — it locates the two YAML rule files,
parses every expression, attaches the collector labels, and returns a
:class:`RuleSet` that can resolve a label selector to the rules it matches.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from collectors import COLLECTOR_GLOB, MetricLabels, scan_collectors
from promql import Matcher, Selector, parse_promql, walk

RULES_DIR = "etc/prometheus_config"
SOURCE_DIR = "src/fhs_prometheus_exporter"

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
