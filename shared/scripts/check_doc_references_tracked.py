#!/usr/bin/env python3
"""Verify that files referenced from tracked documentation are themselves tracked.

Why this exists
---------------
A link check that asks the filesystem "does this path exist?" passes for a file
that exists on the author's machine but is not in the repository. The reader who
clones the repository gets a dead reference, and CI says the documentation is fine.

That is not hypothetical. On 2026-08-12 a runbook was written pointing at
``integrations/databricks/uc-storage-credential-role.yaml`` and a parameter
example. Both files matched a broad ``*credential*`` rule in ``.gitignore`` and
silently did not commit. Everything worked locally. Nothing would have worked for
anybody else.

The existing link check in docs-quality.yml has the same blind spot twice over: it
tests ``[[ -e ]]`` against the working tree, and its ``BROKEN`` counter is
incremented inside a pipeline subshell, so the value never escapes and the step
cannot fail. A gate whose success is not evidence that it ran is worth replacing
rather than trusting.

This script asks git, not the filesystem, and it exits non-zero.

The general rule this enforces
------------------------------
Writing a file is not the same as the file being in effect. A configuration file
can be silently ineffective, and a deliverable can be silently absent, and in both
cases the local machine gives no signal because locally everything is present.
This script converts the repository half of that rule into a check.

What it deliberately does not cover: agent configuration under ``.kiro/`` --
steering files, skills and hooks. Those are gitignored in this repository, so
repository CI cannot see them, and a hook that never registers still fails
silently. That half remains a human check when adding one: confirm the file meets
the registration conditions rather than assuming that saving it was enough.

Usage
-----
    ./check_doc_references_tracked.py            # all tracked markdown
    ./check_doc_references_tracked.py FILE ...   # only these files

Exit codes
----------
    0  every referenced path is tracked
    1  at least one reference is missing or untracked
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Only check references to files we would expect to live in the repository.
# Links to directories, anchors, URLs and mail addresses are out of scope.
CHECKED_SUFFIXES = {
    ".md", ".yaml", ".yml", ".json", ".py", ".sh", ".sql", ".tf", ".ts", ".txt",
    ".csv", ".ipynb", ".toml", ".cfg", ".ini",
}

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          check=False).stdout


def tracked_files() -> set[str]:
    return {line for line in git("ls-files", "-z").split("\0") if line}


def main(argv: list[str]) -> int:
    tracked = tracked_files()
    if not tracked:
        print("not inside a git repository, or nothing is tracked", file=sys.stderr)
        return 1

    targets = [a for a in argv if a.endswith(".md")] or sorted(
        f for f in tracked if f.endswith(".md"))

    missing: list[tuple[str, str, str]] = []
    for md in targets:
        p = Path(md)
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        for m in LINK.finditer(text):
            raw = m.group(1)
            if raw.startswith(("http://", "https://", "mailto:", "#", "<")):
                continue
            target = raw.split("#", 1)[0]
            if not target:
                continue
            suffix = Path(target).suffix.lower()
            if suffix not in CHECKED_SUFFIXES:
                continue
            # Resolve relative to the referring document, then normalise to a
            # repository-relative path the way git spells it.
            resolved = (p.parent / target).resolve()
            try:
                rel = resolved.relative_to(Path.cwd().resolve()).as_posix()
            except ValueError:
                # Points outside the repository. Report rather than guess.
                missing.append((md, raw, "outside the repository"))
                continue
            if rel in tracked:
                continue
            reason = ("present on disk but NOT tracked by git"
                      if resolved.exists() else "does not exist")
            missing.append((md, raw, reason))

    if not missing:
        print(f"✓ every referenced path in {len(targets)} document(s) is tracked")
        return 0

    untracked = [x for x in missing if "NOT tracked" in x[2]]
    print(f"✗ {len(missing)} reference(s) will not resolve for someone who clones "
          f"this repository\n")
    for md, raw, reason in missing:
        print(f"  {md}")
        print(f"    -> {raw}   ({reason})")
    if untracked:
        print("\nThe 'present on disk but NOT tracked' cases are the dangerous ones: "
              "they work for you and fail for everyone else.")
        print("Check .gitignore before assuming the file was added. A broad pattern "
              "such as *credential* or *secret* will match a legitimate filename.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
