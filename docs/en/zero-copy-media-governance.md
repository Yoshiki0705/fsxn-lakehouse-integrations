# Zero-Copy Media Governance: Eliminating S3 Duplication with FSx for ONTAP + Databricks UC

🌐 [日本語](../ja/zero-copy-media-governance.md) | English

## Customer Challenge

| # | Challenge | Root Cause |
|---|-----------|-----------|
| 1 | S3 storage costs growing continuously; want to eliminate duplicate data | Generic file server → DataSync (file-level diff) → S3 full copy creates redundant storage |
| 2 | Need tag-based access control for images/videos across organizations on Databricks | No governance layer on flat S3 copies; Databricks is the decided platform |

### Current Architecture (Problem State)

```
On-premises Generic File Server (NAS/Windows)
  ↓ DataSync (file-level diff — full file retransfer on any change)
Amazon S3 (full copy, no deduplication)
  ↓
Databricks UC / Other services

Problems:
- No deduplication on either file server or S3
- DataSync file-diff: 1-byte change → entire file retransferred
- S3 cost grows linearly with data volume
- No governance on media assets
```

---

## Solution Options

### Option A: S3 Optimization Only (Minimal Change)

```
Generic File Server (unchanged)
  ↓ DataSync (file-level diff)
S3 bucket
  ├── S3 Intelligent-Tiering (auto-tiering)
  ├── S3 Lifecycle Policy (delete old versions)
  └── UC External Volume (governance)
```

| Pros | Cons |
|------|------|
| No infrastructure change | No deduplication possible |
| Quick to implement | DataSync bandwidth inefficiency remains |
| | Storage cost reduction limited (tiering only) |

**Cost reduction**: 20-40% (tiering only, no dedup)

---

### Option B: FSx for ONTAP Migration (Recommended)

**Replace S3 copies with FSx for ONTAP as the single cloud copy with inline deduplication.**

```
Generic File Server
  ↓ DataSync (one-time migration)
FSx for ONTAP (single cloud copy)
  │ ← Inline deduplication + compression (automatic)
  │ ← Snapshot (point-in-time recovery)
  │ ← FabricPool (auto-tier cold data to S3 at $0.0125/GB)
  │
  ↓ S3 Access Point (multiple APs for different consumers)
  ├── AP-1: Databricks (Instance Profile + boto3)
  ├── AP-2: Bedrock Knowledge Base
  └── AP-3: Other services

S3 full copy = ELIMINATED
DataSync ongoing sync = ELIMINATED (or minimal for new files)
```

**Cost comparison (10TB media assets)**:

| Item | Current (Generic FS + S3) | Option B (FSx for ONTAP) |
|------|--------------------------|--------------------------|
| On-prem storage | Generic FS: 10TB | Eliminated (cloud migration) |
| S3 storage | 10TB × $0.023/GB = **$230/mo** | $0 (no S3 copy needed) |
| FSx for ONTAP | — | 10TB → 5TB (dedup) × $0.08/GB = **$400/mo** |
| FabricPool (cold 80%) | — | 4TB → S3 IA = **$50/mo** |
| DataSync transfer | Monthly diff cost | Eliminated |
| **Total storage** | $230 + on-prem ops | **$450/mo** (no on-prem ops) |

**Net effect**: When on-prem operational costs (hardware, power, rack, personnel) are included, FSx for ONTAP typically achieves lower TCO.

**ONTAP deduplication effectiveness**:

| Data Type | Typical Dedup Rate | 10TB → Effective |
|-----------|-------------------|-----------------|
| Images (many similar) | 20-40% | 6-8TB |
| Videos (low duplication) | 5-15% | 8.5-9.5TB |
| Documents (many versions) | 40-70% | 3-6TB |
| Mixed workload | 30-50% | 5-7TB |

---

### Option C: On-prem ONTAP + SnapMirror (Hybrid)

**Replace generic file server with on-prem ONTAP, use SnapMirror for block-level sync.**

```
On-prem ONTAP (replaces generic file server)
  │ ← Inline deduplication + compression
  │ ← Snapshot
  │
  ↓ SnapMirror (block-level diff = maximum bandwidth efficiency)
FSx for ONTAP (cloud replica)
  ↓ S3 Access Point
  ├── Databricks
  └── Other services

DataSync (file-level diff) = ELIMINATED
S3 full copy = ELIMINATED
```

**DataSync vs SnapMirror bandwidth efficiency**:

| Aspect | DataSync (file diff) | SnapMirror (block diff) |
|--------|---------------------|------------------------|
| Diff detection | File timestamp/size comparison | Block-level change tracking |
| 1-byte change in 10GB file | **10GB retransferred** | **4KB transferred** |
| Bandwidth efficiency | Low | **2,500x more efficient** |
| Network compression | None | Built-in |
| Encryption | TLS | TLS + SnapMirror encryption |

---

### Option D: FlexCache S3 Access Points (Future Roadmap)

> **Status**: FlexCache S3 Access Points support is expected to be available soon. This option represents the future-state architecture.

**FlexCache enables on-prem ONTAP to serve as a read cache for FSx for ONTAP data, with S3 AP providing the analytics access layer.**

```
On-prem ONTAP (source of truth)
  ↓ SnapMirror
FSx for ONTAP (cloud replica)
  ↓ FlexCache S3 Access Point (NEW — coming soon)
  │
  │ FlexCache provides:
  │ - Read caching of hot data at edge/on-prem
  │ - S3 AP access to cached data without full replication
  │ - Reduced WAN bandwidth (only cache misses traverse WAN)
  │
  ↓ S3 Access Point (on FlexCache volume)
  ├── Databricks (low-latency access to hot data)
  ├── Bedrock KB
  └── Other services

Benefits over current architecture:
- Hot data cached locally → sub-millisecond read latency
- Cold data fetched on-demand → no full replication needed
- S3 AP on FlexCache → analytics engines access cached data directly
- Deduplication preserved across cache and origin
```

**FlexCache S3 AP vs Full Replication**:

| Aspect | Full Replication (SnapMirror) | FlexCache S3 AP |
|--------|------------------------------|-----------------|
| Storage required | Full copy at destination | Cache size only (10-30% of origin) |
| Initial sync time | Hours-days (full dataset) | Minutes (cache warms on access) |
| Bandwidth | Block-level diff (efficient) | On-demand fetch (most efficient) |
| Read latency (hot) | Local disk speed | Local disk speed (cached) |
| Read latency (cold) | Local disk speed | WAN RTT (cache miss) |
| Write support | Full read-write | Read-only (write-back to origin) |
| S3 AP access | ✅ (on FSx volume) | ✅ (on FlexCache volume — coming soon) |
| Cost | Full storage at both sites | Cache storage only |

**Architecture with FlexCache S3 AP**:

```
┌─────────────────────────────────────────────────────────────┐
│  On-premises                                                 │
│  ┌──────────────────┐                                       │
│  │ ONTAP (Source)    │                                       │
│  │ 10TB media assets │                                       │
│  │ Dedup: 5TB actual │                                       │
│  └────────┬─────────┘                                       │
│           │ SnapMirror (block diff)                          │
└───────────┼─────────────────────────────────────────────────┘
            │ Direct Connect / VPN
┌───────────┼─────────────────────────────────────────────────┐
│  AWS      ▼                                                 │
│  ┌──────────────────┐     ┌──────────────────────┐          │
│  │ FSx for ONTAP    │     │ FlexCache Volume     │          │
│  │ (Full replica)   │────▶│ (2TB cache, hot data)│          │
│  │ 5TB (dedup)      │     │ S3 AP enabled        │          │
│  └──────────────────┘     └──────────┬───────────┘          │
│                                      │                      │
│                           ┌──────────▼───────────┐          │
│                           │ S3 Access Point      │          │
│                           │ (on FlexCache)       │          │
│                           └──────────┬───────────┘          │
│                                      │                      │
│                    ┌─────────────────┼─────────────────┐    │
│                    │                 │                 │    │
│              ┌─────▼──────┐   ┌──────▼──────┐  ┌──────▼──┐  │
│              │ Databricks │   │ Bedrock KB  │  │ Athena  │  │
│              │ UC Volume  │   │             │  │         │  │
│              └────────────┘   └─────────────┘  └─────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Cost projection (FlexCache S3 AP)**:

| Item | Full Replication | FlexCache S3 AP |
|------|-----------------|-----------------|
| FSx storage | 5TB × $0.08 = $400/mo | 2TB cache × $0.08 = $160/mo |
| FabricPool | $50/mo | $20/mo |
| **Total** | **$450/mo** | **$180/mo** |
| **Savings vs current S3 copy** | 50% | **80%** |

---

## Databricks Governance for Media Assets (All Options)

### UC Volume + Metadata Table + Tag-based Access Control + Delta Sharing

```sql
-- 1. External Volume (backed by S3 or FSx S3 AP via DataSync subset)
CREATE EXTERNAL VOLUME media_assets
  LOCATION 's3://company-media-bucket/assets/';

-- 2. Metadata catalog table
CREATE TABLE media_catalog (
  asset_id STRING GENERATED ALWAYS AS IDENTITY,
  volume_path STRING,
  media_type STRING,            -- 'image/jpeg', 'video/mp4'
  department STRING,
  project STRING,
  classification STRING,        -- 'public', 'internal', 'confidential'
  tags MAP<STRING, STRING>,
  file_size_bytes BIGINT,
  checksum STRING,              -- For duplicate detection
  source_path STRING,
  synced_at TIMESTAMP
);

-- 3. UC Tags
ALTER TABLE media_catalog SET TAGS ('data_domain' = 'media_assets');

-- 4. Tag-based Row Filter
CREATE FUNCTION media_access_filter(department STRING, classification STRING)
RETURN
  IS_ACCOUNT_GROUP_MEMBER('media_admin')
  OR (department = current_user_attribute('department')
      AND classification IN ('public', 'internal'))
  OR (IS_ACCOUNT_GROUP_MEMBER(concat(department, '_confidential'))
      AND classification = 'confidential');

ALTER TABLE media_catalog SET ROW FILTER media_access_filter
  ON (department, classification);

-- 5. Delta Sharing (cross-organization)
CREATE SHARE media_partner_share;
ALTER SHARE media_partner_share ADD TABLE media_catalog;

-- 6. Duplicate detection
SELECT checksum, COUNT(*) as copies,
       SUM(file_size_bytes) as wasted_bytes
FROM media_catalog
GROUP BY checksum HAVING COUNT(*) > 1;
```

---

## Recommendation Matrix

| Priority | Recommended Option | Rationale |
|----------|-------------------|-----------|
| **Fastest cost reduction** | Option B (FSx for ONTAP) | Inline dedup eliminates 30-50% storage; S3 copy eliminated |
| **Maximum bandwidth efficiency** | Option C (SnapMirror) | Block-level diff = 2500x more efficient than DataSync |
| **Future-optimal (lowest cost)** | Option D (FlexCache S3 AP) | Cache-only storage = 80% cost reduction vs current |
| **Minimal change** | Option A (S3 optimization) | Tiering only, limited savings |
| **Databricks governance** | UC Volume + Tags + Delta Sharing | All options; independent of storage choice |

---

## Persona Perspectives Summary

| Persona | Key Recommendation |
|---------|-------------------|
| **Snowflake PMM** | Consider Snowflake Horizon for governance enforcement on external engines. Even with Databricks decided, Horizon can govern the same data for other consumers. |
| **Databricks SA** | UC Volumes + Delta Sharing is the correct path. For S3 cost, recommend S3 Intelligent-Tiering as immediate action, FSx for ONTAP as strategic solution. |
| **AWS Iceberg SA** | FSx for ONTAP S3 AP eliminates the need for S3 copies entirely. FlexCache S3 AP (roadmap) will further reduce costs by 60%+. |
| **Storage Specialist** | ONTAP deduplication is the only way to achieve true storage efficiency. S3 has no native dedup. Moving to FSx for ONTAP is the root-cause fix. |
| **Partner SA** | NetApp BlueXP provides unified management. DataSync → FSx migration is well-supported. FlexCache S3 AP will be a game-changer for hybrid architectures. |
| **Public Sector SA** | Data sovereignty requirements may mandate on-prem ONTAP + SnapMirror (Option C). FlexCache S3 AP enables cloud analytics without full data replication. |
| **Outcome SA** | Customer's real goal is "cost reduction + governed sharing." FlexCache S3 AP (roadmap) achieves both with minimal data movement. |
