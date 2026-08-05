#!/usr/bin/env python3
"""Benchmark ListObjectsV2 latency: FSx for ONTAP S3 Access Point vs native S3.

Why this exists
---------------
Documentation across this repository states that ListObjectsV2 against an
FSx for ONTAP S3 Access Point is "30-80x slower than native S3". That figure
needs reproducible evidence, because it drives real design decisions:

  * Polling-based ingestion (EventBridge Schedule -> Lambda -> ListObjectsV2)
    cannot poll faster than a single list call takes to complete.
  * Snowflake ``ALTER EXTERNAL TABLE ... REFRESH`` and Directory Table refresh
    both perform a full listing.
  * Databricks Auto Loader directory-listing mode performs a full listing.

This script measures the wall-clock time of a *fully paginated* ListObjectsV2
against two targets holding an identical set of objects, and reports the
distribution across repeated trials.

What is measured
----------------
Only the paginated ListObjectsV2 loop is timed. Client construction, credential
resolution, and object setup are all outside the timed region. Each target gets
one discarded warm-up call before the recorded trials, so the reported numbers
reflect steady-state behaviour rather than first-call overhead.

Usage
-----
    python3 benchmark_list_objects.py \
        --ap-arn arn:aws:s3:<region>:<account>:accesspoint/<ap-name> \
        --native-bucket my-comparison-bucket \
        --counts 10,100,1000 \
        --trials 5 \
        --output-json results.json

    # Tear down the objects this script created, then exit:
    python3 benchmark_list_objects.py ... --teardown-only

Notes
-----
* ``--native-bucket`` is optional. Without it the script measures the Access
  Point alone and skips the ratio calculation.
* Objects are written under ``--prefix`` (default ``listbench/``) and are
  removed by ``--teardown`` / ``--teardown-only``. Nothing outside that prefix
  is touched.
* Object bodies are intentionally tiny (a few bytes). ListObjectsV2 returns
  metadata only, so object size does not affect listing cost, and small bodies
  keep setup fast and storage cost negligible.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Any

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    sys.exit("boto3 is required: pip install boto3")


# Setup/teardown parallelism. Measurement is always sequential.
SETUP_WORKERS = 32

# Deliberately generous: a single slow list call is the phenomenon under test,
# so the client must not abort it before it completes.
READ_TIMEOUT_SECONDS = 900
CONNECT_TIMEOUT_SECONDS = 30


@dataclass
class TrialSet:
    """Recorded latencies for one (target, object_count) combination."""

    target_label: str
    target_bucket: str
    object_count: int
    keys_listed: int
    api_calls: int
    layout: str = "flat"
    durations_ms: list[float] = field(default_factory=list)

    @property
    def median_ms(self) -> float:
        return statistics.median(self.durations_ms)

    @property
    def mean_ms(self) -> float:
        return statistics.fmean(self.durations_ms)

    @property
    def min_ms(self) -> float:
        return min(self.durations_ms)

    @property
    def max_ms(self) -> float:
        return max(self.durations_ms)

    @property
    def stdev_ms(self) -> float:
        return statistics.stdev(self.durations_ms) if len(self.durations_ms) > 1 else 0.0

    def summary(self) -> dict[str, Any]:
        return {
            "target_label": self.target_label,
            "layout": self.layout,
            "object_count": self.object_count,
            "keys_listed": self.keys_listed,
            "api_calls_per_trial": self.api_calls,
            "trials": len(self.durations_ms),
            "median_ms": round(self.median_ms, 1),
            "mean_ms": round(self.mean_ms, 1),
            "min_ms": round(self.min_ms, 1),
            "max_ms": round(self.max_ms, 1),
            "stdev_ms": round(self.stdev_ms, 1),
            "durations_ms": [round(d, 1) for d in self.durations_ms],
        }


def make_client(region: str):
    """Build an S3 client tuned for long, slow list calls."""
    return boto3.client(
        "s3",
        region_name=region,
        config=Config(
            connect_timeout=CONNECT_TIMEOUT_SECONDS,
            read_timeout=READ_TIMEOUT_SECONDS,
            retries={"max_attempts": 1, "mode": "standard"},
        ),
    )


def timed_full_list(client, bucket: str, prefix: str) -> tuple[float, int, int]:
    """Fully paginate ListObjectsV2 and return (elapsed_ms, key_count, api_calls).

    The timer brackets only the pagination loop. Nothing else is included.
    """
    keys = 0
    api_calls = 0
    token: str | None = None

    start = time.perf_counter()
    while True:
        kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
        if token:
            kwargs["ContinuationToken"] = token
        resp = client.list_objects_v2(**kwargs)
        api_calls += 1
        keys += len(resp.get("Contents", []))
        if resp.get("IsTruncated"):
            token = resp.get("NextContinuationToken")
        else:
            break
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    return elapsed_ms, keys, api_calls


def build_key(prefix: str, index: int, layout: str, fanout: int) -> str:
    """Return the object key for `index` under the requested layout.

    ONTAP maps S3 keys onto real filesystem paths, so the shape of the key space
    (one wide directory vs. many nested directories) can affect listing cost in
    ways that do not apply to native S3's flat keyspace. ``nested`` emulates the
    date-partitioned layouts common in lakehouse workloads.
    """
    if layout == "flat":
        return f"{prefix}obj-{index:06d}.txt"
    # nested: prefix/d000/d000/obj-000000.txt, fanout entries per leaf directory
    leaf = index // fanout
    outer = leaf // fanout
    inner = leaf % fanout
    return f"{prefix}d{outer:03d}/d{inner:03d}/obj-{index:06d}.txt"


def seed_objects(
    client,
    bucket: str,
    prefix: str,
    count: int,
    layout: str = "flat",
    fanout: int = 10,
) -> int:
    """Ensure exactly `count` objects exist under `prefix`. Returns objects written."""
    body = b"listbench"

    def put(i: int) -> None:
        client.put_object(
            Bucket=bucket, Key=build_key(prefix, i, layout, fanout), Body=body
        )

    written = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=SETUP_WORKERS) as pool:
        futures = {pool.submit(put, i): i for i in range(count)}
        for fut in concurrent.futures.as_completed(futures):
            fut.result()  # surface any error
            written += 1
    return written


def delete_prefix(client, bucket: str, prefix: str) -> int:
    """Delete every object under `prefix`. Returns count deleted.

    Re-lists from the start after each delete batch rather than following a
    continuation token: the token refers to a keyspace that the delete has just
    mutated, which caused batches to be skipped. Looping until the listing comes
    back empty is slower but leaves nothing behind.
    """
    deleted = 0
    while True:
        resp = client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1000)
        contents = resp.get("Contents", [])
        if not contents:
            break

        objects = [{"Key": o["Key"]} for o in contents]
        # delete_objects (batch) is not universally available on FSx for ONTAP
        # S3 Access Points, so fall back to per-object deletes on failure.
        try:
            client.delete_objects(Bucket=bucket, Delete={"Objects": objects})
        except ClientError:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=SETUP_WORKERS
            ) as pool:
                list(
                    pool.map(
                        lambda o: client.delete_object(Bucket=bucket, Key=o["Key"]),
                        objects,
                    )
                )
        deleted += len(objects)
    return deleted


def run_target(
    client,
    label: str,
    bucket: str,
    base_prefix: str,
    counts: list[int],
    trials: int,
    layout: str = "flat",
    fanout: int = 10,
) -> list[TrialSet]:
    """Seed and measure one target across all requested object counts."""
    results: list[TrialSet] = []

    for count in counts:
        prefix = f"{base_prefix}{layout}-n{count:06d}/"
        print(f"  [{label}] seeding {count} objects under {prefix} ...", flush=True)
        seed_objects(client, bucket, prefix, count, layout, fanout)

        # Discarded warm-up: excludes cold connection / metadata cache effects.
        print(f"  [{label}] warm-up list ...", flush=True)
        warm_ms, warm_keys, _ = timed_full_list(client, bucket, prefix)
        print(f"  [{label}] warm-up: {warm_ms:.0f} ms ({warm_keys} keys)", flush=True)

        if warm_keys != count:
            print(
                f"  [{label}] WARNING: expected {count} keys, listed {warm_keys}",
                flush=True,
            )

        ts = TrialSet(
            target_label=label,
            target_bucket=bucket,
            object_count=count,
            keys_listed=warm_keys,
            api_calls=0,
            layout=layout,
        )
        for t in range(1, trials + 1):
            elapsed_ms, keys, api_calls = timed_full_list(client, bucket, prefix)
            ts.durations_ms.append(elapsed_ms)
            ts.api_calls = api_calls
            ts.keys_listed = keys
            print(
                f"  [{label}] trial {t}/{trials}: {elapsed_ms:.0f} ms "
                f"({keys} keys, {api_calls} API call(s))",
                flush=True,
            )
        results.append(ts)

    return results


def build_comparison(
    ap_results: list[TrialSet], native_results: list[TrialSet]
) -> list[dict[str, Any]]:
    """Pair AP and native results by object count and compute the slowdown ratio."""
    native_by_count = {r.object_count: r for r in native_results}
    rows = []
    for ap in ap_results:
        native = native_by_count.get(ap.object_count)
        if native is None:
            continue
        rows.append(
            {
                "object_count": ap.object_count,
                "fsx_ontap_ap_median_ms": round(ap.median_ms, 1),
                "native_s3_median_ms": round(native.median_ms, 1),
                "slowdown_factor": round(ap.median_ms / native.median_ms, 1)
                if native.median_ms > 0
                else None,
            }
        )
    return rows


def markdown_table(comparison: list[dict[str, Any]]) -> str:
    lines = [
        "| Objects | FSx for ONTAP S3 AP (median) | Native S3 (median) | Slowdown |",
        "|--------:|-----------------------------:|-------------------:|---------:|",
    ]
    for row in comparison:
        factor = row["slowdown_factor"]
        factor_cell = f"{factor:.1f}x" if factor is not None else "n/a"
        lines.append(
            f"| {row['object_count']} "
            f"| {row['fsx_ontap_ap_median_ms']:.0f} ms "
            f"| {row['native_s3_median_ms']:.0f} ms "
            f"| {factor_cell} |"
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Benchmark ListObjectsV2: FSx for ONTAP S3 AP vs native S3.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--ap-arn",
        required=True,
        help="FSx for ONTAP S3 Access Point ARN (used as the Bucket parameter).",
    )
    p.add_argument(
        "--native-bucket",
        default=None,
        help="Native S3 bucket name for comparison. Omit to measure the AP only.",
    )
    p.add_argument("--region", default="ap-northeast-1", help="AWS region.")
    p.add_argument(
        "--prefix",
        default="listbench/",
        help="Key prefix for benchmark objects (default: listbench/).",
    )
    p.add_argument(
        "--counts",
        default="10,100,1000",
        help="Comma-separated object counts to test (default: 10,100,1000).",
    )
    p.add_argument(
        "--trials", type=int, default=5, help="Recorded trials per count (default: 5)."
    )
    p.add_argument(
        "--layout",
        choices=["flat", "nested"],
        default="flat",
        help=(
            "Key layout. 'flat' puts all objects in one prefix. 'nested' spreads "
            "them across two directory levels, emulating partitioned lakehouse "
            "layouts (default: flat)."
        ),
    )
    p.add_argument(
        "--fanout",
        type=int,
        default=10,
        help="Objects per leaf directory when --layout nested (default: 10).",
    )
    p.add_argument("--output-json", default=None, help="Write full results as JSON.")
    p.add_argument(
        "--teardown",
        action="store_true",
        help="Delete benchmark objects after measuring.",
    )
    p.add_argument(
        "--teardown-only",
        action="store_true",
        help="Delete benchmark objects and exit without measuring.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    counts = [int(c.strip()) for c in args.counts.split(",") if c.strip()]
    client = make_client(args.region)

    targets: list[tuple[str, str]] = [("fsx-ontap-s3ap", args.ap_arn)]
    if args.native_bucket:
        targets.append(("native-s3", args.native_bucket))

    if args.teardown_only:
        for label, bucket in targets:
            for count in counts:
                prefix = f"{args.prefix}{args.layout}-n{count:06d}/"
                n = delete_prefix(client, bucket, prefix)
                print(f"[{label}] deleted {n} objects under {prefix}")
        return 0

    print("=" * 72)
    print("ListObjectsV2 latency benchmark")
    print(f"  region          : {args.region}")
    print(f"  object counts   : {counts}")
    print(f"  trials per count: {args.trials}")
    print(f"  prefix          : {args.prefix}")
    print(f"  layout          : {args.layout}", end="")
    print(f" (fanout={args.fanout})" if args.layout == "nested" else "")
    print("=" * 72)

    all_results: dict[str, list[TrialSet]] = {}
    for label, bucket in targets:
        print(f"\n>>> target: {label}")
        all_results[label] = run_target(
            client,
            label,
            bucket,
            args.prefix,
            counts,
            args.trials,
            args.layout,
            args.fanout,
        )

    print("\n" + "=" * 72)
    print("RESULTS")
    print("=" * 72)
    for label, results in all_results.items():
        for ts in results:
            s = ts.summary()
            print(
                f"[{label}] n={s['object_count']:>5} "
                f"median={s['median_ms']:>9.1f} ms  "
                f"mean={s['mean_ms']:>9.1f} ms  "
                f"min={s['min_ms']:>9.1f} ms  "
                f"max={s['max_ms']:>9.1f} ms  "
                f"api_calls={s['api_calls_per_trial']}"
            )

    comparison: list[dict[str, Any]] = []
    if "native-s3" in all_results:
        comparison = build_comparison(
            all_results["fsx-ontap-s3ap"], all_results["native-s3"]
        )
        print("\n" + markdown_table(comparison))

    payload = {
        "benchmark": "listobjectsv2-latency",
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "region": args.region,
        "object_counts": counts,
        "trials_per_count": args.trials,
        "layout": args.layout,
        "fanout": args.fanout if args.layout == "nested" else None,
        "timing_scope": (
            "Paginated ListObjectsV2 loop only. Client construction, credential "
            "resolution, and object setup excluded. One discarded warm-up call "
            "per (target, count) before recorded trials."
        ),
        "results": {
            label: [ts.summary() for ts in results]
            for label, results in all_results.items()
        },
        "comparison": comparison,
    }

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"\nWrote {args.output_json}")

    if args.teardown:
        print("\nTearing down benchmark objects ...")
        for label, bucket in targets:
            for count in counts:
                prefix = f"{args.prefix}{args.layout}-n{count:06d}/"
                n = delete_prefix(client, bucket, prefix)
                print(f"[{label}] deleted {n} objects under {prefix}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
