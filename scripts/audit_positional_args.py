#!/usr/bin/env python3
"""Flag functions/methods with 3+ consecutive same-typed positional parameters.

Spike for https://github.com/Youth-Research-Center/PandaPlot/issues/239: a call
with several same-typed positional arguments in a row (e.g. three `str`
parameters) is easy to accidentally swap, and a type checker won't catch it.
This script scans function/method definitions for that shape so call sites can
be spot-checked and converted to keyword arguments where it helps clarity.

This is a standalone dev tool, not wired into CI or pre-commit: false
positives are expected (e.g. a `(x: float, y: float)` point pair reads fine
positionally), so results are meant to be skimmed by a human, not enforced.

Usage:
    uv run python scripts/audit_positional_args.py [path ...]
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path

# Types where a positional swap is genuinely easy to make and easy to miss.
# Booleans are excluded: ruff's FBT rules already cover that case (see #238).
FLAGGED_TYPES = {"str", "int", "float"}

DEFAULT_TARGETS = ["pandaplot", "pandaplot_storybook"]


@dataclass
class Finding:
    path: Path
    lineno: int
    func_name: str
    param_names: list[str]
    type_name: str


def _annotation_name(annotation: ast.expr | None) -> str | None:
    if annotation is None:
        return None
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return annotation.value
    return None


def _check_function(path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[Finding]:
    # posonlyargs (before a `/`) come first in calling order, and are even more
    # squarely "positional" than plain args, which a caller could pass by keyword.
    args = [*node.args.posonlyargs, *node.args.args]
    # Drop a leading self/cls: it's never passed positionally by a caller.
    if args and args[0].arg in ("self", "cls"):
        args = args[1:]

    findings: list[Finding] = []
    run_names: list[str] = []
    run_type: str | None = None

    def flush() -> None:
        if run_type is not None and len(run_names) >= 3:
            findings.append(
                Finding(
                    path=path,
                    lineno=node.lineno,
                    func_name=node.name,
                    param_names=list(run_names),
                    type_name=run_type,
                )
            )

    for arg in args:
        type_name = _annotation_name(arg.annotation)
        if type_name in FLAGGED_TYPES and type_name == run_type:
            run_names.append(arg.arg)
            continue
        flush()
        run_names = [arg.arg] if type_name in FLAGGED_TYPES else []
        run_type = type_name if type_name in FLAGGED_TYPES else None
    flush()

    return findings


def audit_file(path: Path) -> list[Finding]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        print(f"warning: could not parse {path}: {exc}", file=sys.stderr)
        return []

    findings: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            findings.extend(_check_function(path, node))
    return findings


def audit_paths(targets: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for target in targets:
        target_path = Path(target)
        files = [target_path] if target_path.is_file() else sorted(target_path.rglob("*.py"))
        for path in files:
            findings.extend(audit_file(path))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", default=DEFAULT_TARGETS)
    args = parser.parse_args()

    findings = audit_paths(args.paths)
    for finding in findings:
        params = ", ".join(finding.param_names)
        print(f"{finding.path}:{finding.lineno}: {finding.func_name}({params}) -- {len(finding.param_names)} {finding.type_name} in a row")

    print(f"\n{len(findings)} function(s) flagged", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
