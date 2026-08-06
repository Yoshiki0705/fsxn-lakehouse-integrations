🌐 **English** | [日本語](./aws-ja.md)

# Feedback: AWS

Scope: Amazon FSx for NetApp ONTAP S3 Access Points, and the AWS analytics services
that read through them. Compiled 2026-08-06.

## Summary

The read path works well and is verified across Athena, Glue, EMR Serverless,
Redshift Spectrum, DuckDB and Bedrock. Iceberg read **and write** through Athena and
the Glue Data Catalog is verified end to end, which is a stronger result than this
repository expected — the catalog-held commit pointer sidesteps the missing object
store primitives entirely.

Two gaps stand out above the rest, and not because of the missing capability itself.
They fail in a way that leaves state behind. That is the difference between a
constraint to design around and a hazard to detect after the fact.

| Priority | Item | Why this ranking |
|:---:|---|---|
| 1 | [Encryption type reported as `aws:fsx`](#1-encryption-type-awsfsx-breaks-client-checksum-validation-after-the-write-lands) | Silent partial write. Client reports failure, object is intact on the Access Point |
| 2 | [Conditional writes return 501](#2-conditional-writes-return-http-501) | Blocks Delta and Hudi, and failed attempts strand data files |
| 3 | [S3 Event Notifications absent](#3-s3-event-notifications-are-not-emitted) | Rules out event-driven ingestion; workarounds are operationally heavier |
| 4 | [SnapMirror S3 disabled](#4-snapmirror-s3-is-disabled-on-fsx-for-ontap) | Capability exists in ONTAP, unreachable through FSx |
| 5 | [EMR Serverless Iceberg write fails](#5-emr-serverless-cannot-write-iceberg-to-an-access-point) | Athena succeeds on identical storage, so this is addressable |
| 6 | [Lake Formation column-level on S3 Tables](#6-lake-formation-column-level-permissions-are-not-available-on-s3-tables-federated-catalogs) | Governance ceiling on an otherwise clean path |
| 7 | [`HeadBucket` is not a health signal](#7-headbucket-succeeds-when-data-operations-do-not) | Documentation gap that sends diagnosis to the wrong layer |

---

## 1. Encryption type `aws:fsx` breaks client checksum validation after the write lands

**Measured** 2026-08-06.
[Evidence](../../verification-pack/snowflake/evidence/2026-08-06/evidence-record.yaml) ·
[BLK-009](../en/blocker-tracker.md)

FSx for ONTAP reports server-side encryption as `aws:fsx`. Clients that validate a
post-upload checksum against the returned encryption type do not recognise it, since
it is neither `AWS_SSE_S3` nor `AWS_SSE_KMS`, and fail the operation.

The write itself succeeds. Snowflake `COPY INTO @stage` failed in 479 ms with:

```
Remote upload failed checksum validation. Ensure the destination stage or COPY
command was configured with the storage bucket's default encryption type, such
as AWS_SSE_KMS.
```

and the object was on the Access Point anyway — 25 bytes, valid gzip, correct
content, `ServerSideEncryption: aws:fsx`, `StorageClass: FSX_ONTAP`.

Setting `ENCRYPTION=(TYPE='AWS_SSE_S3')` on the stage does not help. It converts a
fast failure into a hang: cancelled after 2 minutes 54 seconds with nothing written.

**Why this is ranked first.** A caller that sees a failed statement will reasonably
assume nothing was written. Here a complete object remains. Anyone who has attempted
unload against an Access Point-backed stage has orphans they do not know about. This
is a correctness problem in the failure path, not a missing feature.

**What would resolve it**: report an encryption type that S3 clients already accept,
or document `aws:fsx` prominently enough that client vendors can add it to their
accepted set. The second option needs coordination with every client; the first does
not.

---

## 2. Conditional writes return HTTP 501

**Confirmed** 2026-05-22 as a product-level limitation.
[BLK-002](../en/blocker-tracker.md)

`If-None-Match` returns `501 NotImplemented`. Amazon S3 has supported conditional
writes since August 2024, so this is a parity gap rather than a novel request.

### What it actually blocks, measured

The scope is narrower than this repository previously stated, and the correction
matters for anyone reading older revisions.

| Format / engine | Write | Reason |
|---|:---:|---|
| Iceberg via Athena + Glue Data Catalog | ✅ Works | Glue holds the current-metadata pointer, so the commit is a conditional update in Glue rather than on the object store. CREATE, INSERT, UPDATE, DELETE, time travel, `OPTIMIZE`, `VACUUM` and two concurrent commits all succeeded ([evidence](../../verification-pack/athena-iceberg/evidence/2026-08-06/evidence-record.yaml)) |
| Delta Lake, any engine | ❌ Fails | The commit log lives in `_delta_log/` on the object store, so the commit needs the primitive that is missing |
| Hudi | ❓ Not tested | Same atomic-rename requirement in the timeline. This is inference, not measurement (UNV-023) |

Delta's failure, verbatim, from delta-rs 1.2.1 on 2026-05-23:

```
Generic S3 error: Error performing PUT
.../delta-lake/write_test/_delta_log/00000000000000000000.json
- Server returned non-2xx status code: 501 Not Implemented
```

### The secondary effect matters as much as the primary one

Delta writes Parquet data files first and commits second. When the commit hits the
501, **the data files stay.** Observed on the verification Access Point 2026-08-06:
four prefixes holding Delta data files with no `_delta_log`, one of them with three
files written a minute apart — retries, each leaving its own residue.

This is the same residue shape as item 1, from an unrelated cause. Two independent
paths to the same operational problem suggests the failure path deserves attention
alongside the feature gap.

**What would resolve it**: implement `If-None-Match` for parity with S3 native.

---

## 3. S3 Event Notifications are not emitted

**Confirmed** 2026-05-22. [BLK-003](../en/blocker-tracker.md)

No `s3:ObjectCreated` or related events. This rules out Snowpipe auto-ingest,
Databricks Auto Loader notification mode, and any EventBridge-triggered pipeline
reading directly from an Access Point.

Workarounds exist and were partially verified. Lambda polling → SNS → Snowpipe was
verified on both legs: the AWS side (6 defects found and fixed during
implementation) and the Snowflake side, which ingested roughly 0.5 s after publish
([evidence](../../verification-pack/snowpipe-pattern-a/evidence/2026-08-06/snowflake-side-verification.yaml)).

**The trade-off, stated fairly**: FPolicy → Lambda is technically valid but carries
real operational weight — Lambda concurrency limits, DLQ handling, backpressure. If
a DataSync schedule at `rate(5 minutes)` meets the requirement, that is the simpler
choice. This is not a blocker that stops work; it is one that makes the simple
architecture unavailable.

---

## 4. SnapMirror S3 is disabled on FSx for ONTAP

**Confirmed** 2026-05-26 on ONTAP 9.17.1P6, via both CLI and REST API.
[Evidence](../../verification-pack/snapmirror-s3/evidence/2026-05-26/evidence-record.yaml) ·
[BLK-004](../en/blocker-tracker.md) · [ADR-002](../adr/ADR-002-snapmirror-s3-unavailability.md)

| Probe | Result |
|---|---|
| `snapmirror object-store show` | `"object-store" is not a recognized command` — at admin, advanced and diagnostic privilege alike |
| `GET /api/cloud/targets` | `{"error":{"message":"not authorized for that command","code":"6"}}` |
| `snapmirror policy show -type continuous` | The `Continuous` policy exists, with the comment "Policy for S3 bucket mirroring" — but cannot be referenced |

The ONTAP S3 protocol layer itself is functional: `vserver object-store-server
create` and `bucket create` both succeeded on a fresh SVM. So this is a managed
service restriction, not an ONTAP version limitation.

**Why it matters for migration planning**: on-premises ONTAP supports SnapMirror S3
from 9.10.1+. A migration plan written against on-premises capability will assume
this works. AWS DataSync (NFS → S3) is the only verified sync mechanism on FSx for
ONTAP, and it loses ONTAP-native replication efficiency.

**Documentation observation**: `docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-snapmirror.html`
redirects to the FSx for ONTAP main page, and the scheduled-replication page covers
only volume-level SnapMirror. The absence is not documented as an absence, so it is
discovered by attempting it.

---

## 5. EMR Serverless cannot write Iceberg to an Access Point

**Measured** 2026-05-24.
[Evidence](../../verification-pack/iceberg/evidence/2026-05-24/evidence-record.yaml)

```
java.lang.NullPointerException: Cannot invoke
"org.apache.iceberg.TableMetadata.metadataFileLocation()"
because "metadata" is null
```

The failure is in Iceberg's metadata write and commit verification, not in the data
file write. Glue Catalog database creation succeeded.

**This is now clearly addressable, and that is new information.** When this was
recorded, the assumption was that Iceberg writes were blocked by the same missing
primitives as Delta. The Athena Iceberg run on 2026-08-06 disproved that: the same
table format, on the same Access Point, completed a full lifecycle. Athena's Iceberg
implementation does not traverse the S3FileIO code path that fails here.

So the constraint is in how S3FileIO resolves an Access Point alias, not in the
storage. Filed against Apache Iceberg as well — see
[the Iceberg page](./apache-iceberg.md) — but EMR Serverless ships and configures
that runtime, so the fix has two possible homes.

---

## 6. Lake Formation column-level permissions are not available on S3 Tables federated catalogs

**Confirmed** 2026-05. [BLK-008](../en/blocker-tracker.md)

Table-level grants work. Column-level masking does not.

The workaround is to place tables needing column-level control on ordinary Glue
Catalog tables over general-purpose S3 buckets, where Lake Formation column masks
apply normally. That works, but it means the governance model differs depending on
where a table lives, which is a design constraint that has to be carried through the
whole catalog layout.

Athena is the only zero-configuration SQL path to S3 Tables via the Glue federated
catalog, and it applies Lake Formation governance at table level in sub-2-second
queries. The column-level gap is the one ceiling on an otherwise clean path.

---

## 7. `HeadBucket` succeeds when data operations do not

Observed across several diagnostic sessions; see
[networking considerations](../en/fsx-ontap-s3ap-networking.md).

`HeadBucket` validates that the Access Point exists at the S3 layer without
traversing the file system, so it returns 200 in situations where
`ListObjectsV2`, `GetObject` and `PutObject` all return `AccessDenied` or time out.

Two situations produce this:

| Situation | What is actually wrong |
|---|---|
| SVM has DNS servers configured for AD membership and they are unreachable | Every Access Point on that SVM times out. The S3 request path traverses the SVM name-service stack, which needs DNS to reach domain controllers. Volume security style, export policies and Access Point lifecycle state are all irrelevant |
| VPC-attached compute reaching an internet-origin Access Point through an S3 Gateway Endpoint | The alias resolves to `s3-r-w.<region>.amazonaws.com`, which may not be in the prefix list the Gateway Endpoint uses. Traffic is intercepted and not routed |

In both cases a green `HeadBucket` plus correct IAM sends the investigation to the
IAM and Access Point policy layers, which are not where the problem is.

**What would help**: document that `HeadBucket` does not exercise the file system
path, and recommend `ListObjectsV2 --max-keys 1` as the connectivity probe. This is
a documentation change, and it would save a lot of misdirected debugging.

---

## Corrections to this repository's own record

Stated here because two of them were raised with AWS as problems and should not
remain on the record uncorrected.

| Previous claim | Current state |
|---|---|
| ListObjectsV2 is 30–80x slower than native S3 | **Withdrawn.** Re-measured 2026-08-05 at 0.9–1.4x for 10 to 5,000 objects, flat and nested layouts alike, all inside the original performance target. The 30–80x figure did not reproduce and its origin was not determined. Behaviour above 5,000 objects in one directory is still unmeasured (UNV-025), and ONTAP sorts directory entries in memory, so file consolidation remains sound practice — just not for the reason previously given. [Evidence](../../verification-pack/s3ap-list-latency/evidence/2026-08-05/benchmark-result.yaml) |
| Concurrent Iceberg writes risk corrupting the table | **Withdrawn as inference.** Two concurrent Athena commits produced the correct row count with no lost update. Two writers is not a concurrency limit, but the risk is not categorical as previously implied |
| Delta write is blocked, therefore all table format writes are blocked | **Corrected.** Iceberg via Athena + Glue works. The determining factor is where the commit pointer lives, not the storage |

## What the verified results do not cover

Stated so the positive results are not over-read.

| Gap | Effect on interpretation |
|---|---|
| The Athena Iceberg run used single-digit row counts | Manifest growth, compaction cost and partition evolution at realistic scale are unmeasured (UNV-021) |
| The Athena concurrency run was cache-resident | 25/25 queries succeeded with full scans degrading about 2x, but roughly 389 MB/s aggregate moved through a file system provisioned at 128 MBps. Caching did significant work. Read it as evidence that concurrency is not a failure mode up to 25, not as a throughput model (UNV-022) |
| Only `SINGLE_AZ_1` at 128 MBps was tested | Multi-AZ behaviour and higher throughput tiers are unmeasured. Note that writes consume 2x network bandwidth on Multi-AZ |
