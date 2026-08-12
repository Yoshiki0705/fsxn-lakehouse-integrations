#!/usr/bin/env python3
"""Probe object-tag and user-metadata behaviour on an FSx for ONTAP S3 Access Point.

Why this exists
---------------
Databricks' ``_object_metadata`` column (DBR 18.2+) and the FILE type (Beta)
both make object-storage-side metadata part of the lakehouse story: object tags
and ``x-amz-meta-*`` headers become queryable columns. That turns "can we tag
objects on an FSx for ONTAP Access Point?" into a design question rather than
trivia, because the answer decides whether metadata applied at write time can be
inherited by a metadata table downstream.

AWS documents the tagging operations as supported and Object Annotations as not
supported, which settles capability but not the operating envelope. Measured
2026-08-12 on one file system, the envelope had two surprises:

* Tag keys and values are effectively ASCII. Characters at U+0100 and above are
  rejected with ``InvalidTag`` for most strings but accepted for a few
  (``分類`` accepted, ``東京`` rejected — both two-character CJK). Outcomes are
  stable per string across repeats, so this is not flakiness, but no rule could
  be inferred. Restrict tags to ASCII.
* Tags and user metadata are silently cleared by an object overwrite, so a
  pipeline that rewrites a file must re-apply them in the same PutObject.

Tags are stored with the ONTAP file rather than with the Access Point: a tag
written through one Access Point is readable through another Access Point on the
same volume.

Re-run this after an ONTAP version change or in a new region before relying on
the character-set result, because it was established on a single file system.

Evidence: verification-pack/s3ap-object-tagging/evidence/2026-08-12/
Discussion: docs/en/databricks-file-type-evaluation.md

What this does NOT establish
---------------------------
Whether tags are visible from NFS or SMB, and whether they survive SnapMirror,
FlexClone, Snapshot restore or FabricPool tiering. Those need a NAS client and
ONTAP-side operations, neither of which this script touches.

Usage
-----
    # full probe against one Access Point
    ./probe_s3ap_object_tagging.py --access-point <alias>

    # also check that tags are file-scoped, not Access-Point-scoped
    ./probe_s3ap_object_tagging.py --access-point <alias> \
        --second-access-point <alias-on-same-volume>

    # skip the character-set sweep (it issues ~40 requests)
    ./probe_s3ap_object_tagging.py --access-point <alias> --skip-charset

    # machine readable
    ./probe_s3ap_object_tagging.py --access-point <alias> --json

Objects are written under ``--prefix`` (default ``_probe-object-tagging/``) and
deleted before exit, including on failure.

Exit codes
----------
    0  probe completed; tagging is supported
    1  an error, or tagging is not supported on this Access Point
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import uuid

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    sys.exit("boto3 is required: pip install boto3")

# Codepoints chosen to bracket the observed Latin-1 boundary rather than to
# cover scripts exhaustively. U+00FF is the highest value seen accepted and
# U+0100 the lowest seen rejected.
CHARSET_PROBES = [
    ("ascii", "confidential"),
    ("ascii-space", "hello world"),
    ("ascii-specials", "a+b-c=d.e_f:g/h"),
    ("latin1-e-acute-U+00E9", "café"),
    ("latin1-u-umlaut-U+00FC", "ü"),
    ("latin1-boundary-U+00FF", "ÿ"),
    ("beyond-latin1-U+0100", "Ā"),
    ("greek-U+03B2", "β"),
    ("cyrillic-U+0434", "д"),
    ("hiragana-U+3042", "あ"),
    ("katakana-U+30A2", "ア"),
    ("cjk-U+6A5F", "機"),
    ("fullwidth-U+FF21", "Ａ"),
    ("non-bmp-emoji", "🙂"),
]

# Strings whose acceptance differed despite being the same script and length.
# Kept so a re-run can show whether the inconsistency still reproduces.
INCONSISTENCY_PROBES = ["分類", "品質", "名古屋", "東京", "機密", "日本語"]


def _tagging_error(exc: ClientError) -> str:
    msg = str(exc)
    field = "TagValue" if "TagValue" in msg else "TagKey" if "TagKey" in msg else "?"
    return f"{exc.response.get('Error', {}).get('Code', '?')}/{field}"


class Probe:
    def __init__(self, s3, bucket: str, key: str) -> None:
        self.s3, self.bucket, self.key = s3, bucket, key

    def clear_tags(self) -> None:
        try:
            self.s3.delete_object_tagging(Bucket=self.bucket, Key=self.key)
        except ClientError:
            pass

    def try_tag(self, key: str, value: str) -> tuple[bool, str | None]:
        """Return (accepted, error). Clears tagging first so results are independent."""
        self.clear_tags()
        try:
            self.s3.put_object_tagging(
                Bucket=self.bucket, Key=self.key,
                Tagging={"TagSet": [{"Key": key, "Value": value}]},
            )
            return True, None
        except ClientError as exc:
            return False, _tagging_error(exc)

    def boundary(self, make, lo: int, hi: int) -> dict:
        """Confirm ``lo`` is accepted and ``hi`` is rejected for a length limit."""
        acc, acc_err = self.try_tag(*make(lo))
        rej, rej_err = self.try_tag(*make(hi))
        return {
            "accepted_at": lo, "accepted": acc, "accepted_error": acc_err,
            "rejected_at": hi, "rejected": not rej, "rejected_error": rej_err,
            "matches_native_s3": acc and not rej,
        }


def run(args) -> dict:
    s3 = boto3.client("s3", region_name=args.region)
    prefix = args.prefix.strip("/")
    key = f"{prefix}/probe-{uuid.uuid4().hex[:8]}.txt"
    body = b"object tag probe payload\n"
    out: dict = {"access_point": args.access_point, "key": key, "region": args.region}
    written = False

    try:
        # --- write path: user metadata and tags in a single PutObject ---------
        try:
            s3.put_object(
                Bucket=args.access_point, Key=key, Body=body,
                ContentType="text/plain",
                Metadata={"dept": "quality", "lineid": "A12"},
                Tagging="classification=internal&owner_team=eng",
            )
            written = True
            out["write_time_tagging"] = {"supported": True}
        except ClientError as exc:
            out["write_time_tagging"] = {"supported": False, "error": str(exc)[:200]}
            return out

        head = s3.head_object(Bucket=args.access_point, Key=key)
        out["user_metadata_roundtrip"] = {
            "supported": bool(head.get("Metadata")),
            "returned": head.get("Metadata"),
            "storage_class": head.get("StorageClass"),
            "server_side_encryption": head.get("ServerSideEncryption"),
        }
        out["write_time_tagging"]["returned"] = s3.get_object_tagging(
            Bucket=args.access_point, Key=key)["TagSet"]

        probe = Probe(s3, args.access_point, key)

        # --- limits ----------------------------------------------------------
        def put_n_tags(n: int) -> tuple[bool, str | None]:
            probe.clear_tags()
            try:
                s3.put_object_tagging(
                    Bucket=args.access_point, Key=key,
                    Tagging={"TagSet": [{"Key": f"k{i}", "Value": f"v{i}"} for i in range(n)]},
                )
                return True, None
            except ClientError as exc:
                return False, _tagging_error(exc)

        ok10, _ = put_n_tags(10)
        ok11, err11 = put_n_tags(11)
        out["limits"] = {
            "max_tags_per_object": {
                "accepted_at": 10, "accepted": ok10,
                "rejected_at": 11, "rejected": not ok11, "rejected_error": err11,
                "matches_native_s3": ok10 and not ok11,
            },
            "tag_key_length": probe.boundary(lambda n: ("k" * n, "v"), 128, 129),
            "tag_value_length": probe.boundary(lambda n: ("k", "v" * n), 256, 257),
        }

        # --- character set ---------------------------------------------------
        if not args.skip_charset:
            charset = []
            for label, value in CHARSET_PROBES:
                accepted, err = probe.try_tag("probe", value)
                charset.append({
                    "label": label,
                    "codepoints": [f"U+{ord(c):04X}" for c in value][:4],
                    "accepted": accepted, "error": err,
                })
            out["charset"] = charset

            # --- is validation per-character? ---------------------------------
            # Added 2026-08-12 after AWS Support escalated the charset behaviour
            # to the FSx for ONTAP service team. A per-character allowlist is the
            # natural implementation to suspect, and this rules it out: a
            # character rejected on its own can be accepted inside a longer
            # string. Recorded here so nobody has to re-derive it.
            distinct = list(dict.fromkeys("".join(INCONSISTENCY_PROBES)))
            per_char = []
            for ch in distinct:
                runs = [probe.try_tag(ch, "v")[0] for _ in range(args.repeats)]
                per_char.append({
                    "char": ch, "codepoint": f"U+{ord(ch):04X}",
                    "accepted_runs": sum(runs), "total_runs": len(runs),
                    "deterministic": len(set(runs)) == 1,
                })
            out["per_character"] = per_char

            # Does the per-character result explain the whole string? On the
            # 2026-08-12 file system it did not.
            single = {c["char"]: c["accepted_runs"] == c["total_runs"] for c in per_char}
            composition = []
            for s in INCONSISTENCY_PROBES:
                whole = probe.try_tag(s, "v")[0]
                predicted = all(single.get(c, False) for c in s)
                composition.append({
                    "string": s,
                    "codepoints": [f"U+{ord(c):04X}" for c in s],
                    "every_char_accepted_alone": predicted,
                    "whole_string_accepted": whole,
                    "compositional": predicted == whole,
                })
            out["composition"] = composition

            # --- does the position matter? -----------------------------------
            # Same string as tag key and as tag value. On the 2026-08-12 file
            # system the results were identical; the error only names whichever
            # field carried the string.
            position = []
            for s in INCONSISTENCY_PROBES:
                as_key, err_k = probe.try_tag(s, "probe")
                as_val, err_v = probe.try_tag("probe", s)
                position.append({
                    "string": s,
                    "as_tag_key": as_key, "key_error": err_k,
                    "as_tag_value": as_val, "value_error": err_v,
                    "position_independent": as_key == as_val,
                })
            out["position"] = position

            inconsistency = []
            for s in INCONSISTENCY_PROBES:
                runs = [probe.try_tag(s, "v")[0] for _ in range(args.repeats)]
                inconsistency.append({
                    "string": s, "as_tag_key": True,
                    "accepted_runs": sum(runs), "total_runs": len(runs),
                    "deterministic": len(set(runs)) == 1,
                })
            out["multibyte_inconsistency"] = inconsistency
            out["multibyte_verdict"] = (
                "mixed — some multibyte strings accepted, some rejected; restrict tags to ASCII"
                if any(0 < i["accepted_runs"] < i["total_runs"] or i["accepted_runs"] > 0
                       for i in inconsistency)
                and any(i["accepted_runs"] == 0 for i in inconsistency)
                else "uniform"
            )

        # --- scope: file-scoped or access-point-scoped? ----------------------
        probe.clear_tags()
        s3.put_object_tagging(
            Bucket=args.access_point, Key=key,
            Tagging={"TagSet": [{"Key": "scopecheck", "Value": "written-via-ap1"}]},
        )
        if args.second_access_point:
            try:
                seen = s3.get_object_tagging(
                    Bucket=args.second_access_point, Key=key)["TagSet"]
                out["scope"] = {
                    "second_access_point": args.second_access_point,
                    "tags_visible_via_second_ap": bool(seen), "returned": seen,
                    "conclusion": "file-scoped" if seen else "access-point-scoped",
                }
            except ClientError as exc:
                out["scope"] = {"error": str(exc)[:200],
                                "note": "second Access Point must target the same volume"}
        else:
            out["scope"] = {"skipped": "pass --second-access-point to test this"}

        # --- durability across overwrite ------------------------------------
        s3.put_object(Bucket=args.access_point, Key=key, Body=body)
        out["durability_on_overwrite"] = {
            "tags_after_overwrite": s3.get_object_tagging(
                Bucket=args.access_point, Key=key)["TagSet"],
            "user_metadata_after_overwrite": s3.head_object(
                Bucket=args.access_point, Key=key).get("Metadata"),
            "note": "empty means PutObject cleared them — re-apply in the same request",
        }

        # --- per-file read cost ---------------------------------------------
        s3.get_object_tagging(Bucket=args.access_point, Key=key)  # warm
        samples = []
        for _ in range(args.latency_samples):
            t0 = time.perf_counter()
            s3.get_object_tagging(Bucket=args.access_point, Key=key)
            samples.append((time.perf_counter() - t0) * 1000)
        out["get_object_tagging_latency_ms"] = {
            "n": len(samples),
            "min": round(min(samples)), "median": round(statistics.median(samples)),
            "max": round(max(samples)),
            "caveat": "single caller, one object, warm. Sample run, not a benchmark.",
        }
        return out

    finally:
        if written:
            try:
                s3.delete_object(Bucket=args.access_point, Key=key)
                out["cleanup"] = "probe object deleted"
            except ClientError as exc:
                out["cleanup"] = f"FAILED to delete {key}: {str(exc)[:120]}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--access-point", required=True,
                   help="Access Point alias or ARN to probe")
    p.add_argument("--second-access-point",
                   help="another Access Point on the SAME volume, to test tag scope")
    p.add_argument("--prefix", default="_probe-object-tagging",
                   help="prefix for the probe object (default: _probe-object-tagging)")
    p.add_argument("--region", default=None, help="AWS region (default: from environment)")
    p.add_argument("--repeats", type=int, default=3,
                   help="repeats per multibyte string, to separate flakiness from a stable rule")
    p.add_argument("--latency-samples", type=int, default=10)
    p.add_argument("--skip-charset", action="store_true",
                   help="skip the character-set sweep (~40 requests)")
    p.add_argument("--json", action="store_true", help="emit JSON only")
    args = p.parse_args()

    try:
        result = run(args)
    except Exception as exc:  # noqa: BLE001 — report and exit non-zero
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("write_time_tagging", {}).get("supported") else 1

    print(f"Access Point : {result['access_point']}")
    if not result.get("write_time_tagging", {}).get("supported"):
        print("tagging      : NOT SUPPORTED")
        print(f"  {result['write_time_tagging'].get('error')}")
        return 1

    print("write-time tagging (x-amz-tagging on PutObject) : supported")
    um = result["user_metadata_roundtrip"]
    print(f"user metadata (x-amz-meta-*)                   : "
          f"{'supported' if um['supported'] else 'NOT returned'}  {um['returned']}")
    print(f"storage class                                  : {um['storage_class']}")

    print("\nlimits (vs native Amazon S3)")
    for name, r in result["limits"].items():
        verdict = "same as native S3" if r["matches_native_s3"] else "DIFFERS"
        print(f"  {name:20} accept@{r['accepted_at']} reject@{r['rejected_at']}  {verdict}")

    if "composition" in result:
        alone = sum(1 for c in result["per_character"]
                    if c["accepted_runs"] == c["total_runs"])
        non_comp = [c for c in result["composition"] if not c["compositional"]]
        print(f"\nper-character: {alone} of {len(result['per_character'])} "
              f"characters accepted alone")
        print(f"composition:   {len(non_comp)} of {len(result['composition'])} "
              f"strings are NOT explained by their characters")
        for c in non_comp:
            print(f"   {' '.join(c['codepoints'])}: every char accepted alone="
                  f"{c['every_char_accepted_alone']}, whole string accepted="
                  f"{c['whole_string_accepted']}")
        if non_comp:
            print("   -> validation is a property of the whole byte sequence, "
                  "not of its characters")
    if "position" in result:
        dep = [x for x in result["position"] if not x["position_independent"]]
        print("position:      " + ("independent of tag key vs tag value"
                                   if not dep else
                                   f"{len(dep)} string(s) differ by position"))
    if "charset" in result:
        acc = [c["label"] for c in result["charset"] if c["accepted"]]
        rej = [c["label"] for c in result["charset"] if not c["accepted"]]
        print(f"\ncharset  accepted: {len(acc)}  rejected: {len(rej)}")
        for c in result["charset"]:
            print(f"  {'OK  ' if c['accepted'] else 'FAIL'} {c['label']:26} "
                  f"{','.join(c['codepoints'])}")
        print("\nmultibyte strings as tag keys (stability check)")
        for i in result["multibyte_inconsistency"]:
            print(f"  {i['string']:6} {i['accepted_runs']}/{i['total_runs']} accepted"
                  f"  {'stable' if i['deterministic'] else 'NON-DETERMINISTIC'}")
        print(f"  verdict: {result['multibyte_verdict']}")

    sc = result["scope"]
    print(f"\ntag scope : {sc.get('conclusion', sc.get('skipped', sc.get('error')))}")

    d = result["durability_on_overwrite"]
    print(f"after overwrite : tags={d['tags_after_overwrite']} "
          f"metadata={d['user_metadata_after_overwrite']}")

    lat = result["get_object_tagging_latency_ms"]
    print(f"\nGetObjectTagging : median {lat['median']} ms "
          f"(min {lat['min']}, max {lat['max']}, n={lat['n']})")
    print(f"  {lat['caveat']}")
    print(f"\ncleanup : {result.get('cleanup')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
