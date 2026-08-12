#!/usr/bin/env python3
"""Register a Databricks Unity Catalog external location on an FSx for ONTAP S3
Access Point and compare reads against a native S3 control.

Why this exists
---------------
This repository recorded, from May to August 2026, that "Unity Catalog External
Location does not support S3 Access Points". Measured on 2026-08-12 with a
native-S3 control running the identical test in the same session, that wording
was wrong in a way that mattered:

* Creating the storage credential, the external location and an external volume
  on an Access Point alias all **succeed**, with Unity Catalog's own validation
  enabled rather than skipped.
* **Reading** through them is denied. AWS authorises an Access Point request
  against the *access point ARN*, while the down-scoped session policy Unity
  Catalog attaches when it vends credentials is written in *bucket-style* ARNs.
  A session policy intersects with the role policy, so the access point ARN
  grant sitting in the role is irrelevant. The error says so:

      is not authorized to perform: s3:ListBucket on resource:
      "arn:aws:s3:<region>:<account>:accesspoint/<name>"
      because no session policy allows the s3:ListBucket action

The control is the point of this script. A bare failure against an Access Point
cannot be told apart from a mistake in your own IAM setup -- which is exactly how
the incorrect blocker survived three months. Every run therefore exercises a
native S3 path alongside the Access Point path and refuses to draw a conclusion
if the control does not behave.

Run it again after any Databricks release note that mentions external locations,
credential vending or access points. The failure is on the platform side, so it
can be fixed without anything changing here.

Prerequisites
-------------
* The IAM role from ``integrations/databricks/uc-storage-credential-role.yaml``.
* A Databricks CLI profile in ``~/.databrickscfg`` with a token scoped to at
  least ``unity-catalog``, ``files`` and ``sql``. Least privilege has a cost
  here: ``--vend-check`` additionally needs ``all-apis``, and revoking the token
  afterwards needs ``authentication``.
* A running SQL warehouse, or ``--warehouse-id`` to pick one. The FILE type and
  ``_object_metadata`` are not available on serverless *notebooks*; a serverless
  SQL warehouse is fine, which is what this uses.
* ``databricks-sdk`` installed, and the AWS CLI on PATH.

Usage
-----
    # the whole comparison, then clean up
    ./probe_uc_external_location.py --profile myprofile \\
        --role-arn arn:aws:iam::<account>:role/databricks-uc-fsxn-s3ap \\
        --ap-alias <alias>-ext-s3alias --ap-name my-ap \\
        --control-bucket databricks-uc-fsxn-s3ap-ctl-<account> \\
        --teardown-after

    # decisive test: use the credentials Unity Catalog itself vends, locally.
    # Needs External Data Access on the metastore plus EXTERNAL USE grants.
    ./probe_uc_external_location.py ... --vend-check

    # remove everything a previous run created, and nothing else
    ./probe_uc_external_location.py --profile myprofile --teardown-only

What this does NOT establish
---------------------------
Whether ``_object_metadata`` would read object tags through an Access Point if
the session policy were widened -- the read is refused before it reaches that
code. Nor anything about VPC-origin Access Points or Access Points with WINDOWS
identity: one INTERNET-origin, UNIX-root Access Point was exercised.

Evidence: verification-pack/databricks/file-type/evidence/2026-08-12/
Discussion: docs/en/databricks-file-type-evaluation.md, BLK-001
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any

# Names this script creates. Teardown removes exactly these and nothing else, so
# a run in a shared metastore cannot delete somebody else's objects.
CRED_NAME = "probe_uc_extloc_cred"
EXTLOC_CONTROL = "probe_uc_extloc_control"
EXTLOC_AP = "probe_uc_extloc_s3ap"
CONTROL_PREFIX = "control/"
AP_PREFIX = "_probe-uc-extloc/"

# Object tags written to both sides, so the comparison is like-for-like.
# ASCII only: tag keys and values are effectively ASCII on an FSx for ONTAP
# Access Point (see probe_s3ap_object_tagging.py).
PROBE_TAGS = "classification=internal&quality=gold&stage=probe"
PROBE_METADATA = "reviewer=ops,origin=probe"


def log(msg: str) -> None:
    print(msg, flush=True)


def aws(args: list[str], region: str | None = None) -> tuple[int, str]:
    """Run an AWS CLI command. Returns (exit code, combined output)."""
    cmd = ["aws"] + args
    if region:
        cmd += ["--region", region]
    env = dict(os.environ)
    # Ambient temporary credentials left over from an earlier assume-role are a
    # common cause of confusing failures here.
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        env.pop(k, None)
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return p.returncode, (p.stdout + p.stderr).strip()


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def seed(bucket: str, prefix: str, region: str, label: str) -> bool:
    """Write two tagged objects. Returns True on success."""
    body = f"/tmp/.probe-uc-extloc-{label}.txt"
    with open(body, "w") as fh:
        fh.write(f"probe payload for {label}\n")
    ok = True
    for name, extra in (("a.txt", ["--tagging", PROBE_TAGS]),
                        ("b.txt", ["--tagging", PROBE_TAGS,
                                   "--metadata", PROBE_METADATA])):
        rc, out = aws(["s3api", "put-object", "--bucket", bucket,
                       "--key", f"{prefix}{name}", "--body", body] + extra,
                      region)
        if rc != 0:
            log(f"  seed {label}/{name}: FAILED -- {out.splitlines()[-1][:160]}")
            ok = False
        else:
            log(f"  seed {label}/{name}: ok (3 tags"
                f"{', 2 user metadata' if 'metadata' in extra else ''})")
    os.unlink(body)
    return ok


# ---------------------------------------------------------------------------
# Databricks side
# ---------------------------------------------------------------------------

def sql(w: Any, warehouse_id: str, statement: str, label: str) -> list[list[str]] | None:
    """Run one statement. Returns rows, or None if it failed (and says why)."""
    try:
        r = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id, statement=statement, wait_timeout="50s")
    except Exception as exc:  # noqa: BLE001 - surfacing the message is the point
        log(f"  [{label}] EXCEPTION {type(exc).__name__}: {str(exc)[:300]}")
        return None
    state = str(r.status.state)
    if "SUCCEEDED" not in state:
        msg = r.status.error.message if r.status.error else "(no message)"
        log(f"  [{label}] {state}")
        log(f"      {msg[:400]}")
        return None
    rows = r.result.data_array if (r.result and r.result.data_array) else []
    log(f"  [{label}] SUCCEEDED, {len(rows)} row(s)")
    return rows


def pick_warehouse(w: Any, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    best = None
    for wh in w.warehouses.list():
        if "RUNNING" in str(wh.state):
            return wh.id
        best = best or wh.id
    if best:
        log(f"  no warehouse is RUNNING; starting {best} (this takes a minute)")
        try:
            w.api_client.do("POST", f"/api/2.0/sql/warehouses/{best}/start")
        except Exception as exc:  # noqa: BLE001
            log(f"  could not start it: {type(exc).__name__}: {str(exc)[:200]}")
            return best
        for _ in range(40):
            if "RUNNING" in str(w.warehouses.get(best).state):
                log("  warehouse is RUNNING")
                return best
            time.sleep(15)
    return best


def ensure_credential(w: Any, role_arn: str) -> str | None:
    """Create the storage credential if absent. Returns its external ID."""
    from databricks.sdk.service.catalog import AwsIamRole
    try:
        sc = w.storage_credentials.create(
            name=CRED_NAME, aws_iam_role=AwsIamRole(role_arn=role_arn),
            comment="temporary: UC external location probe")
        log(f"  storage credential created")
    except Exception as exc:  # noqa: BLE001
        if "already exists" not in str(exc):
            log(f"  storage credential FAILED: {type(exc).__name__}: {str(exc)[:300]}")
            return None
        sc = w.storage_credentials.get(CRED_NAME)
        log("  storage credential already present, reusing")
    ext = sc.aws_iam_role.external_id if sc.aws_iam_role else None
    log(f"  external ID Databricks expects: {ext}")
    log("  the IAM role's trust policy must condition sts:ExternalId on exactly this")
    return ext


def create_extloc(w: Any, name: str, url: str) -> tuple[bool, str]:
    """Create an external location with validation ON. Returns (ok, message)."""
    try:
        w.external_locations.create(name=name, url=url,
                                    credential_name=CRED_NAME,
                                    comment="temporary: UC external location probe",
                                    skip_validation=False)
        return True, "created with validation enabled"
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "already exists" in msg:
            return True, "already present"
        return False, f"{type(exc).__name__}: {msg[:300]}"


# ---------------------------------------------------------------------------
# The decisive test
# ---------------------------------------------------------------------------

def vend_check(w: Any, url: str, label: str, region: str) -> str:
    """Ask UC for the credentials it would use, then use them locally.

    This removes the Databricks network and the Databricks compute form from the
    picture: if a credential vended for one path works from here and a credential
    vended for another path does not, the difference is the session policy.
    """
    try:
        r = w.api_client.do("POST", "/api/2.0/unity-catalog/temporary-path-credentials",
                            body={"url": url, "operation": "PATH_READ"})
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "External Data Access" in msg:
            return ("not attempted: the metastore has External Data Access disabled. "
                    "A metastore admin can enable it; it also needs EXTERNAL USE SCHEMA "
                    "and EXTERNAL USE LOCATION grants")
        if "all-apis" in msg:
            return "not attempted: this token lacks the all-apis scope"
        return f"not attempted: {type(exc).__name__}: {msg[:200]}"

    creds = r.get("aws_temp_credentials") or {}
    if not creds:
        return "no credentials returned"
    env = dict(os.environ)
    env.pop("AWS_PROFILE", None)
    env["AWS_ACCESS_KEY_ID"] = creds["access_key_id"]
    env["AWS_SECRET_ACCESS_KEY"] = creds["secret_access_key"]
    env["AWS_SESSION_TOKEN"] = creds["session_token"]
    # Strip the scheme and split bucket / prefix back out of the URL.
    rest = url[len("s3://"):]
    bucket, _, prefix = rest.partition("/")
    p = subprocess.run(
        ["aws", "s3api", "list-objects-v2", "--bucket", bucket,
         "--prefix", prefix, "--max-keys", "3", "--region", region],
        capture_output=True, text=True, env=env)
    if p.returncode == 0:
        return "ListObjectsV2 SUCCEEDED with UC-vended credentials"
    tail = (p.stdout + p.stderr).strip().splitlines()[-1][:300]
    return f"ListObjectsV2 DENIED with UC-vended credentials -- {tail}"


# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------

def teardown(w: Any, control_bucket: str | None, ap_alias: str | None,
             region: str) -> None:
    log("teardown")
    for name in (EXTLOC_CONTROL, EXTLOC_AP):
        try:
            w.external_locations.delete(name, force=True)
            log(f"  external location {name}: deleted")
        except Exception as exc:  # noqa: BLE001
            log(f"  external location {name}: {type(exc).__name__} "
                f"({'absent' if 'does not exist' in str(exc) else str(exc)[:120]})")
    try:
        w.storage_credentials.delete(CRED_NAME, force=True)
        log(f"  storage credential {CRED_NAME}: deleted")
    except Exception as exc:  # noqa: BLE001
        log(f"  storage credential {CRED_NAME}: {type(exc).__name__} "
            f"({'absent' if 'does not exist' in str(exc) else str(exc)[:120]})")
    for bucket, prefix, label in ((control_bucket, CONTROL_PREFIX, "control"),
                                  (ap_alias, AP_PREFIX, "access point")):
        if not bucket:
            continue
        for name in ("a.txt", "b.txt"):
            rc, _ = aws(["s3api", "delete-object", "--bucket", bucket,
                         "--key", f"{prefix}{name}"], region)
            log(f"  {label} object {prefix}{name}: "
                f"{'deleted' if rc == 0 else 'not removed (may already be gone)'}")
    log("  the IAM role and the control bucket belong to the CloudFormation "
        "stack; delete the stack to remove them")


# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--profile", required=True,
                   help="Databricks CLI profile name from ~/.databrickscfg")
    p.add_argument("--role-arn", help="IAM role ARN for the storage credential")
    p.add_argument("--ap-alias", help="Access Point alias, ending in -s3alias")
    p.add_argument("--ap-name", help="Access Point name (for the report only)")
    p.add_argument("--control-bucket", help="native S3 bucket to use as the control")
    p.add_argument("--region", default=os.environ.get("AWS_REGION", "ap-northeast-1"))
    p.add_argument("--warehouse-id", help="SQL warehouse to use (default: pick one)")
    p.add_argument("--vend-check", action="store_true",
                   help="also test the credentials Unity Catalog vends, locally")
    p.add_argument("--teardown-after", action="store_true",
                   help="remove what this run created before exiting")
    p.add_argument("--teardown-only", action="store_true",
                   help="remove what a previous run created, then exit")
    args = p.parse_args()

    # Check the arguments before importing anything or touching the network, so a
    # missing flag reports itself as a missing flag rather than as a dependency
    # problem three layers down.
    if not args.teardown_only:
        missing = [f for f, v in (("--role-arn", args.role_arn),
                                  ("--ap-alias", args.ap_alias),
                                  ("--control-bucket", args.control_bucket)) if not v]
        if missing:
            log(f"missing required argument(s): {', '.join(missing)}")
            log("--control-bucket is required on purpose: a failure against the "
                "Access Point means nothing without a control that is expected to "
                "succeed. Deploy integrations/databricks/uc-storage-credential-role.yaml "
                "with CreateControlBucket=yes and pass the bucket it outputs.")
            return 2

    try:
        from databricks.sdk import WorkspaceClient
    except ImportError:
        log("databricks-sdk is not installed.")
        log("  python3 -m venv .venv && .venv/bin/pip install databricks-sdk")
        log("  then run this script with .venv/bin/python")
        return 2

    try:
        w = WorkspaceClient(profile=args.profile)
        me = w.current_user.me().user_name
    except Exception as exc:  # noqa: BLE001
        log(f"could not reach the workspace with profile '{args.profile}': "
            f"{type(exc).__name__}")
        log(f"  {str(exc)[:300]}")
        log("  Check ~/.databrickscfg has a [" + args.profile + "] section with host "
            "and token, that the token has not expired, and that its scopes include "
            "unity-catalog, files and sql.")
        return 2

    if args.teardown_only:
        teardown(w, args.control_bucket, args.ap_alias, args.region)
        return 0

    log(f"workspace user: {me}")
    wh = pick_warehouse(w, args.warehouse_id)
    if not wh:
        log("no SQL warehouse available")
        return 2

    log("\nseeding both sides with identical tags")
    control_seeded = seed(args.control_bucket, CONTROL_PREFIX, args.region, "control")
    ap_seeded = seed(args.ap_alias, AP_PREFIX, args.region, "access point")
    if not control_seeded:
        log("\nthe control bucket could not be seeded. Fix that before reading "
            "anything into the Access Point result.")
        return 1

    log("\nstorage credential")
    if ensure_credential(w, args.role_arn) is None:
        return 1

    log("\nexternal locations (validation enabled, not skipped)")
    results: dict[str, dict[str, Any]] = {}
    for label, name, url in (
            ("control", EXTLOC_CONTROL, f"s3://{args.control_bucket}/{CONTROL_PREFIX}"),
            ("s3ap", EXTLOC_AP, f"s3://{args.ap_alias}/{AP_PREFIX}")):
        ok, msg = create_extloc(w, name, url)
        results[label] = {"url": url, "registered": ok, "register_msg": msg}
        log(f"  {label}: {'OK' if ok else 'FAILED'} -- {msg}")

    log("\nreading _object_metadata through each location")
    for label in ("control", "s3ap"):
        if not results[label]["registered"]:
            results[label]["read"] = False
            continue
        url = results[label]["url"]
        rows = sql(w, wh,
                   f"SELECT _object_metadata FROM read_files('{url}', format => 'text')",
                   f"{label} read")
        results[label]["read"] = rows is not None
        if rows:
            first = rows[0][0] if rows[0] else ""
            has_tags = '"tags"' in first and '"tags":"{}"' not in first
            results[label]["tags_present"] = has_tags
            log(f"      object tags present in _object_metadata: "
                f"{'yes' if has_tags else 'no'}")

    if args.vend_check:
        log("\nUC-vended credentials, exercised from this machine")
        for label in ("control", "s3ap"):
            verdict = vend_check(w, results[label]["url"], label, args.region)
            results[label]["vend"] = verdict
            log(f"  {label}: {verdict}")

    # -----------------------------------------------------------------
    # Verdict. The control decides whether a conclusion is allowed at all.
    # -----------------------------------------------------------------
    log("\n" + "=" * 72)
    c, s = results["control"], results["s3ap"]
    if not c.get("read"):
        log("INCONCLUSIVE. The native S3 control could not be read either, so this "
            "run says nothing about Access Points.")
        log("Check the storage credential's external ID against the value printed "
            "above, and that the IAM role grants the control bucket.")
        rc = 1
    elif s.get("registered") and s.get("read"):
        log("The Access Point path WORKS: registered and read successfully.")
        log("This differs from the 2026-08-12 result. If it reproduces, BLK-001 has "
            "been resolved on the platform side -- update the blocker tracker and "
            "the compatibility matrix, and record the Databricks release that did it.")
        rc = 0
    elif s.get("registered") and not s.get("read"):
        log("Matches the 2026-08-12 result: registration succeeds, the read is denied.")
        log("Cause: AWS authorises the request against the access point ARN, while "
            "the session policy Unity Catalog vends is written in bucket-style ARNs.")
        log("There is no workaround on your side -- the session policy is generated "
            "by Unity Catalog. See BLK-001.")
        rc = 0
    else:
        log("The Access Point could not even be registered, which the 2026-08-12 run "
            "did achieve.")
        log("Most likely the IAM permission policy is missing the access point ARN "
            "form (arn:aws:s3:<region>:<account>:accesspoint/<name> and "
            ".../object/*). Granting only the alias-as-bucket ARN fails here while "
            "working from the AWS CLI.")
        log(f"Registration said: {s.get('register_msg')}")
        rc = 1
    log("=" * 72)

    if args.teardown_after:
        log("")
        teardown(w, args.control_bucket, args.ap_alias, args.region)
    else:
        log("\nNothing was removed. Re-run with --teardown-only to clean up, then "
            "delete the CloudFormation stack.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
