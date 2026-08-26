#!/usr/bin/env python3
"""Generate plain-English tables for the FHS Prometheus rules.

Reads the threshold and aggregation rule files from the
ska-mid-cbf-fhs-prometheus-exporter repository and writes two tables:

  1. every threshold rule and the condition that sets it to 1;
  2. every aggregation rule, its child metrics, and what makes it fail.

The ``source``/``data_type`` labels the aggregation rules select on are set by
the exporter's collectors, so they are read out of the collector modules — no
mapping is maintained here by hand.

  ./generate_rule_tables.py --git-url <repo> --ref 0.0.5-rc3 -o rules.md
  ./generate_rule_tables.py --repo ../ska-mid-cbf-fhs-prometheus-exporter
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import describe as describe_module  # noqa: E402
from collectors import scan_collectors  # noqa: E402
from describe import AggregationDescriber, Unrecognised, describe_threshold  # noqa: E402
from rules import Rule, RuleSet, load_rules  # noqa: E402

DEFAULT_GIT_URL = (
    "https://gitlab.com/ska-telescope/ska-mid-cbf/host-software/"
    "ska-mid-cbf-fhs-prometheus-exporter.git"
)
DEFAULT_REF = "0.0.5-rc3"
RULES_DIR = "etc/prometheus_config"
SOURCE_DIR = "src/fhs_prometheus_exporter"

THRESHOLD_HEADERS = ["record", "source", "record_tag", "input metrics", "set to 1 when"]
AGGREGATION_HEADERS = ["record", "child metrics", "set to 1 when"]
DERIVED_HEADERS = ["record", "input metrics", "calculation"]


def clone(git_url: str, ref: str, destination: Path) -> Path:
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", ref, git_url, str(destination)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    return destination


def build_ruleset(repo: Path) -> RuleSet:
    rules_dir = repo / RULES_DIR
    rules = load_rules(rules_dir / "threshold_rules.yml", "threshold")
    rules += load_rules(rules_dir / "aggregation_rules.yml", "aggregation")
    return RuleSet(rules, scan_collectors(repo / SOURCE_DIR))


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
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--repo", type=Path, help="path to an exporter checkout")
    source.add_argument(
        "--git-url", default=DEFAULT_GIT_URL, help="clone this repository instead (default: %(default)s)"
    )
    parser.add_argument("--ref", default=DEFAULT_REF, help="tag/branch to clone (default: %(default)s)")
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

    with tempfile.TemporaryDirectory() as workdir:
        if args.repo:
            repo = args.repo
            origin = f"`{repo}`"
        else:
            repo = clone(args.git_url, args.ref, Path(workdir) / "exporter")
            origin = f"`{args.ref}`"
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
