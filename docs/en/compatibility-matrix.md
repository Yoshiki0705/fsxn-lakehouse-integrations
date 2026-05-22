# Compatibility Matrix

## Overview

This document defines the verified compatibility between FSx for ONTAP S3 Access Points and Lakehouse platforms/formats. The matrix is based on the S3 API operations supported by FSx for ONTAP access points as documented in [Access point compatibility](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html).

## Critical Constraints of FSx for ONTAP S3 Access Points

Before reviewing the compatibility matrix, understand these fundamental constraints:

| Constraint | Detail | Source |
|-----------|--------|--------|
| No Rename operation | S3 API does not have a native rename. CopyObject is supported only within the same access point. | [API support](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| Max upload size: 5 GB | Single object upload limited to 5 GB (multipart upload supported) | [API support](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| No Object Versioning | S3 Object Versioning is not supported | [API support](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| No conditional writes | Conditional writes are not supported | [API support](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| No Presigned URLs | Presigned URL generation is not supported | [API support](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| Storage class: FSX_ONTAP only | Cannot specify other storage classes | [API support](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| Encryption: SSE-FSX only | AWS KMS managed, transparent encryption at rest | [API support](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html) |
| Same region required | Access point must be in same region as FSx for ONTAP volume | [Restrictions](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-point-for-fsxn-restrictions-limitations-naming-rules.html) |
| Same account required | Access point and file system must be in same AWS account | [Restrictions](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-point-for-fsxn-restrictions-limitations-naming-rules.html) |
| ONTAP 9.17.1+ required | Minimum ONTAP version for S3 Access Points | [Restrictions](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-point-for-fsxn-restrictions-limitations-naming-rules.html) |

## Impact on Lakehouse Table Formats

Lakehouse table formats (Delta Lake, Apache Iceberg, Apache Hudi) rely on specific S3 behaviors for transactional guarantees:

| Requirement | Delta Lake | Apache Iceberg | Apache Hudi | FSx S3 AP Support |
|-------------|-----------|----------------|-------------|-------------------|
| Atomic rename for commit | Required (\_delta\_log/) | Not required (uses metadata pointers) | Required (timeline) | **Not available** — CopyObject + DeleteObject as workaround within same AP |
| Consistent list-after-write | Required | Required | Required | Supported (ONTAP provides consistency) |
| PutObject | Required | Required | Required | Supported |
| DeleteObject | Required for vacuum/cleanup | Required for expiration | Required | Supported |
| Multipart upload | For large files | For large files | For large files | Supported (5 GB max per upload) |
| Conditional writes (If-None-Match) | Used by some implementations | Used by some implementations | Used by some implementations | **Not supported** |

## Platform × Format × Mode Compatibility Matrix

### Legend

| Status | Meaning |
|--------|---------|
| ✅ Verified | Tested and confirmed working |
| ⚠️ Experimental | Partially working with known limitations |
| ❌ Not Supported | Does not work due to fundamental constraints |
| 🔲 Planned | Not yet tested |

### Matrix

| Platform | Format | Mode | Status | Required Setting | Known Limitation |
|----------|--------|------|--------|-----------------|------------------|
| **Amazon Athena** | Parquet | Read-only | ✅ Verified | Internet-origin AP, Glue Catalog, IAM role with s3:GetObject/ListBucket on AP ARN | Athena cannot use VPC-origin APs (accesses from managed infra outside VPC). Results written to separate S3 bucket, not back to FSx. |
| **Amazon Athena** | CSV | Read-only | ✅ Verified | Same as Parquet | Same as above |
| **Amazon Athena** | JSON | Read-only | ✅ Verified | Same as Parquet | Same as above |
| **Amazon Athena** | ORC | Read-only | ✅ Verified | Same as Parquet | Same as above |
| **Amazon Athena** | Delta Lake | Read-only (symlink manifest) | ⚠️ Experimental | Athena Delta Lake connector, symlink_format_manifest generation required | No direct Delta log reading; requires pre-generated manifest. Write/MERGE not supported. |
| **Amazon Athena** | Iceberg | Read-only | 🔲 Planned | Athena Iceberg connector, Glue Catalog as Iceberg catalog | Read path should work; write path untested. |
| **AWS Glue ETL** | Parquet | Read | ✅ Verified | Glue IAM role with AP permissions, AP alias in S3 path | — |
| **AWS Glue ETL** | Parquet | Write (Append) | ✅ Verified | Read-write file system user on AP | 5 GB max per file upload |
| **AWS Glue ETL** | Parquet | Overwrite | ⚠️ Experimental | Read-write file system user | DeleteObject + PutObject pattern; no atomic overwrite guarantee |
| **AWS Glue ETL** | Delta Lake | Read | ⚠️ Experimental | Glue 4.0+ with Delta Lake library | Delta log reading works; commit protocol untested for writes |
| **AWS Glue ETL** | Delta Lake | Write | ❌ Not Supported | — | Delta commit protocol requires atomic rename of _delta_log JSON files; not natively supported |
| **Amazon EMR Serverless** | Parquet | Read | ✅ Verified | Spark with S3A connector, AP alias | — |
| **Amazon EMR Serverless** | Parquet | Write (Append) | ✅ Verified | Read-write file system user | 5 GB max per file |
| **Amazon EMR Serverless** | Iceberg | Read | ⚠️ Experimental | Iceberg Spark runtime, Glue Catalog | Metadata reading works; write commit untested |
| **Amazon EMR Serverless** | Delta Lake | Read | ⚠️ Experimental | Delta Lake Spark library | Log reading works |
| **Amazon EMR Serverless** | Delta Lake | Write/MERGE | ❌ Not Supported | — | Atomic rename required for commit protocol |
| **Databricks** | Parquet/CSV | Read (External Location) | ✅ Verified | Unity Catalog External Location, instance profile/storage credential with AP permissions | — |
| **Databricks** | Delta Lake | Read (External Table) | ⚠️ Experimental | Unity Catalog, Delta log on FSx volume | Read works if Delta log is pre-existing |
| **Databricks** | Delta Lake | Write/MERGE/Compaction | ❌ Not Supported | — | Delta commit protocol requires rename; S3A rename emulation (copy+delete) may fail without conditional writes |
| **Snowflake** | Parquet/CSV | Read (External Stage) | ✅ Verified | External Stage with AP alias, storage integration IAM role | — |
| **Snowflake** | Iceberg | Read (External Catalog) | ⚠️ Experimental | Snowflake Iceberg Tables with external catalog | Metadata pointer reading works |
| **Snowflake** | Any | Write | ❌ Not Supported | — | Snowflake External Stages are read-only by design |
| **Redshift Spectrum** | Parquet/CSV | Read-only | 🔲 Planned | External schema via Glue Catalog, IAM role with AP permissions | Expected to work (same pattern as Athena) |
| **Amazon Bedrock** | Documents (PDF, TXT, etc.) | Read (Knowledge Base) | ✅ Verified | Bedrock Knowledge Base with S3 data source pointing to AP | For RAG applications; documents indexed for retrieval |

## Performance Characteristics

**Important**: S3 API access via FSx for ONTAP S3 Access Points is **NOT equivalent to native S3 performance**. Performance depends on the FSx file system's provisioned throughput capacity.

| Characteristic | FSx S3 Access Point | Native S3 |
|---------------|--------------------:|----------:|
| Latency | Tens of milliseconds | Single-digit milliseconds |
| Throughput | Limited by FSx provisioned throughput | Virtually unlimited (scales with prefixes) |
| Requests/sec | Limited by FSx provisioned throughput | 5,500 GET/s per prefix, 3,500 PUT/s per prefix |
| Max object size (upload) | 5 GB | 5 TB |
| Concurrent readers | Limited by FSx throughput capacity | Highly parallel |

Source: [Amazon FSx for NetApp ONTAP performance](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html), [Accessing your data via Amazon S3 access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)

### Throughput Planning

When planning analytics workloads on FSx S3 Access Points:

1. **Identify peak scan volume**: e.g., 100 GB table scan
2. **Determine acceptable query time**: e.g., < 60 seconds
3. **Calculate required throughput**: 100 GB / 60s ≈ 1.7 GB/s read throughput
4. **Provision accordingly**: Select FSx throughput capacity that meets or exceeds requirement

Note: Write operations consume 2x network bandwidth (replicated to secondary file server in Multi-AZ).

## Required IAM Permissions by Platform

| Platform | Required IAM Actions on Access Point ARN |
|----------|------------------------------------------|
| Athena (via Glue) | `s3:GetObject`, `s3:ListBucket` on AP ARN and AP ARN/object/* |
| Glue Crawler | `s3:GetObject`, `s3:ListBucket` on AP ARN |
| Glue ETL (read-write) | `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket` |
| EMR Serverless | `s3:GetObject`, `s3:PutObject`, `s3:ListBucket`, `s3:DeleteObject` |
| Databricks | `s3:GetObject`, `s3:PutObject`, `s3:ListBucket`, `s3:DeleteObject`, `s3:GetBucketLocation` |
| Snowflake | `s3:GetObject`, `s3:ListBucket`, `s3:GetBucketLocation` |
| Bedrock Knowledge Base | `s3:GetObject`, `s3:ListBucket` |

Additionally, the **file system user** associated with the access point must have appropriate UNIX/NTFS permissions on the volume's files and directories.

## Snapshot vs. Lakehouse Time Travel

See [Recovery Semantics](recovery-semantics.md) for detailed comparison.

---

## Verification Level Definitions

| Level | Definition | What Was Tested | Confidence for Production |
|-------|-----------|-----------------|--------------------------|
| **API Verified** | Basic S3 API operations succeed against FSx S3 AP | GetObject/PutObject/ListObjectsV2 return expected results | Low — only confirms API compatibility |
| **Functional Verified** | Representative end-to-end use case succeeds | Full workflow: data upload → catalog registration → query → correct results | Medium — confirms the pattern works |
| **Security Verified** | IAM, AP policy, VPC endpoint, file system permissions, CloudTrail all confirmed | Unauthorized access denied at both layers; audit events logged | High — confirms security posture |
| **Production Validated** | Customer PoC or production-equivalent load tested | Concurrent queries, failure recovery, cost validation, SLA compliance | Highest — ready for production proposal |

### Current Verification Status

| Platform + Mode | Verification Level | Notes |
|----------------|-------------------|-------|
| Athena + Parquet Read | Security Verified | AWS official tutorial validates full workflow including IAM |
| Glue ETL + Parquet Read/Write | Functional Verified | AWS official tutorial validates read and write-back |
| EMR Serverless + Parquet Read/Write | Functional Verified | AWS official tutorial validates Spark workflow |
| Bedrock Knowledge Base + Document Read | Functional Verified | AWS official tutorial validates RAG ingestion |
| Databricks + Parquet Read | API Verified | External Location registration and read confirmed |
| Snowflake + Parquet Read | API Verified | External Stage creation and query confirmed |
| Delta Lake Write (any platform) | Not Supported | Fundamental constraint (no atomic rename) |

---

## Lakehouse Commit Protocol Sequences

### Why This Matters

Lakehouse table formats require specific S3 behaviors for transactional guarantees. Understanding the commit protocol explains why some operations work and others do not on FSx S3 AP.

### Delta Lake Write Path (NOT SUPPORTED on FSx S3 AP)

```
Writer                          S3 (or FSx S3 AP)
  │                                    │
  │  1. Write data files               │
  │  ──── PutObject(part-00000.parquet)──▶│  ✅ Supported
  │                                    │
  │  2. Write commit JSON              │
  │  ──── PutObject(_delta_log/tmp/...)──▶│  ✅ Supported
  │                                    │
  │  3. ATOMIC RENAME commit file      │
  │  ──── Rename(tmp/... → 00001.json)──▶│  ❌ NOT SUPPORTED
  │                                    │     (No rename operation in S3 API)
  │  Fallback: CopyObject + Delete     │
  │  ──── CopyObject(tmp → 00001.json)─▶│  ⚠️ Supported (same AP only)
  │  ──── DeleteObject(tmp/...)────────▶│  ✅ Supported
  │                                    │
  │  4. Verify commit (conditional)    │
  │  ──── If-None-Match check ────────▶│  ❌ NOT SUPPORTED
  │                                    │     (No conditional writes)
  └────────────────────────────────────┘

RESULT: Without atomic rename AND conditional writes, Delta Lake cannot
guarantee exactly-once commit semantics. Concurrent writers may corrupt
the transaction log. DO NOT USE for production writes.
```

### Apache Iceberg with External Catalog (EXPERIMENTAL Read on FSx S3 AP)

```
Writer                    Glue Catalog           FSx S3 AP
  │                           │                      │
  │  1. Write data files      │                      │
  │  ──── PutObject(data/...) ──────────────────────▶│  ✅ Supported
  │                           │                      │
  │  2. Write metadata file   │                      │
  │  ──── PutObject(metadata/snap-N.avro) ─────────▶│  ✅ Supported
  │                           │                      │
  │  3. Update catalog pointer│                      │
  │  ──── UpdateTable(metadata_location) ──▶│        │
  │                           │  ✅ Catalog          │
  │                           │  manages pointer     │
  │                           │  (no rename needed)  │
  │                           │                      │
  │  4. Reader queries        │                      │
  │       GetTable() ────────▶│                      │
  │       ◀── metadata_location                      │
  │       GetObject(snap-N.avro) ──────────────────▶│  ✅ Supported
  │       GetObject(data/...) ─────────────────────▶│  ✅ Supported
  └───────────────────────────┴──────────────────────┘

RESULT: Iceberg with external catalog (Glue) does NOT require rename
for commit. The catalog atomically updates the metadata pointer.
READ PATH works. WRITE PATH is theoretically possible but untested
for concurrent writers and compaction on FSx S3 AP.
```

### Read-Only Analytics Path (VERIFIED on FSx S3 AP)

```
Athena/Glue/EMR           Glue Catalog           FSx S3 AP
  │                           │                      │
  │  1. Get table metadata    │                      │
  │  ──── GetTable() ────────▶│                      │
  │  ◀── location: s3://ap-alias/path/              │
  │                           │                      │
  │  2. List data files       │                      │
  │  ──── ListObjectsV2(prefix) ──────────────────▶│  ✅ Supported
  │  ◀── file list                                   │
  │                           │                      │
  │  3. Read data files       │                      │
  │  ──── GetObject(file1.parquet) ────────────────▶│  ✅ Supported
  │  ──── GetObject(file2.parquet) ────────────────▶│  ✅ Supported
  │  ◀── data                                        │
  │                           │                      │
  │  4. Return query results  │                      │
  └───────────────────────────┴──────────────────────┘

RESULT: Read-only analytics is the safest and most verified pattern.
No rename, no conditional writes, no concurrent writer conflicts.
```

---

## Workload-Specific Performance Characteristics

| Workload | Typical Pattern | Bottleneck | Recommended FSx Config | File Size Guidance | Concurrency | Verification Status |
|----------|----------------|-----------|----------------------|-------------------|-------------|-------------------|
| **Large sequential scan** (Athena full-table) | Few large reads, high throughput | FSx network throughput | ≥ 1 GB/s provisioned throughput | ≥ 128 MB per file (Parquet/ORC) | Low-medium (1-10 queries) | Functional Verified |
| **Small file / metadata-heavy** (many small CSVs) | Many ListObjectsV2 + small GetObject | Request rate, latency | Higher throughput for IOPS headroom | Consolidate to ≥ 32 MB files | Low | API Verified |
| **High-concurrency Athena** (many analysts) | Parallel scans on same data | FSx aggregate throughput | Scale throughput to concurrent load | Partition data for scan reduction | High (10-50 queries) | Not yet validated |
| **Glue ETL read-heavy** (batch transform) | Sequential large reads + write-back | FSx read throughput | ≥ 512 MB/s provisioned | ≥ 128 MB per file | Low (1-5 jobs) | Functional Verified |
| **Spark write-heavy** (ETL output) | Many PutObject calls | FSx write throughput (2x bandwidth) | ≥ 1 GB/s for write-heavy | Target 128-256 MB output files | Low | Functional Verified |
| **RAG document ingestion** (Bedrock) | Many small-medium GetObject | Latency per document | Standard throughput sufficient | N/A (document size varies) | Low (batch ingestion) | Functional Verified |

### Performance Planning Formula

```
Required FSx Throughput = max(
  Read workload:  (Total scan size / Acceptable query time),
  Write workload: (Total write size / Acceptable job time) × 2,  # 2x for Multi-AZ replication
  Concurrent load: Sum of all concurrent workload throughput needs
)
```

---

## Failure Scenario FAQ

### Q: What happens after an ONTAP Snapshot restore?

**A**: Snapshot restore reverts all files on the volume to the snapshot point-in-time. Effects:
- **Glue Catalog**: Catalog metadata is NOT on the FSx volume — it remains unchanged. This creates a mismatch: catalog may reference files that no longer exist (if added after snapshot), or miss files that were restored.
- **Action required**: Re-run Glue Crawler after snapshot restore to reconcile catalog with actual file state.
- **Athena queries**: May fail with "file not found" until catalog is refreshed.

### Q: What happens if the S3 Access Point policy is accidentally modified?

**A**: Access point policy changes take effect immediately.
- **If policy becomes too restrictive**: All requests through the AP are denied. Existing queries fail with AccessDenied.
- **If policy becomes too permissive**: Unauthorized principals may gain access (mitigated by file system user permissions as second layer).
- **Recovery**: Update the AP policy via S3 console/CLI/API. Changes are immediate. No AP recreation needed.
- **Prevention**: Use SCPs to restrict who can modify AP policies. Enable CloudTrail to detect changes.

### Q: What happens if a Spark/Glue job fails mid-write?

**A**: Partial files may remain on the FSx volume.
- **Parquet append**: Orphaned partial files exist but are not referenced by catalog. Safe to clean up manually.
- **Delta write (if attempted)**: Transaction log may be in inconsistent state. This is why Delta write is Not Supported.
- **Recovery**: Delete orphaned files via S3 API (DeleteObject) or NFS/SMB. Re-run the job.
- **Note**: FSx S3 AP does not support Object Lifecycle rules for automatic cleanup.

### Q: What happens if a file is updated via NFS while Bedrock is ingesting it?

**A**: FSx for ONTAP provides read-after-write consistency within the file system.
- **If Bedrock reads during NFS write**: May read partial/old content depending on timing.
- **Best practice**: Use ONTAP Snapshot to create a consistent point-in-time view for ingestion, or schedule ingestion during known quiet periods.
- **Note**: S3 AP reads reflect the current state of the file system — there is no eventual consistency delay between NFS write and S3 AP read.

### Q: What happens after SnapMirror failover to DR region?

**A**: The S3 Access Point is bound to the original FSx file system in the source region.
- **AP ARN**: Remains in source region. Does NOT automatically transfer to DR.
- **Action required**: Create a new S3 Access Point on the DR volume in the DR region. Update all references (Glue Catalog location, IAM policies, application configs) to point to the new AP.
- **Automation**: Include AP recreation in DR runbook. Use CloudFormation/Terraform for repeatable setup.
- **Note**: AP names can be reused across regions, but ARNs will differ.

### Q: What happens if the file system user associated with the AP is deleted?

**A**: The access point transitions to `MISCONFIGURED` state.
- **Effect**: All S3 requests through the AP fail.
- **Recovery**: Recreate the user on the file system, or update the AP to use a different valid user.
- **FSx behavior**: FSx periodically checks and automatically returns the AP to `AVAILABLE` when the user identity is resolvable again. ([source](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-ap-manage-access-fsxn.html))

---

## References

- [Access point compatibility — Supported S3 API operations](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)
- [Managing access point access — Dual-layer authorization](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-ap-manage-access-fsxn.html)
- [Amazon FSx for NetApp ONTAP performance](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)
- [Using access points with AWS services](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-access-points-with-aws-services.html)
- [Query files with SQL using Amazon Athena](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)
- [Configuring network access for Amazon S3 access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html)
