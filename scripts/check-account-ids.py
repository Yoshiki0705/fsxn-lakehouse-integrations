#!/usr/bin/env python3
"""Detect real AWS account IDs in tracked files.

The concern is publishing a *real* account ID (see the public-output safety rule:
account IDs must never be published). AWS reserves 123456789012 and a handful of
other numbers for documentation, so those are the correct thing to write in
examples and are allowed here -- the previous version of this check flagged them,
which made it fail on 70 legitimate placeholder occurrences while never being able
to catch an actual leak.

A 12-digit number is only treated as an account ID when it appears in a position
where AWS puts one (ARN account field, an AccountId-style key, an S3 Access Point
alias, or an ECR registry host). This avoids flagging unrelated 12-digit values
such as byte sizes (107374182400 = 100 GiB).

Usage:
    python3 scripts/check-account-ids.py [path ...]     # default: git ls-files

Exit code 1 if a non-allowlisted account ID is found.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

# AWS-reserved documentation account IDs.
# https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-identifiers.html
RESERVED_EXAMPLE_IDS = {
    "123456789012",
    "111122223333",
    "444455556666",
    "555555555555",
    "222222222222",
    "333333333333",
}

# Third-party account IDs that are published by their owner and are required
# verbatim for cross-account trust policies.
PUBLIC_THIRD_PARTY_IDS = {
    "414351767826": "Databricks control plane (published by Databricks)",
}

ALLOWED = RESERVED_EXAMPLE_IDS | set(PUBLIC_THIRD_PARTY_IDS)

ACCOUNT_POSITIONS = [
    ("arn", re.compile(r"arn:aws[a-z0-9-]*:[a-z0-9-]*:[a-z0-9-]*:(\d{12}):")),
    ("account-key", re.compile(r"(?i)account[_ -]?id[\"' ]*[:=][\"' ]*(\d{12})")),
    ("s3-ap-alias", re.compile(r"-(\d{12})-[a-z0-9-]*s3alias")),
    ("ecr-host", re.compile(r"(\d{12})\.dkr\.ecr\.")),
]

SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".parquet")


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, text=True, check=True
    ).stdout
    return [p for p in out.split("\0") if p]


def main() -> int:
    paths = sys.argv[1:] or tracked_files()
    findings: list[str] = []
    allowed_hits = 0

    for path in paths:
        if path.lower().endswith(SKIP_SUFFIXES) or path == "scripts/check-account-ids.py":
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.read().split("\n")
        except (IsADirectoryError, FileNotFoundError, OSError):
            continue

        for lineno, line in enumerate(lines, 1):
            for kind, pattern in ACCOUNT_POSITIONS:
                for match in pattern.finditer(line):
                    account = match.group(1)
                    if account in ALLOWED:
                        allowed_hits += 1
                        continue
                    findings.append(
                        f"{path}:{lineno} [{kind}] {account} - replace with the "
                        f"reserved example ID 123456789012 or <ACCOUNT_ID>"
                    )

    in_actions = "GITHUB_ACTIONS" in os.environ
    for finding in findings:
        print(f"::error::{finding}" if in_actions else finding)

    if findings:
        print(f"\n{len(findings)} possible real AWS account ID(s) found.")
        return 1

    print(
        f"No real AWS account IDs found "
        f"({allowed_hits} allowlisted example/public ID occurrence(s))."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
