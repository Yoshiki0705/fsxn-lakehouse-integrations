#!/usr/bin/env python3
"""Record, then verify, the AWS footprint of a Databricks workspace created with
"Use your existing cloud account".

Why this exists
---------------
That workspace mode creates a VPC, a NAT Gateway, an Elastic IP, subnets, an
internet gateway, an S3 gateway endpoint, security groups, an S3 bucket and two
IAM roles **directly** -- not as a CloudFormation stack. Deleting the workspace
in the Databricks account console does not remove any of them. A forgotten NAT
Gateway is roughly 45 USD a month.

On 2026-08-12 the teardown needed eleven separate deletions in a specific order,
and two of them only succeeded after removing dependencies the console does not
mention: security groups had to be emptied of rules before deletion, and the main
route table cannot be deleted separately because it goes with the VPC.

Comparing against a baseline is the part that makes this trustworthy. "It looks
clean" is not the same as "it matches what was there before I started", and in a
shared account the difference matters -- several of the resources this reports are
named after other people's environments.

Usage
-----
    # before creating the workspace
    ./audit_databricks_workspace_footprint.py --region ap-northeast-1 \\
        --save baseline.json

    # after tearing it down
    ./audit_databricks_workspace_footprint.py --region ap-northeast-1 \\
        --compare baseline.json

    # just look
    ./audit_databricks_workspace_footprint.py --region ap-northeast-1

Exit codes
----------
    0  no differences from the baseline, or no baseline given
    1  resources exist that were not in the baseline

What this does NOT do
--------------------
It does not delete anything. Deletion order matters and a wrong order leaves a
half-removed VPC, so the removal is a documented runbook step rather than an
automated sweep. See docs/en/databricks-verification-runbook.md.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

# Chargeable things first: these are the ones that cost money if forgotten.
# Each entry is (label, aws cli args, JMESPath, chargeable).
PROBES: list[tuple[str, list[str], str, bool]] = [
    ("NAT gateways (available)",
     ["ec2", "describe-nat-gateways", "--filter", "Name=state,Values=available"],
     "NatGateways[].NatGatewayId", True),
    ("Elastic IPs (unassociated)",
     ["ec2", "describe-addresses"],
     "Addresses[?AssociationId==null].AllocationId", True),
    ("EC2 instances (running or pending)",
     ["ec2", "describe-instances",
      "--filters", "Name=instance-state-name,Values=running,pending"],
     "Reservations[].Instances[].InstanceId", True),
    ("Databricks-managed VPCs",
     ["ec2", "describe-vpcs", "--filters", "Name=tag:Name,Values=databricks-*"],
     "Vpcs[].VpcId", False),
    ("Databricks workspace S3 buckets",
     ["s3api", "list-buckets"],
     "Buckets[?starts_with(Name, 'databricks-storage-')].Name", True),
    ("Databricks workspace IAM roles",
     ["iam", "list-roles"],
     "Roles[?starts_with(RoleName, 'databricks-compute-role-') || "
     "starts_with(RoleName, 'databricks-storage-role-')].RoleName", False),
    ("S3 gateway endpoints in a Databricks VPC",
     ["ec2", "describe-vpc-endpoints",
      "--filters", "Name=service-name,Values=com.amazonaws.*.s3"],
     "VpcEndpoints[].VpcEndpointId", False),
]

GLOBAL_SERVICES = {"iam", "s3api"}


def probe(args_: list[str], query: str, region: str) -> list[str]:
    cmd = ["aws"] + args_ + ["--query", query, "--output", "json"]
    if args_[0] not in GLOBAL_SERVICES:
        cmd += ["--region", region]
    env = dict(os.environ)
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        env.pop(k, None)
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if p.returncode != 0:
        return [f"<error: {(p.stderr or p.stdout).strip().splitlines()[-1][:120]}>"]
    try:
        val = json.loads(p.stdout or "null")
    except json.JSONDecodeError:
        return ["<error: unparseable response>"]
    if val is None:
        return []
    return [str(v) for v in val] if isinstance(val, list) else [str(val)]


def collect(region: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for label, args_, query, _chargeable in PROBES:
        out[label] = probe(args_, query, region)
    return out


def render(snapshot: dict[str, list[str]]) -> None:
    charge = {label: c for label, _a, _q, c in PROBES}
    for label, ids in snapshot.items():
        marker = "$" if charge.get(label) and ids else " "
        print(f" {marker} {label}: {len(ids)}")
        for i in ids[:12]:
            print(f"      {i}")
        if len(ids) > 12:
            print(f"      ... and {len(ids) - 12} more")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--region", required=True)
    p.add_argument("--save", metavar="FILE", help="write this snapshot as a baseline")
    p.add_argument("--compare", metavar="FILE", help="compare against a baseline")
    args = p.parse_args()

    print(f"footprint in {args.region}   ($ marks chargeable resources)")
    now = collect(args.region)
    render(now)

    if args.save:
        with open(args.save, "w") as fh:
            json.dump({"region": args.region, "snapshot": now}, fh, indent=2)
        print(f"\nbaseline written to {args.save}")
        print("Re-run with --compare after teardown. Without a baseline, "
              "'it looks clean' is not a verifiable claim.")
        return 0

    if not args.compare:
        print("\nNo baseline given, so this is a listing rather than a verdict.")
        print("In a shared account many of these belong to other environments.")
        return 0

    try:
        with open(args.compare) as fh:
            base = json.load(fh)
    except OSError as exc:
        print(f"\ncannot read baseline: {exc}")
        return 2
    if base.get("region") != args.region:
        print(f"\nbaseline was taken in {base.get('region')}, not {args.region}")
        return 2

    print("\ndifferences from baseline")
    added_total = 0
    for label in now:
        before = set(base["snapshot"].get(label, []))
        after = set(now[label])
        added = sorted(after - before)
        removed = sorted(before - after)
        if not added and not removed:
            continue
        print(f"  {label}")
        for i in added:
            print(f"    + {i}   (not in baseline)")
        for i in removed:
            print(f"    - {i}   (was in baseline, now gone)")
        added_total += len(added)

    if added_total:
        print(f"\n{added_total} resource(s) exist that were not in the baseline.")
        print("If a teardown just ran, these are what it missed. Removal order "
              "matters -- see the runbook.")
        return 1
    print("\nNothing exists that was not in the baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
