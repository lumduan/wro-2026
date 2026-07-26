#!/usr/bin/env python3
"""Assert that hub-bound code stays inside the MicroPython subset.

``docs/FIELD_TEST_PLAN.md`` Step 1 states the project's core invariant — *"mission
code imports only ``robot_io.RobotIO``, so one file runs on the simulator and on
hardware"* — and then admits it is **an untested claim**. It also assumes the
test needs two hubs.

Most of it does not. The risk is not electrical, it is linguistic: the simulator
is CPython 3.13 and both hubs are MicroPython, EV3's from May 2020. A construct
that CPython accepts and MicroPython rejects is a syntax error discovered on the
competition table. This module finds it on every commit instead.

Hardware still tests what only hardware can — that the Pybricks calls do what
their docs say. What it no longer has to catch is an f-string.

**Every rule cites its evidence.** A lint rule without a source is a style
opinion, and this repo does not accept those.
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Iterable, Sequence

#: Directories whose contents may be copied onto a hub.
DEFAULT_ROOTS: Final = (Path("robot"),)

#: Modules a hub can actually resolve. Anything else fails at import there.
#: `robot_io` is the contract itself; `pybricks.*` exists only on a hub and is
#: imported lazily inside the hardware backends, never at module scope.
ALLOWED_IMPORTS: Final = frozenset({
    "robot_io", "robot_io_ev3", "robot_io_spike",
    "math", "sys", "micropython", "utime", "time",
})

#: Import prefixes allowed in addition to the exact names above.
ALLOWED_IMPORT_PREFIXES: Final = ("pybricks.",)

#: Modules that simply do not exist on these MicroPython ports.
FORBIDDEN_IMPORTS: Final = {
    "typing": "not present on MicroPython",
    "dataclasses": "not present on MicroPython",
    "abc": "not present on MicroPython; the contract uses a plain class instead",
    "enum": "not present on MicroPython",
    "__future__": "MicroPython has no __future__ imports",
    "numpy": "CPython-only; simulator code must not be imported by a mission",
    "json": "present on some ports only; not relied on here",
    "logging": "not present on MicroPython",
}


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    rule: str
    detail: str
    source: str

    def __str__(self) -> str:
        return (f"{self.path}:{self.line}: [{self.rule}] {self.detail}\n"
                f"    evidence: {self.source}")


FSTRING_SOURCE: Final = (
    "MicroPython added f-strings in 1.17 (September 2021); EV3 MicroPython "
    "v2.0 is 18 May 2020, so f-strings are a SyntaxError on the EV3. "
    "pybricks.com/ev3-micropython/")
ASYNC_SOURCE: Final = (
    "async/await are not available on the EV3 and SPIKE Pybricks ports")
IMPORT_SOURCE: Final = (
    "a hub resolves only its own frozen modules; anything else fails at import")


class _Visitor(ast.NodeVisitor):
    def __init__(self, path: Path):
        self.path = path
        self.findings: list[Finding] = []

    # f-strings ------------------------------------------------------- #
    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        self.findings.append(Finding(
            self.path, node.lineno, "no-fstring",
            "f-string; use concatenation or .format()", FSTRING_SOURCE))
        self.generic_visit(node)

    # async ----------------------------------------------------------- #
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.findings.append(Finding(
            self.path, node.lineno, "no-async",
            "async def", ASYNC_SOURCE))
        self.generic_visit(node)

    def visit_Await(self, node: ast.Await) -> None:
        self.findings.append(Finding(
            self.path, node.lineno, "no-async", "await", ASYNC_SOURCE))
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.findings.append(Finding(
            self.path, node.lineno, "no-async", "async for", ASYNC_SOURCE))
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self.findings.append(Finding(
            self.path, node.lineno, "no-async", "async with", ASYNC_SOURCE))
        self.generic_visit(node)

    # imports --------------------------------------------------------- #
    def _check_module(self, module: str | None, lineno: int) -> None:
        if not module:
            return
        root = module.split(".")[0]
        if root in FORBIDDEN_IMPORTS:
            self.findings.append(Finding(
                self.path, lineno, "forbidden-import",
                f"import {module} — {FORBIDDEN_IMPORTS[root]}", IMPORT_SOURCE))
            return
        if module in ALLOWED_IMPORTS or root in ALLOWED_IMPORTS:
            return
        if any(module.startswith(p) for p in ALLOWED_IMPORT_PREFIXES):
            return
        self.findings.append(Finding(
            self.path, lineno, "unlisted-import",
            f"import {module} is not on the hub allowlist", IMPORT_SOURCE))

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_module(alias.name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            self.findings.append(Finding(
                self.path, node.lineno, "no-relative-import",
                "relative import; hub files are copied flat", IMPORT_SOURCE))
        else:
            self._check_module(node.module, node.lineno)
        self.generic_visit(node)

    # annotations ----------------------------------------------------- #
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.findings.append(Finding(
            self.path, node.lineno, "no-annotation",
            "variable annotation; MicroPython parses but `typing` is absent, "
            "so annotations naming typing constructs fail at import",
            "MicroPython has no typing module"))
        self.generic_visit(node)


def check_file(path: Path) -> list[Finding]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    visitor = _Visitor(path)
    visitor.visit(tree)
    return visitor.findings


def python_files(roots: Iterable[Path]) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        if root.is_file():
            out.append(root)
        else:
            out.extend(p for p in sorted(root.rglob("*.py"))
                       if "__pycache__" not in p.parts)
    return out


def check(roots: Iterable[Path]) -> list[Finding]:
    return [f for path in python_files(roots) for f in check_file(path)]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="*", type=Path, default=list(DEFAULT_ROOTS))
    args = parser.parse_args(argv)

    roots = args.roots or list(DEFAULT_ROOTS)
    files = python_files(roots)
    findings = check(roots)
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} portability problem(s) in {len(files)} file(s)")
        return 1
    print(f"{len(files)} file(s) are inside the MicroPython subset:")
    for path in files:
        print(f"   {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
