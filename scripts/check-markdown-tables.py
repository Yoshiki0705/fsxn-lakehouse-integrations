#!/usr/bin/env python3
"""Detect Markdown structures that render as unreadable raw text.

Checks performed on every tracked ``*.md`` file:

1. Broken table    - a run of ``|`` rows without a header separator (``|---|``).
   This happens when a blockquote note or blank line is inserted in the middle
   of a table: every row after the interruption renders as one long paragraph.
2. Column mismatch - a data row whose column count differs from its header.
3. Unbalanced code fences - an odd number of ``` markers swallows the rest of
   the document into a code block.

Usage:
    python3 scripts/check-markdown-tables.py [path ...]

Exit code 1 if any issue is found.
"""

from __future__ import annotations

import os
import re
import sys

SEPARATOR = re.compile(r"^\|[\s:|-]+\|?\s*$")
SKIP_DIRS = {".git", "node_modules", ".playwright-mcp", ".private", ".venv"}


def count_columns(row: str) -> int:
    """Count cells in a table row, ignoring pipes inside inline code or escapes."""
    body = row.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]

    cells = 1
    in_code = False
    i = 0
    while i < len(body):
        char = body[i]
        if char == "\\":
            i += 2
            continue
        if char == "`":
            in_code = not in_code
        elif char == "|" and not in_code:
            cells += 1
        i += 1
    return cells


def check_file(path: str) -> list[str]:
    lines = open(path, encoding="utf-8").read().split("\n")
    problems: list[str] = []

    in_fence = False
    fence_count = 0
    run: list[tuple[int, str]] = []
    header_cols = 0

    def close_run() -> None:
        nonlocal run
        if not run:
            return
        start, first = run[0]
        if len(run) < 2 or not SEPARATOR.match(run[1][1]):
            problems.append(
                f"{path}:{start}: broken table - {len(run)} row(s) with no header "
                f"separator (renders as raw text): {first[:70]}"
            )
        run = []

    for index, line in enumerate(lines):
        lineno = index + 1
        stripped = line.strip()

        if stripped.startswith("```"):
            fence_count += 1
            in_fence = not in_fence
            close_run()
            continue
        if in_fence:
            continue

        if not stripped.startswith("|"):
            close_run()
            continue

        run.append((lineno, stripped))
        if len(run) == 1:
            header_cols = count_columns(stripped)
        elif not SEPARATOR.match(stripped):
            actual = count_columns(stripped)
            if actual != header_cols:
                problems.append(
                    f"{path}:{lineno}: column mismatch - header has {header_cols} "
                    f"column(s), row has {actual}: {stripped[:70]}"
                )

    close_run()

    if fence_count % 2:
        problems.append(
            f"{path}: unbalanced code fences ({fence_count} ``` markers) - "
            "the rest of the document renders as a code block"
        )

    return problems


def main() -> int:
    roots = sys.argv[1:] or ["."]
    problems: list[str] = []

    for root in roots:
        if os.path.isfile(root):
            problems.extend(check_file(root))
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in sorted(filenames):
                if name.endswith(".md"):
                    problems.extend(check_file(os.path.join(dirpath, name)))

    for problem in problems:
        print(problem)

    if problems:
        print(f"\n{len(problems)} Markdown rendering issue(s) found.")
        return 1

    print("No Markdown rendering issues found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
