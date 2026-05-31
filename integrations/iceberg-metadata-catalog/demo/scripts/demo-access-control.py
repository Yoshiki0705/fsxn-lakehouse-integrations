#!/usr/bin/env python3
"""
demo-access-control.py — Governance & Access Control Demo

Demonstrates Lake Formation access control:
  1. Authorized user: query succeeds
  2. Revoke permission: query blocked
  3. Restore permission: query succeeds again

Also shows CloudTrail audit logging.

Usage:
    python demo-access-control.py --region ap-northeast-1
"""

import argparse
import json
import time

import boto3


def run_athena_query(athena, query, region):
    """Execute Athena query and return status + results."""
    query_id = athena.start_query_execution(
        QueryString=query,
        WorkGroup="primary",
        ResultConfiguration={"OutputLocation": f"s3://fsxn-athena-verification-results-{region}/demo/"},
    )["QueryExecutionId"]

    for _ in range(20):
        status = athena.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]
        state = status["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            return state, status["Status"].get("StateChangeReason", ""), query_id
        time.sleep(1)
    return "TIMEOUT", "", query_id


def main():
    parser = argparse.ArgumentParser(description="Access Control Demo")
    parser.add_argument("--region", default="ap-northeast-1")
    args = parser.parse_args()

    athena = boto3.client("athena", region_name=args.region)
    lf = boto3.client("lakeformation", region_name=args.region)
    ct = boto3.client("cloudtrail", region_name=args.region)
    sts = boto3.client("sts", region_name=args.region)

    account_id = sts.get_caller_identity()["Account"]
    caller_arn = sts.get_caller_identity()["Arn"]

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Governance Demo: Lake Formation Access Control              ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print(f"  User: {caller_arn}")
    print()

    query = 'SELECT file_name, classification FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files" LIMIT 3'

    # =========================================================================
    # Step 1: Authorized access
    # =========================================================================
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 1: Query with authorized user                          │")
    print("└──────────────────────────────────────────────────────────────┘")

    state, reason, qid = run_athena_query(athena, query, args.region)
    if state == "SUCCEEDED":
        results = athena.get_query_results(QueryExecutionId=qid)
        rows = results["ResultSet"]["Rows"]
        print(f"  ✅ Query SUCCEEDED ({len(rows)-1} rows)")
        for row in rows[1:]:
            values = [col.get("VarCharValue", "N/A") for col in row["Data"]]
            print(f"     → {values[0]} | {values[1]}")
    else:
        print(f"  Result: {state} — {reason}")
    print()

    # =========================================================================
    # Step 2: Revoke permission → Access denied
    # =========================================================================
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 2: Revoke SELECT → Query should be BLOCKED             │")
    print("└──────────────────────────────────────────────────────────────┘")

    try:
        lf.revoke_permissions(
            Principal={"DataLakePrincipalIdentifier": caller_arn},
            Resource={"Table": {"CatalogId": "s3tablescatalog/fsxn-metadata-catalog", "DatabaseName": "metadata", "Name": "unstructured_files"}},
            Permissions=["SELECT"],
        )
        print("  Permission revoked. Querying again...")
    except Exception as e:
        print(f"  ⚠️  Revoke skipped: {e}")

    time.sleep(2)
    state, reason, qid = run_athena_query(athena, query, args.region)
    if state == "FAILED" and "not authorized" in reason.lower():
        print(f"  🔒 Query BLOCKED: {reason[:80]}")
        print(f"     Lake Formation correctly denied access!")
    elif state == "FAILED":
        print(f"  🔒 Query FAILED: {reason[:80]}")
    else:
        print(f"  ⚠️  Unexpected: {state}")
    print()

    # =========================================================================
    # Step 3: Restore permission
    # =========================================================================
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 3: Restore SELECT → Query should succeed again         │")
    print("└──────────────────────────────────────────────────────────────┘")

    try:
        lf.grant_permissions(
            Principal={"DataLakePrincipalIdentifier": caller_arn},
            Resource={"Table": {"CatalogId": "s3tablescatalog/fsxn-metadata-catalog", "DatabaseName": "metadata", "Name": "unstructured_files"}},
            Permissions=["SELECT", "DESCRIBE"],
        )
        print("  Permission restored. Querying again...")
    except Exception as e:
        print(f"  ⚠️  Grant: {e}")

    time.sleep(2)
    state, reason, qid = run_athena_query(athena, query, args.region)
    if state == "SUCCEEDED":
        print(f"  ✅ Query SUCCEEDED — access restored")
    else:
        print(f"  Result: {state}")
    print()

    # =========================================================================
    # Step 4: Audit trail
    # =========================================================================
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 4: CloudTrail Audit Log                                │")
    print("└──────────────────────────────────────────────────────────────┘")

    events = ct.lookup_events(
        LookupAttributes=[{"AttributeKey": "EventSource", "AttributeValue": "athena.amazonaws.com"}],
        MaxResults=5,
    )["Events"]

    print(f"  Recent Athena events (last {len(events)}):")
    for event in events[:5]:
        print(f"    {event['EventTime'].strftime('%H:%M:%S')} | {event['EventName']} | {event.get('Username', 'N/A')}")
    print()
    print("  ✅ All access is audited — who, when, what query")
    print("  ✅ Lake Formation enforces governance on every query")


if __name__ == "__main__":
    main()
