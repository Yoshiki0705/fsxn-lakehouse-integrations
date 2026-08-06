🌐 **English** | [日本語](./snowflake-ja.md)

# Feedback: Snowflake

Scope: Snowflake behaviour with Amazon FSx for NetApp ONTAP S3 Access Points, measured
2026-08-06 unless noted.
[Evidence](../../verification-pack/snowflake/evidence/2026-08-06/evidence-record.yaml)

## Summary

The read path is the most thoroughly verified of any third-party platform here. In one
session: Parquet, CSV, JSON, Avro and ORC all read from an Access Point-backed
external stage; `SnowflakeFile.open` in a Snowpark UDF returned file contents;
`BUILD_SCOPED_FILE_URL`, `PARSE_DOCUMENT` and `TO_FILE` all worked; and a Managed
Iceberg Table was populated end to end from `COPY INTO` against the stage, with a
real Iceberg layout on the destination bucket.

Three findings. The first is a genuine defect in a failure path. The second is a
constraint worth documenting. The third is a correction to something this repository
published incorrectly, which is included because the wrong explanation was ours, not
Snowflake's.

| # | Finding | Severity |
|:---:|---|---|
| 1 | [Unload fails checksum validation after the object has landed](#1-unload-fails-checksum-validation-after-the-object-has-landed) | **High** — silent orphaned object |
| 2 | [A Dynamic Table cannot select from an External Table](#2-a-dynamic-table-cannot-select-from-an-external-table) | Low — clean error, simple workaround |
| 3 | [Correction: external stages are not read-only by design](#3-correction-external-stages-are-not-read-only-by-design) | Documentation — our error, not Snowflake's |

---

## 1. Unload fails checksum validation after the object has landed

**Measured** 2026-08-06. [BLK-009](../en/blocker-tracker.md)

`COPY INTO @stage` against an Access Point-backed external stage fails in 479 ms with:

```
Remote upload failed checksum validation. Ensure the destination stage or COPY
command was configured with the storage bucket's default encryption type, such
as AWS_SSE_KMS.
```

**The object is written anyway.** Verified on the Access Point after the failure:

| Property | Value |
|---|---|
| Key | `sfverify/formats/unload_probe_1/data_0_0_0.csv.gz` |
| Size | 25 bytes |
| gzip integrity | Valid |
| Content | Matches what was selected |
| `ServerSideEncryption` | `aws:fsx` |
| `StorageClass` | `FSX_ONTAP` |

### Root cause

FSx for ONTAP reports server-side encryption as `aws:fsx`, which is neither
`AWS_SSE_S3` nor `AWS_SSE_KMS`. Snowflake's post-upload checksum validation does not
recognise it and fails the statement. The write to the file system had already
succeeded by that point.

This is raised with AWS as well, since reporting an unrecognised encryption type is
the upstream cause — see [the AWS page](./aws.md). It is raised here because the
client-side handling is what turns an unrecognised encryption type into a partial
write.

### Why this is ranked high

A failed statement normally means nothing happened. Here it means the write completed
and the acknowledgement failed. Any caller with retry logic will accumulate
duplicates. Anyone who tried this before reading this page has orphans they do not
know about.

The suggested change is not to accept `aws:fsx` blindly. It is to **fail before
writing, or clean up after failing.** Either would preserve the invariant that a
failed `COPY INTO` leaves no output. Validating the stage's encryption type at
statement start, when the stage is already known, would be the cheaper of the two.

### Setting the encryption type explicitly makes it worse

| Attempt | Result |
|---|---|
| No explicit encryption | Failed in 479 ms. Object written |
| `ENCRYPTION=(TYPE='AWS_SSE_S3')` on the stage | **Hung.** Cancelled after 2 m 54 s. Nothing written |

The second row is arguably the more concerning behaviour of the two — a hang gives the
operator nothing to act on. Whether `AWS_SSE_KMS` behaves differently is untested.

**Workaround, verified**: do not unload to an Access Point. Write to Snowflake-managed
storage instead — an internal table, or a Managed Iceberg Table on an External Volume.
The latter was verified end to end in the same session. If NFS or SMB access to the
same volume is available, writing there bypasses the S3 layer entirely.

---

## 2. A Dynamic Table cannot select from an External Table

**Measured** 2026-08-06.

```
CREATE DYNAMIC TABLE ... AS SELECT ... FROM <external table over AP stage>

→ Object ref EXT_FMT_JSON of type EXTERNAL_TABLE not supported in
  Dynamic Table definition
```

Clean rejection, clear message, straightforward workaround. Recorded as a constraint
rather than a defect.

**The working path**, verified in the same session:

| Step | Result |
|---|---|
| `COPY INTO` a standard table from the Access Point-backed stage | PASS, 2,114 ms, 3 rows |
| `CREATE DYNAMIC TABLE (TARGET_LAG='60 seconds', REFRESH_MODE=FULL)` | PASS, 1,872 ms |
| `SELECT` from the Dynamic Table | PASS, 541 ms |

Refresh behaviour matched the specification: after adding a second file and loading
it, aggregates updated correctly, refresh history showed runs about every 48 s with
`refresh_action` of `FULL` when data had changed and `NO_DATA` when it had not, all
`SUCCEEDED`, lag 1–3 s.

**What would help**: mention the External Table restriction in the Dynamic Table
documentation. Anyone designing an incremental pipeline over external data will reach
for exactly this combination first, and the landing step is easy to add once known.

---

## 3. Correction: external stages are not read-only by design

**This is a correction to this repository, not feedback on Snowflake.** It is included
because the incorrect statement was published here and read by others.

Earlier revisions stated:

> Snowflake external stages are read-only by design.

That is wrong. Writes are not refused. The write reaches the file system and the object
is intact; the statement then fails at checksum validation for the reason in item 1.

The wrong explanation was worse than merely inaccurate — it concealed the partial-write
hazard. If stages were read-only by design, a failed unload would imply nothing was
written. Because they are not, a failed unload can leave a complete object behind, and
the incorrect explanation would have led a reader to skip checking.

The [compatibility matrix](../en/compatibility-matrix.md),
[blocker tracker](../en/blocker-tracker.md) and
[unverified inventory](../en/unverified-inventory.md) all now carry the corrected
reason.

---

## Verified in the same session, recorded for completeness

Nothing needed from Snowflake on these. They are here because a feedback document
listing only problems misrepresents the state of the integration.

| Capability | Result |
|---|---|
| JSON, Avro, ORC read from an Access Point-backed stage | All three returned identical rows for identical content. Requires a named `FILE FORMAT` object — an inline `FILE_FORMAT` is not accepted in the stage table-function form. Snowflake syntax, not an Access Point limitation |
| Snowpark `SnowflakeFile.open` | Returned file contents. Useful for unstructured handling SQL cannot express |
| Managed Iceberg Table via `COPY INTO` from the stage | End to end: External Volume created, `SYSTEM$VERIFY_EXTERNAL_VOLUME` passed write/read/list/delete, table created, rows loaded and read back, real Iceberg layout on the destination bucket (metadata JSON, manifest Avro, data Parquet) |
| Glue Iceberg REST with `VENDED_CREDENTIALS` | Verified 2026-06-05. `CREATE TABLE`, `SELECT`, `COUNT`, `DESCRIBE` and `AUTO_REFRESH` all working. Requires explicit `ACCESS_DELEGATION_MODE = VENDED_CREDENTIALS` and a schema with no default External Volume |
| Snowpipe from a synthesized S3 notification | Ingested roughly 0.5 s after publish. Since FSx for ONTAP S3 Access Points emit no S3 events, the notification was synthesized by a Lambda poller. [Evidence](../../verification-pack/snowpipe-pattern-a/evidence/2026-08-06/snowflake-side-verification.yaml) |

### One setup observation

A Snowflake External Volume needs the same two-phase IAM trust setup as a Storage
Integration: create with a placeholder trust policy, read back the generated IAM user
ARN and external ID, then update the trust policy. This is documented, but it is the
step most likely to be missed on a first attempt, and the resulting failure does not
point at the trust policy.

---

## Open items

| Item | Blocked by |
|---|---|
| S3 Tables Iceberg REST endpoint as an External Catalog source | Not a supported catalog type. Feature request filed 2026-05. Glue Iceberg REST works as the alternative and is verified |
| `COPY INTO` 64-day load-history deduplication | 64 days of elapsed time (UNV-003). Cannot be compressed |
| Horizon Catalog governance enforced on external engines reading the Iceberg table | A second engine configured against the catalog (UNV-004) |
| PrivateLink to an Access Point-backed stage | Business Critical edition or higher (UNV-007) |
| Whether `AWS_SSE_KMS` on the destination stage changes the unload outcome | Untested |

> Scale caveat on everything above: every test in the 2026-08-06 session used
> single-digit row counts. The results establish that these paths work, not how they
> behave at volume.
