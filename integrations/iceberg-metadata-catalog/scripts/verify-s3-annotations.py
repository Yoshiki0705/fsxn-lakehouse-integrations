#!/usr/bin/env python3
"""Reproducible verification of Amazon S3 Annotations (announced 2026-06).

Purpose
-------
Validate the object-annotation round-trip that underpins the S3 Annotations
governance/discovery evaluation (see
docs/{ja,en}/s3-annotations-governance-evaluation.md). It demonstrates two
proposal cases on a *native* Amazon S3 general-purpose bucket:

  - Case 1 (enrichment): attach AI-classification "business-context"
  - Case 2 (discovery signal): attach ONTAP-derived "ontap-acl-hint"
    NOTE: a discovery signal is NOT an access-control enforcement boundary.

Scope / boundary
----------------
S3 Metadata + Annotations apply only to Amazon S3 general-purpose buckets
(AWS docs: metadata-tables-restrictions.html). FSx for ONTAP S3 (ONTAP S3
server exposed via S3 Access Points) is NOT an Amazon S3 bucket and cannot
be configured for S3 Metadata. This script therefore runs against a native
S3 bucket — representing the staged-to-S3 pattern, not direct FSx for ONTAP S3 AP.

Safety
------
Creates a uniquely named throwaway bucket and deletes all resources
(annotations -> object -> bucket) in a finally block. No persistent or
billable resources remain after a normal run.

Requirements
------------
- boto3 >= ~1.40 (operations: PutObjectAnnotation, GetObjectAnnotation,
  ListObjectAnnotations, DeleteObjectAnnotation). The bundled AWS CLI v2
  exposes these only from 2.35.7+.
- AWS credentials with s3:CreateBucket/DeleteBucket/PutObject/DeleteObject
  and the s3 object-annotation permissions.

Usage
-----
  AWS_REGION=ap-northeast-1 python3 verify-s3-annotations.py

Last verified: 2026-06-18 (ap-northeast-1, boto3 1.43.32).
"""
import json
import os
import time
import uuid

import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
BUCKET = f"s3ann-verify-{int(time.time())}-{uuid.uuid4().hex[:8]}"
KEY = "staged/quality-inspection/lot-0001/img-0001.png"

BUSINESS_CONTEXT = {
    "schema": "manufacturing.quality.v1",
    "ai_classification": "defect:scratch",
    "ai_confidence": 0.94,
    "model": "bedrock-vision (demo)",
    "source": "synthetic test data",
}
ONTAP_ACL_HINT = {
    "note": "DISCOVERY SIGNAL ONLY - not an access-control enforcement boundary",
    "owner": "svc_quality",
    "group": "line3-inspectors",
    "acl_hash": "sha256:demo0000",
    "svm": "svm_demo",
    "volume": "vol_quality",
    "snapshot_id": "daily.2026-06-18_0000",
    "allowed_principals": ["role/quality-agent", "group/line3-inspectors"],
}


def main() -> int:
    s3 = boto3.client("s3", region_name=REGION)
    results = []
    created = False

    def step(name, ok, detail=""):
        results.append({"step": name, "ok": bool(ok), "detail": str(detail)[:300]})
        print(f"[{'OK ' if ok else 'ERR'}] {name}: {detail}")

    try:
        s3.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": REGION},
        )
        created = True
        step("create_bucket", True, BUCKET)

        s3.put_object(Bucket=BUCKET, Key=KEY, Body=b"\x89PNG demo-bytes")
        step("put_object", True, KEY)

        for name, payload in (
            ("business-context", BUSINESS_CONTEXT),
            ("ontap-acl-hint", ONTAP_ACL_HINT),
        ):
            s3.put_object_annotation(
                Bucket=BUCKET,
                Key=KEY,
                AnnotationName=name,
                AnnotationPayload=json.dumps(payload).encode("utf-8"),
            )
            step(f"put_object_annotation[{name}]", True, "json payload attached")

        lst = s3.list_object_annotations(Bucket=BUCKET, Key=KEY)
        names = [a["AnnotationName"] for a in lst.get("Annotations", [])]
        step("list_object_annotations", True, f"count={lst.get('AnnotationCount')} names={names}")

        got = s3.get_object_annotation(Bucket=BUCKET, Key=KEY, AnnotationName="ontap-acl-hint")
        payload = got["AnnotationPayload"].read().decode("utf-8")
        ok = json.loads(payload).get("owner") == "svc_quality"
        step("get_object_annotation[ontap-acl-hint]", ok, f"roundtrip_ok={ok}")

    finally:
        try:
            for an in ("business-context", "ontap-acl-hint"):
                try:
                    s3.delete_object_annotation(Bucket=BUCKET, Key=KEY, AnnotationName=an)
                except ClientError as e:
                    step(f"cleanup delete_annotation[{an}]", False, e.response["Error"]["Code"])
            try:
                s3.delete_object(Bucket=BUCKET, Key=KEY)
                step("cleanup delete_object", True, KEY)
            except ClientError as e:
                step("cleanup delete_object", False, e.response["Error"]["Code"])
            if created:
                s3.delete_bucket(Bucket=BUCKET)
                step("cleanup delete_bucket", True, BUCKET)
        except Exception as e:  # noqa: BLE001
            step("cleanup", False, repr(e))

    print("\nRESULT_JSON " + json.dumps({"bucket": BUCKET, "key": KEY, "steps": results}))
    return 0 if all(s["ok"] for s in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
