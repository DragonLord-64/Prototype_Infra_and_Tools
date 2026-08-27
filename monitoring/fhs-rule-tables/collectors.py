"""Recovering the source/data_type labels from the collector modules.

The aggregation rules select on ``source`` and ``data_type`` labels that are
set in the exporter's Python, not in the rule files, so each ``*_collector.py``
is parsed with :mod:`ast` (never imported) to recover which labels every metric
series carries. :func:`scan_collectors` is the whole public surface.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

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
