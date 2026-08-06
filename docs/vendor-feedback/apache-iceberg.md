🌐 **English** | [日本語](./apache-iceberg-ja.md)

# Feedback: Apache Iceberg

Scope: `S3FileIO` handling of an Amazon FSx for NetApp ONTAP S3 Access Point alias
during metadata write. Compiled 2026-08-06.

## Summary

One finding, and it is more actionable than it looked when first recorded.

Iceberg on an FSx for ONTAP S3 Access Point works — verified end to end through Athena
and the Glue Data Catalog, including UPDATE, DELETE, time travel, `OPTIMIZE`, `VACUUM`
and two concurrent commits. The same table format on the same storage fails through
EMR Serverless with a `NullPointerException` in the commit path.

Since the format works and the storage works, the gap is in how `S3FileIO` resolves an
Access Point alias. That makes it a client-code issue rather than a storage
compatibility issue, which is a meaningful reclassification.

---

## The failure

**Measured** 2026-05-24 on EMR Serverless 7.1.0.
[Evidence](../../verification-pack/iceberg/evidence/2026-05-24/evidence-record.yaml)

`CREATE TABLE` with the warehouse path on an Access Point alias fails during the
metadata write:

```
java.lang.NullPointerException: Cannot invoke
"org.apache.iceberg.TableMetadata.metadataFileLocation()"
because "metadata" is null
```

| Observation | Detail |
|---|---|
| Failure point | Metadata write and commit verification |
| Data file write | Not reached |
| Glue Catalog database creation | Succeeded (`glue:CreateDatabase` works) |
| Warehouse path form | Access Point alias used as the bucket name, e.g. `s3://<ap-alias>-ext-s3alias/path` |

The recorded root-cause analysis considered three possibilities:

1. `S3FileIO` may not correctly handle an S3 Access Point alias as a bucket name
2. The metadata `PutObject` may succeed while the subsequent `HeadObject` or
   `GetObject` verification fails due to alias resolution
3. The commit protocol may require operations the Access Point does not support

## Why possibility 3 can now be ruled out

This is the part worth adding, because it was not knowable when the failure was
recorded.

At the time, FSx for ONTAP S3 Access Points were known to return `501 NotImplemented`
for conditional writes, and Delta Lake writes were known to fail for that reason. The
reasonable inference was that Iceberg writes failed for the same reason.

The Athena run on 2026-08-06 disproved that inference.
[Evidence](../../verification-pack/athena-iceberg/evidence/2026-08-06/evidence-record.yaml)

| Operation on an Access Point via Athena + Glue | Result |
|---|---|
| `CREATE TABLE` (Iceberg) | Succeeded, 1,607 ms |
| `INSERT INTO` (commit) | Succeeded, 4,766 ms |
| `UPDATE` (row-level) | Succeeded, 4,733 ms |
| `DELETE` (row-level) | Succeeded, 6,323 ms |
| Time travel `FOR VERSION AS OF` | Succeeded |
| `OPTIMIZE ... REWRITE DATA` | Succeeded, 4,748 ms |
| `VACUUM` (expire snapshots) | Succeeded, 4,773 ms |
| Two concurrent `INSERT` statements | Both succeeded; count correct, no lost update |

Data and metadata both lived on the Access Point — 11 objects written, 3 data files and
8 metadata files. The commit needs no conditional write on the object store because
Glue holds the current-metadata pointer and the commit is a conditional update in Glue.

So the Access Point supports everything Iceberg's commit protocol asks of it. The EMR
failure is possibility 1 or 2, in `S3FileIO`.

## What would help

| Suggestion | Rationale |
|---|---|
| Confirm whether `S3FileIO` supports an S3 Access Point alias as a bucket name, and document the answer either way | The current situation is that it appears to work — the alias is syntactically a valid bucket name — until commit verification. An explicit statement of support or non-support would let users choose a path immediately |
| Fail with a diagnosable error rather than a `NullPointerException` | `metadata is null` gives no indication that alias resolution is involved. A message naming the path that could not be verified would point at the cause |
| If aliases are not supported, consider accepting an Access Point ARN | Some AWS SDK paths accept the ARN form where the alias does not resolve identically. Whether this helps here is untested — noted as a direction, not a conclusion |

## What this project has not tested

Stated so the finding is not read as more complete than it is.

| Gap | Note |
|---|---|
| `S3FileIO` configured with an Access Point ARN instead of an alias | Listed in the evidence record as a recommendation to investigate; never run |
| `S3AFileSystem` (`s3a://`) instead of `S3FileIO` | Same — recommended in the record, not attempted |
| Iceberg write from AWS Glue ETL | UNV-017 / UNV-018. Glue 4.0 has native Iceberg support and uses the Glue Catalog for pointer management, so it may behave like Athena rather than like EMR. No run |
| Concurrent writers beyond two | The Athena run tested two simultaneous commits. That shows concurrency is not categorically unsafe here; it is not a concurrency limit |
| Realistic table size | The Athena run held single-digit rows. Manifest growth, compaction cost and partition evolution at scale are unmeasured (UNV-021) |
| Position-delete versus copy-on-write behaviour | Not inspected |

## Status

Not yet filed with the Apache Iceberg project. Also recorded on
[the AWS page](./aws.md), since EMR Serverless ships and configures the runtime, so a
fix could land in either place.

## Context for anyone reading this from the Iceberg side

FSx for ONTAP S3 Access Points expose NFS/SMB file data through an S3 API. The relevant
differences from Amazon S3 for Iceberg:

| Property | State |
|---|---|
| Conditional writes (`If-None-Match`) | Returns `501 NotImplemented`. Does not matter when the catalog holds the pointer, as the Athena result shows |
| Atomic rename | Not available; no S3 API has it. Iceberg does not need it |
| Consistent list-after-write | Supported |
| `PutObject`, `GetObject`, `DeleteObject`, multipart | Supported |
| Max single upload | 5 GB |
| Object versioning | Not supported |
| Bucket addressing | Access Point alias, of the form `<name>-<suffix>-ext-s3alias` |
