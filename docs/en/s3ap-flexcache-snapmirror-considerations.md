> 🌐 Language: [日本語](../ja/s3ap-flexcache-snapmirror-considerations.md) | **English**

# S3 Access Points + FlexCache / SnapMirror — Additional Design Considerations

> Additional design guidance for distributing S3 AP-collected data via FlexCache (read acceleration) or SnapMirror (DR). Review [general S3 AP design considerations](s3ap-design-considerations.md) first.

---

## Premise

- FSx for ONTAP S3 Access Points are based on the ONTAP S3 NAS bucket mechanism
- S3 AP-attached volumes can be used with SnapMirror / FlexCache like any standard FlexVol/FlexGroup
- For compatibility details, see [research document](../../integrations/snapmirror-flexcache-multicloud/docs/en/research.md)

---

## 1. Directory Design Impact on FlexCache / SnapMirror

S3 AP directory design affects not only standalone performance but also FlexCache / SnapMirror efficiency.

### Impact on FlexCache

| Directory Layout | FlexCache Behavior | Impact |
|-----------------|-------------------|--------|
| 1M files in single directory | Files concentrate on one FlexGroup constituent | Cache load on 1 node only. FlexCache distribution benefit lost |
| Properly distributed directories | Spread across multiple constituents | Cache hits across multiple nodes. FlexCache parallelism utilized |
| Excessively deep hierarchy (>10 levels) | Recursive readdir becomes deep | Multiple Origin round-trips on cache miss |

**Guideline**: When FlexCache is planned, distribute files across directories to leverage FlexGroup constituent parallelism.

### Impact on SnapMirror

| Write Pattern | Effect on Incremental Transfer |
|--------------|-------------------------------|
| Many small files across multiple directories | Changed blocks distributed → efficient incremental transfer |
| Appending to one large file | Changed blocks concentrated → large transfer volume each time |
| Bulk creation in single directory | Directory metadata updates concentrated → transfer volume increase |

**Guideline**: When SnapMirror is planned, writing many small-to-medium files is more transfer-efficient than appending to a single large file.

---

## 2. FlexCache Considerations

### 2.1 Write Mode Selection

| Mode | Behavior | Origin Reflection | Relationship to S3 AP Writes |
|------|----------|:-----------------:|------------------------------|
| write-around (default) | Cache writes forwarded to Origin synchronously | Immediate | Low conflict with Origin-side S3 AP writes |
| write-back | Cache writes stored locally, flushed to Origin asynchronously | 30-90 seconds | Origin-side S3 AP writes revoke XLD, Cache dirty data lost |

**Design Rule**: For "S3 AP writes to Origin, FlexCache reads at destination" pattern, **use write-around mode**. If write-back is used, never write the same file from both S3 AP and FlexCache concurrently.

### 2.2 Cache Propagation and Data Visibility

| Aspect | Value | Notes |
|--------|-------|-------|
| New file visibility (cache miss) | ~3-6 seconds | Validated (intra-cluster ~6s, cross-region <3s) |
| Updated file visibility (cached) | After TTL expires (default 30s) | Adjustable via `read_after_write_flush_time` |
| FlexCache prepopulate | Not supported via S3 AP | NFS/SMB access can pre-warm cache |

**Design Rule**: First read after S3 AP write goes to Origin (cache miss). Subsequent reads within TTL are served from cache.

### 2.3 ListObjectsV2 on FlexCache

When ListObjectsV2 is run on a FlexCache Cache Volume (ONTAP 9.18.1+ with Cache S3):

- ListObjectsV2 is a directory metadata read operation
- Cached directory listings return at local speed
- Cache-miss directories require Origin round-trip (RTT added to latency)

**Recommendation**: Pre-warm frequently-listed prefixes via NFS access to improve response time.

---

## 3. SnapMirror Considerations

### 3.1 S3 AP Metadata Is Not Transferred

SnapMirror transfers volume data (files/directories) only. The following must be configured separately at the destination.

| Item | Transferred? | Destination Action |
|------|:------------:|-------------------|
| File data | ✅ | — |
| UNIX permissions (uid/gid/mode) | ✅ | — |
| NTFS ACLs | ✅ | — |
| S3 Access Point | ❌ | Create new via `aws fsx create-and-attach-s3-access-point` |
| S3 AP IAM policy | ❌ | Configure in destination region |
| S3 user metadata (x-amz-meta-*) | ⚠️ | May persist as ONTAP stream attributes (version-dependent) |
| S3 Object Tags | ⚠️ | Same as above |

**Design Rule**: DR failover procedure must include S3 AP creation + IAM policy configuration. Automate with Lambda or Step Functions.

### 3.2 S3 AP Attachment to DP Volumes

| State | S3 AP Attachment | Notes |
|-------|:----------------:|-------|
| DP (SnapMirror relationship active) | ❌ | Read-only; junction path cannot be set |
| DP → break → RW | ✅ | Set junction path after break, then create S3 AP |
| After resync | ❌ | Returns to DP; S3 AP unusable |

**Design Rule**: S3 AP access requires SnapMirror break. Break stops one-way replication — use in DR failover context. "Maintain SnapMirror while using S3 AP at destination" is not possible.

### 3.3 RPO and Data Visibility

| Item | Value | Notes |
|------|-------|-------|
| SnapMirror Async minimum schedule | 5 minutes | FSx for ONTAP constraint |
| Typical incremental transfer duration | 10-30 seconds | Depends on data volume and throughput capacity |
| Failover RTO (time to S3 AP access) | ~3 minutes | break + junction path + S3 AP creation |
| RPO | = time since last transfer | Worst case: 5 min + in-flight data |

**Design Rule**: Use FlexCache for near-real-time needs, SnapMirror for DR/compliance. Combine both when required.

---

## 4. Integrated Directory Pattern

Recommended directory structure considering S3 AP + FlexCache + SnapMirror together.

```
/volume-root/
  └── {source-id}/                    ← Separate by tenant/source
      └── {year}/{month}/{day}/       ← Time-series partition (Hive-style)
          └── {hour}/                 ← Control files per directory
              ├── {uuid-short}.json
              ├── {uuid-short}.parquet
              └── ...
```

### Requirements This Structure Satisfies

| Requirement | How |
|-------------|-----|
| ListObjectsV2 performance | Prefix narrows target directory; small sort set |
| FlexGroup distribution | Many directories → auto-distributed across constituents |
| FlexCache efficiency | Reads distributed across multiple constituents |
| SnapMirror incremental transfer | Small files × many directories → distributed changed blocks |
| Athena partition pruning | Hive-style partitions auto-recognized by Glue Crawler |
| NFS batch processing | Date directories enable efficient `find` / `rsync` |
| Access control | Tenant directories align with export-policy / AP policy prefix restrictions |

---

## 5. Monitoring

### FlexCache

| Metric | Method | Threshold |
|--------|--------|-----------|
| Cache hit rate | ONTAP REST API: `GET /api/storage/flexcache/flexcaches/{uuid}?fields=*` | < 50% → review directory distribution |
| Origin query latency | `statistics show -object flexcache` | > RTT × 2 → Origin-side bottleneck |
| Cache volume utilization | `volume show -fields percent-used` | > 80% → increased eviction frequency |

### SnapMirror

| Metric | Method | Threshold |
|--------|--------|-----------|
| Lag Time | CloudWatch: `SnapMirrorLagTime` | > RPO target (e.g., 900s) → alert |
| Transfer Duration | CloudWatch: `SnapMirrorTransferDuration` | Increasing trend → write rate exceeds throughput |
| Healthy | CloudWatch: `SnapMirrorHealthy` | < 1 → investigate immediately |

---

## 6. Anti-Patterns

| Pattern | Problem | Mitigation |
|---------|---------|-----------|
| All files in root directory | maxdir-size overflow + FlexCache skew + LIST degradation | Hierarchical partition |
| Appending to one large file | SnapMirror incremental transfer large each time | Split into small files |
| S3 AP + FlexCache write-back on same file | XLD revoke → dirty data lost | Use write-around or separate files |
| Attempt S3 AP on DP volume | Fails (junction path cannot be set) | Break first, then attach |
| Create DP volume via ONTAP REST API only | FSx API propagation takes ~30 min. S3 AP not attachable immediately | Use `aws fsx create-volume` for immediate visibility. For FlexCache (ONTAP API only), wait ~30 min |
| Delete VPC Peering before SVM peer deletion | Zombie SVM peer → MISCONFIGURED → difficult recovery | Follow SM-VAL-011 order |
| Periodic full LIST at root | Latency grows with directory size | Prefix-limited or external catalog |
| Assume cloud-only architecture when data gravity favors on-prem processing | Unnecessary egress costs; latency for time-sensitive workloads | Evaluate SnapMirror to on-prem for licensed tool / low-latency scenarios |

---

## Related Documents

- [General S3 AP Design Considerations](s3ap-design-considerations.md)
- [S3 AP Data Collection CloudFormation Template (with DESIGN TIPs)](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/infrastructure/s3ap-data-collection) — Includes Mermaid data distribution decision flow
- [S3 AP + SnapMirror + FlexCache Research](../../integrations/snapmirror-flexcache-multicloud/docs/en/research.md)
- [Demo Guide 07: SnapMirror Cross-Region + S3 AP Re-Attach](../../integrations/snapmirror-flexcache-multicloud/docs/en/demo-guide-07-snapmirror-cross-region.md)
- [Demo Guide 01: FlexCache Same-Region](../../integrations/snapmirror-flexcache-multicloud/docs/en/demo-guide-01-flexcache-same-region.md)
- [AWS Docs: S3 performance best practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html)
- [NetApp KB: maxdir-size issues](https://kb.netapp.com/on-prem/ontap/Ontap_OS/OS-KBs/How_do_I_avoid_maxdir-size_issues)
- [NetApp Docs: FlexGroup definition](https://docs.netapp.com/us-en/ontap/flexgroup/definition-concept.html)
- [NetApp Docs: FlexCache hotspot remediation](https://docs.netapp.com/us-en/ontap/flexcache-hot-spot/flexcache-hotspot-remediation-architecture.html)
- [NetApp Blog: FlexGroups and Advanced Data Distribution](https://community.netapp.com/t5/Tech-ONTAP-Blogs/FlexGroups-and-Advanced-Data-Distribution/ba-p/456416)
