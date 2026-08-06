#!/usr/bin/env python3
"""Find objects an unload attempt left on an FSx for ONTAP S3 Access Point.

Why this exists
---------------
Unloading to an Access Point backed stage does not fail cleanly. Measured
2026-08-06: Snowflake's ``COPY INTO @stage`` writes the object, the object is
intact, and then the statement fails with ``Remote upload failed checksum
validation`` because FSx for ONTAP reports server-side encryption as ``aws:fsx``
rather than ``AWS_SSE_S3`` or ``AWS_SSE_KMS``.

The caller is told the write failed while a complete object remains. Nothing in
the engine cleans it up, so the objects accumulate silently and can be picked up
later by a table or crawler that has no idea they came from a failed statement.

Tracked as BLK-009. See docs/en/blocker-tracker.md

What this reports
-----------------
Objects whose key matches the naming that unload operations generate. Snowflake
writes ``data_<n>_<n>_<n>.<ext>`` under the stage path; Spark and Glue write
``part-*`` with ``_SUCCESS`` markers. A prefix that holds unload-shaped files but
no ``_SUCCESS`` marker is the interesting case: the write started and no engine
declared it finished.

This is a heuristic on names, not proof. Read the summary, then decide. Use
``--delete`` only once you have looked.

Usage
-----
    # look
    ./check_orphaned_unload_objects.py --access-point <alias-or-arn>

    # narrow to one prefix
    ./check_orphaned_unload_objects.py --access-point <alias> --prefix exports/

    # machine readable
    ./check_orphaned_unload_objects.py --access-point <alias> --json

    # remove, after looking
    ./check_orphaned_unload_objects.py --access-point <alias> --delete

Exit codes
----------
    0  nothing suspicious found, or --delete completed
    1  an error
    2  suspicious objects found and --delete was not passed
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    sys.exit("boto3 is required: pip install boto3")

# Snowflake COPY INTO @stage output, e.g. data_0_0_0.csv.gz
SNOWFLAKE_UNLOAD = re.compile(r"(?:^|/)data_\d+_\d+_\d+\.[\w.]+$")
# Spark / Glue / EMR output, e.g. part-00000-<uuid>.snappy.parquet
SPARK_UNLOAD = re.compile(r"(?:^|/)part-\d{5}-[\w-]+\.[\w.]+$")
# Markers an engine writes when it considers the write complete
COMPLETION_MARKER = re.compile(r"(?:^|/)(_SUCCESS|_committed_[\w-]+|_delta_log/)")


def classify(key: str) -> str | None:
    if SNOWFLAKE_UNLOAD.search(key):
        return "snowflake-unload"
    if SPARK_UNLOAD.search(key):
        return "spark-unload"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Find objects an unload attempt left on an FSx for ONTAP "
                    "S3 Access Point (BLK-009).")
    ap.add_argument("--access-point", required=True,
                    help="Access Point alias or ARN. The alias is what "
                         "'aws fsx describe-s3-access-point-attachments' shows.")
    ap.add_argument("--prefix", default="",
                    help="Only look under this prefix. Default: whole Access Point.")
    ap.add_argument("--region", default=None, help="AWS region.")
    ap.add_argument("--profile", default=None, help="AWS CLI profile.")
    ap.add_argument("--delete", action="store_true",
                    help="Delete what was found. Look first.")
    ap.add_argument("--yes", action="store_true",
                    help="Skip the confirmation prompt. For use in automation.")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="Emit JSON instead of a report.")
    args = ap.parse_args()

    session = boto3.Session(profile_name=args.profile) if args.profile else boto3.Session()
    s3 = session.client("s3", region_name=args.region)

    # An Access Point alias is addressed as a bucket name.
    bucket = args.access_point

    findings: list[dict] = []
    prefixes: dict[str, dict] = defaultdict(
        lambda: {"suspect": 0, "bytes": 0, "has_marker": False, "other": 0})
    total_objects = 0

    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=args.prefix):
            for obj in page.get("Contents", []):
                total_objects += 1
                key, size = obj["Key"], obj["Size"]
                folder = key.rsplit("/", 1)[0] + "/" if "/" in key else "/"

                marker = COMPLETION_MARKER.search(key)
                if marker:
                    # A marker vouches for the table directory, not for the
                    # directory the marker file itself sits in. _delta_log/x.json
                    # means the table above _delta_log committed.
                    prefixes[key[:marker.start() + 1] or "/"]["has_marker"] = True
                    continue

                kind = classify(key)
                if kind:
                    prefixes[folder]["suspect"] += 1
                    prefixes[folder]["bytes"] += size
                    findings.append({
                        "key": key, "size": size, "kind": kind,
                        "prefix": folder,
                        "last_modified": obj["LastModified"].isoformat(),
                    })
                else:
                    prefixes[folder]["other"] += 1
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchBucket", "AccessDenied", "InvalidAccessPointAliasError"):
            print(f"ERROR Could not list '{bucket}': {code}", file=sys.stderr)
            print("      Check the alias, the region, and that your IAM identity "
                  "has s3:ListBucket on the Access Point.", file=sys.stderr)
            return 1
        raise

    # A prefix with unload-shaped files and no completion marker is the strong signal.
    unmarked = {p: v for p, v in prefixes.items()
                if v["suspect"] and not v["has_marker"]}

    if args.as_json:
        print(json.dumps({
            "access_point": bucket,
            "prefix_filter": args.prefix,
            "objects_scanned": total_objects,
            "suspect_objects": len(findings),
            "prefixes_without_completion_marker": sorted(unmarked),
            "findings": findings,
        }, indent=2))
        return 0 if not findings else (0 if args.delete else 2)

    print(f"Access Point : {bucket}")
    print(f"Prefix       : {args.prefix or '(all)'}")
    print(f"Objects seen : {total_objects}")
    print()

    if not findings:
        print("Nothing matching unload output naming was found.")
        print()
        print("That does not prove an unload was never attempted - it only means")
        print("nothing is left behind under the names engines normally use.")
        return 0

    print(f"Unload-shaped objects: {len(findings)}")
    print()
    for prefix in sorted(prefixes):
        v = prefixes[prefix]
        if not v["suspect"]:
            continue
        flag = "  <-- no completion marker" if not v["has_marker"] else ""
        print(f"  {prefix}")
        print(f"      {v['suspect']} file(s), {v['bytes']:,} bytes, "
              f"marker={'yes' if v['has_marker'] else 'no'}{flag}")
    print()

    if unmarked:
        print("Prefixes with unload output but no completion marker:")
        for p in sorted(unmarked):
            print(f"  {p}")
        print()
        print("On an FSx for ONTAP Access Point this is the shape BLK-009 leaves:")
        print("the engine reported failure, the bytes landed anyway. Confirm against")
        print("the engine's history - in Snowflake, COPY_HISTORY or QUERY_HISTORY for")
        print("a statement that failed on checksum validation around that timestamp.")
        print()
    else:
        print("Every prefix with unload output also has a completion marker, so these")
        print("are more likely to be deliberate output than BLK-009 leftovers.")
        print()

    if not args.delete:
        print("Re-run with --delete to remove them, once you have looked.")
        return 2

    if not args.yes:
        print(f"About to delete {len(findings)} object(s) from {bucket}.")
        reply = input("Type 'delete' to confirm: ").strip()
        if reply != "delete":
            print("Aborted. Nothing was deleted.")
            return 0

    deleted = 0
    for i in range(0, len(findings), 1000):
        batch = findings[i:i + 1000]
        resp = s3.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": f["key"]} for f in batch]})
        deleted += len(resp.get("Deleted", []))
        for err in resp.get("Errors", []):
            print(f"  FAILED {err.get('Key')}: {err.get('Message')}", file=sys.stderr)

    print(f"Deleted {deleted} of {len(findings)} object(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
