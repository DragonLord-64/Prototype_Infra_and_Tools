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

This file is only the command line. The work is split across four modules that
sit beside it, in the order the data flows:

  ``promql.py``      parses an expression into an AST (helpers for the rest)
  ``collectors.py``  reads the collector modules for the metric labels
  ``rules.py``       reads the rule files and resolves selectors to rules
  ``describe.py``    turns rules into English and builds the table rows
  ``render.py``      writes those rows out as Markdown or CSV
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rules import RULES_DIR, build_ruleset, describe_ref, find_repo
from render import render_markdown, write_csv


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
        document = render_markdown(ruleset, args, problems, origin, Path(__file__).name)
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
