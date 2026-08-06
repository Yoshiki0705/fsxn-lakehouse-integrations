#!/usr/bin/env python3
"""Create, populate and exercise an Iceberg table on an FSx for ONTAP S3 Access Point.

Why this is worth having
------------------------
Iceberg writes generally do not work against an FSx for ONTAP S3 Access Point: the
Access Point does not implement conditional writes (BLK-002), and unload leaves
objects behind (BLK-009). Athena is the exception. The Glue Data Catalog holds the
current-metadata pointer, so a commit is a conditional update in Glue rather than
on S3, and the Access Point never has to support the operation that is missing.

Measured 2026-08-06: CREATE TABLE, INSERT, SELECT, UPDATE, DELETE, time travel,
OPTIMIZE, VACUUM and two concurrent commits all succeeded, with data and metadata
both on the Access Point.
See verification-pack/athena-iceberg/evidence/2026-08-06/

This script reproduces that in your own account so you can confirm it before
designing around it, and so you can see what the operations cost in your
environment rather than in ours.

Usage
-----
    ./iceberg_quickstart.py \
        --access-point-alias my-ap-abc123-ext-s3alias \
        --athena-output s3://my-athena-results/prefix/

    # keep the table afterwards to poke at it
    ./iceberg_quickstart.py --access-point-alias ... --athena-output ... --keep

    # see the statements without running them
    ./iceberg_quickstart.py --access-point-alias ... --athena-output ... --dry-run

Arguments you have to supply, and where to find them
----------------------------------------------------
--access-point-alias   aws fsx describe-s3-access-point-attachments \
                         --query 'S3AccessPointAttachments[].S3AccessPoint.Alias'
--athena-output        Any standard S3 location you can write to. Athena needs
                       somewhere for query results. This is NOT the Access Point.

Costs
-----
Athena bills per byte scanned. This script writes single-digit row counts, so the
scan cost is effectively zero; the 2026-08-06 run cost under USD 0.01. The table
is dropped at the end unless --keep is passed.
"""
from __future__ import annotations

import argparse
import sys
import time

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    sys.exit("boto3 is required: pip install boto3")


class Athena:
    def __init__(self, region: str, database: str, output: str,
                 workgroup: str, dry_run: bool):
        self.client = boto3.client("athena", region_name=region)
        self.database = database
        self.output = output
        self.workgroup = workgroup
        self.dry_run = dry_run
        self.failures = 0

    def run(self, sql: str, label: str, expect_rows: bool = False,
            allow_failure: bool = False) -> list[list[str]] | None:
        one_line = " ".join(sql.split())
        if self.dry_run:
            print(f"  [dry-run ] {label}")
            print(f"             {one_line[:150]}")
            return None

        qid = self.client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": self.database},
            ResultConfiguration={"OutputLocation": self.output},
            WorkGroup=self.workgroup,
        )["QueryExecutionId"]

        t0 = time.time()
        while True:
            q = self.client.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
            state = q["Status"]["State"]
            if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            time.sleep(1.5)
        ms = int((time.time() - t0) * 1000)

        if state != "SUCCEEDED":
            reason = q["Status"].get("StateChangeReason", "")
            marker = "expected" if allow_failure else "UNEXPECTED"
            print(f"  [{state:<9}] {label}  ({ms} ms)  <-- {marker}")
            if reason:
                print(f"             {reason[:220]}")
            if not allow_failure:
                self.failures += 1
            return None

        rows = None
        if expect_rows:
            res = self.client.get_query_results(QueryExecutionId=qid, MaxResults=10)
            rows = [[c.get("VarCharValue") for c in r["Data"]]
                    for r in res["ResultSet"]["Rows"]][1:]
        scanned = q.get("Statistics", {}).get("DataScannedInBytes", 0)
        extra = f"  rows={rows}" if rows else ""
        print(f"  [SUCCEEDED] {label}  ({ms} ms, {scanned:,} B scanned){extra}")
        return rows


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Exercise an Iceberg table on an FSx for ONTAP S3 Access Point "
                    "using Athena.")
    ap.add_argument("--access-point-alias", required=True,
                    help="Access Point alias, e.g. my-ap-abc123-ext-s3alias")
    ap.add_argument("--athena-output", required=True,
                    help="s3:// location for Athena query results. Standard S3.")
    ap.add_argument("--database", default="fsxn_iceberg_quickstart",
                    help="Glue database. Created if absent.")
    ap.add_argument("--table", default="iceberg_quickstart",
                    help="Table name.")
    ap.add_argument("--prefix", default="athena-iceberg-quickstart/",
                    help="Prefix on the Access Point for the table.")
    ap.add_argument("--workgroup", default="primary", help="Athena workgroup.")
    ap.add_argument("--region", default="ap-northeast-1", help="AWS region.")
    ap.add_argument("--keep", action="store_true",
                    help="Leave the table and its objects in place.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the statements, run nothing.")
    args = ap.parse_args()

    if not args.athena_output.startswith("s3://"):
        sys.exit("--athena-output must start with s3://")
    if args.access_point_alias in args.athena_output:
        sys.exit("--athena-output must not be on the Access Point. Athena writes "
                 "result files there, and writes to an Access Point are the thing "
                 "we are working around. Use a standard S3 bucket.")
    prefix = args.prefix if args.prefix.endswith("/") else args.prefix + "/"
    location = f"s3://{args.access_point_alias}/{prefix}"
    # Athena rejects double-quoted identifiers in DDL such as DROP TABLE, but
    # requires them for the metadata tables because of the '$'.
    fq = f"{args.database}.{args.table}"
    meta = f'"{args.database}"."{args.table}'

    print(f"region    : {args.region}")
    print(f"database  : {args.database}")
    print(f"table     : {args.table}")
    print(f"location  : {location}")
    print(f"results   : {args.athena_output}")
    print()

    if not args.dry_run:
        glue = boto3.client("glue", region_name=args.region)
        try:
            glue.create_database(DatabaseInput={"Name": args.database})
            print(f"  created Glue database {args.database}")
        except glue.exceptions.AlreadyExistsException:
            print(f"  Glue database {args.database} already exists")
        except ClientError as e:
            sys.exit(f"Could not create the Glue database: {e}")
        print()

    a = Athena(args.region, args.database, args.athena_output,
               args.workgroup, args.dry_run)

    print("--- create and load ---")
    a.run(f"DROP TABLE IF EXISTS {fq}", "DROP TABLE (clean slate)")
    a.run(f"""CREATE TABLE {fq} (
                  sensor_id int,
                  reading   double,
                  recorded  timestamp
              )
              LOCATION '{location}'
              TBLPROPERTIES ('table_type'='ICEBERG', 'format'='parquet')""",
          "CREATE TABLE (Iceberg)")
    a.run(f"""INSERT INTO {fq} VALUES
                  (1, 21.5, TIMESTAMP '2026-01-01 10:00:00'),
                  (2, 22.1, TIMESTAMP '2026-01-01 10:01:00'),
                  (3, 23.7, TIMESTAMP '2026-01-01 10:02:00')""",
          "INSERT")
    a.run(f"SELECT count(*) FROM {fq}", "SELECT count(*)", expect_rows=True)

    print()
    print("--- the operations that usually fail on storage without conditional writes ---")
    a.run(f"UPDATE {fq} SET reading = 99.9 WHERE sensor_id = 1", "UPDATE (row-level)")
    a.run(f"SELECT reading FROM {fq} WHERE sensor_id = 1", "SELECT after UPDATE",
          expect_rows=True)
    a.run(f"DELETE FROM {fq} WHERE sensor_id = 3", "DELETE (row-level)")
    a.run(f"SELECT count(*) FROM {fq}", "count after DELETE", expect_rows=True)

    a.run(f'SELECT count(*) FROM {meta}$snapshots"',
          "snapshot count", expect_rows=True)
    first = a.run(f'SELECT snapshot_id FROM {meta}$snapshots" '
                  f"ORDER BY committed_at LIMIT 1", "first snapshot id",
                  expect_rows=True)
    if first and first[0][0]:
        a.run(f"SELECT count(*) FROM {fq} FOR VERSION AS OF {first[0][0]}",
              "time travel to the first snapshot", expect_rows=True)

    a.run(f"OPTIMIZE {fq} REWRITE DATA USING BIN_PACK", "OPTIMIZE (compaction)")
    a.run(f"VACUUM {fq}", "VACUUM (expire snapshots)")

    if not args.dry_run:
        print()
        print("--- where the files actually live ---")
        s3 = boto3.client("s3", region_name=args.region)
        try:
            objs = s3.list_objects_v2(
                Bucket=args.access_point_alias, Prefix=prefix).get("Contents", [])
            data = [o for o in objs if "/data/" in o["Key"]]
            meta = [o for o in objs if "/metadata/" in o["Key"]]
            print(f"  on the Access Point: {len(objs)} object(s) "
                  f"({len(data)} data, {len(meta)} metadata)")
            for o in objs[:4]:
                print(f"      {o['Key']}")
            if meta:
                print("  Metadata on the Access Point alongside the data confirms the")
                print("  table is not secretly living somewhere else.")
        except ClientError as e:
            print(f"  could not list the Access Point: {e}")

    if not args.keep:
        print()
        print("--- cleanup ---")
        a.run(f"DROP TABLE IF EXISTS {fq}", "DROP TABLE")
        if not args.dry_run:
            s3 = boto3.client("s3", region_name=args.region)
            try:
                objs = s3.list_objects_v2(
                    Bucket=args.access_point_alias, Prefix=prefix).get("Contents", [])
                if objs:
                    s3.delete_objects(
                        Bucket=args.access_point_alias,
                        Delete={"Objects": [{"Key": o["Key"]} for o in objs]})
                    print(f"  removed {len(objs)} leftover object(s)")
                else:
                    print("  no leftover objects")
            except ClientError as e:
                print(f"  could not clean the Access Point: {e}")
    else:
        print()
        print(f"--keep passed. {fq} and its objects were left in place.")
        print(f"  Remove later with: DROP TABLE {fq}")
        print(f"  then: aws s3 rm --recursive s3://{args.access_point_alias}/{prefix}")

    print()
    if args.dry_run:
        print("Dry run finished. Nothing was created.")
        return 0
    if a.failures:
        print(f"{a.failures} statement(s) failed unexpectedly.")
        print("If CREATE TABLE failed mentioning the location, check that the Access")
        print("Point alias is right and that your IAM identity has s3:PutObject on it.")
        print("If everything failed, check the Athena workgroup and output location.")
        return 1
    print("All statements succeeded. Iceberg read and write work on this Access Point.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
