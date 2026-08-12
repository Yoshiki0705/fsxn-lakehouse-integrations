#!/usr/bin/env python3
"""Redact credential-shaped strings from browser-automation snapshots on disk.

Why this exists
---------------
Browser automation returns an accessibility tree. When a page has a password
field that the browser's password manager has autofilled, the value is in that
tree, and the tree gets written to disk as a snapshot file. On 2026-08-12 an AWS
console sign-in page put a console password into a snapshot, and an earlier
snapshot captured a Databricks personal access token the same way.

Masking after the fact is the weaker half of the fix. The stronger half is not
snapshotting a page that has a password field at all -- fill it without reading
it back. See the browser-automation rule in AGENTS.md. This script exists for
the cases where that rule was not followed, so the value does not persist.

Idempotent: running it twice changes nothing the second time.

Usage
-----
    redact_browser_snapshots.py                # scan the default directories
    redact_browser_snapshots.py DIR [DIR ...]  # scan specific directories
    redact_browser_snapshots.py --check        # report only, exit 1 if hits

Exit codes
----------
    0  nothing found, or found and redacted
    1  --check was passed and unredacted credentials are present
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Directories browser-automation tooling writes snapshots into. Both the
# workspace-local and the temp-dir location are checked, because which one is
# used depends on the tool's working directory.
DEFAULT_DIRS = [
    Path(".playwright-mcp"),
    Path("/tmp/.playwright-mcp"),
    Path(os.environ.get("TMPDIR", "/tmp")) / ".playwright-mcp",
]

PLACEHOLDER = "<REDACTED-BY-redact_browser_snapshots>"

# Each pattern must match the secret itself, not the surrounding context, so
# that re.sub replaces only the value. Keep these anchored enough to avoid
# eating ordinary prose.
PATTERNS: dict[str, re.Pattern[str]] = {
    # Databricks personal access token
    "databricks-pat": re.compile(r"\bdapi[0-9a-f]{28,}\b"),
    # AWS access key IDs. The temporary (ASIA) form is the one that shows up in
    # assume-role output; the long-term (AKIA) form should never be here at all.
    "aws-access-key-id": re.compile(r"\b(?:ASIA|AKIA)[0-9A-Z]{16}\b"),
    # AWS STS session tokens start with a recognisable prefix and are long.
    "aws-session-token": re.compile(r"\bIQoJ[A-Za-z0-9/+=]{60,}"),
    # A password field whose value survived into the tree. The value is the
    # trailing group; the label is kept so the redaction is auditable.
    "password-field-value": re.compile(
        r'(?P<label>textbox\s+"(?:[^"]*(?:パスワード|[Pp]assword)[^"]*)"[^\n:]*:\s*)'
        r"(?P<value>\S[^\n]*)"
    ),
    # Bearer tokens and Authorization headers captured from network panels.
    "bearer-token": re.compile(r"(?i)\b(?:bearer|authorization:\s*bearer)\s+[A-Za-z0-9._\-]{20,}"),
}


def redact_text(text: str) -> tuple[str, dict[str, int]]:
    """Return the redacted text and a per-pattern hit count."""
    counts: dict[str, int] = {}
    for name, rx in PATTERNS.items():
        if name == "password-field-value":
            # Count only real changes. Returning the match unchanged still
            # counts as a substitution for subn(), which would make the script
            # report the same file forever.
            changed = 0

            def _sub(m: re.Match[str]) -> str:
                nonlocal changed
                if PLACEHOLDER in m.group("value"):
                    return m.group(0)
                changed += 1
                return m.group("label") + PLACEHOLDER

            text = rx.sub(_sub, text)
            n = changed
        else:
            text, n = rx.subn(PLACEHOLDER, text)
        if n:
            counts[name] = n
    return text, counts


def scan(dirs: list[Path], check_only: bool) -> int:
    total = 0
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if not f.is_file():
                continue
            try:
                original = f.read_text(errors="ignore")
            except OSError:
                continue
            redacted, counts = redact_text(original)
            if not counts:
                continue
            summary = ", ".join(f"{k} x{v}" for k, v in sorted(counts.items()))
            total += sum(counts.values())
            if check_only:
                print(f"UNREDACTED {f}: {summary}", file=sys.stderr)
            else:
                f.write_text(redacted)
                # Snapshots are transient artefacts; tighten permissions anyway
                # so a leftover file is not world-readable.
                try:
                    f.chmod(0o600)
                except OSError:
                    pass
                print(f"redacted {f}: {summary}", file=sys.stderr)
    if check_only and total:
        return 1
    return 0


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    args = [a for a in argv if not a.startswith("--")]
    dirs = [Path(a) for a in args] if args else DEFAULT_DIRS
    return scan(dirs, check_only)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
